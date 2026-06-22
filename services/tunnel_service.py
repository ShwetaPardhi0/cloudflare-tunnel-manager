from utils.logger import logger
from utils.error_handler import validate_tunnel_request, get_cloudflared_error
from config import settings
import os
import shutil
import re
import uuid
import asyncio
import signal
import subprocess
import threading
import socket
from typing import Optional
from collections import deque
from sqlalchemy import select, update
from datetime import datetime

from models.tunnel_model import Tunnel
from utils.database import AsyncSessionLocal, init_db
from utils import metrics


# Dictionary to store active tunnels, keyed by unique tunnel_id (UUID)
active_tunnels = {}

# Global metrics - lazy initialization
_start_time = None
_session_start_time = None
total_tunnels_created = 0
failed_tunnels_count = 0

def get_start_time():
    global _start_time, _session_start_time
    # Use session start time if active tunnels exist, otherwise 0
    if not active_tunnels:
        return 0
        
    if _session_start_time is None:
        try:
            loop = asyncio.get_running_loop()
            _session_start_time = loop.time()
        except RuntimeError:
            return 0
    return _session_start_time

def _sync_read_output(pipe, tunnel_id: str):
    """Fallback: Synchronously reads cloudflared pipe line by line (used in thread)."""
    global failed_tunnels_count
    url_found = False
    
    for line in iter(pipe.readline, b''):
        line_decoded = line.decode('utf-8', errors='replace').strip()
        
        # Buffer logs
        if tunnel_id in active_tunnels:
            active_tunnels[tunnel_id]["logs"].append(line_decoded)
            
        logger.debug(f"cloudflared-sync output: {line_decoded}", extra={"tunnel_id": tunnel_id})

        if not url_found:
            pattern = r"https://[a-zA-Z0-9-]+\.trycloudflare\.com"
            match = re.search(pattern, line_decoded)
            if match:
                if tunnel_id in active_tunnels:
                    active_tunnels[tunnel_id]["url"] = match.group(0)
                    active_tunnels[tunnel_id]["status"] = "connected"
                    # Sync to DB
                    asyncio.create_task(_update_tunnel_in_db(tunnel_id, url=match.group(0), status="connected"))
                    
                    # Update Metrics
                    metrics.tunnel_active_count.inc()
                    metrics.tunnel_operations_total.labels(operation="start", status="success").inc()
                    
                    logger.info(
                        f"Tunnel {tunnel_id} connected (Sync Fallback)", 
                        extra={"tunnel_id": tunnel_id, "url": match.group(0), "mode": "sync_fallback"}
                    )
                url_found = True
    pipe.close()


async def _read_process_output(process, tunnel_id: str):
    """
    Asynchronously reads cloudflared stderr to extract the tunnel URL.
    Includes a 30-second watchdog to fail if a URL is not generated.
    """
    global failed_tunnels_count
    url_found = False
    start_time = asyncio.get_running_loop().time()
    watchdog_timeout = 30.0

    # cloudflared logs everything to stderr
    while True:
        # Check for watchdog timeout
        current_time = asyncio.get_running_loop().time()
        if not url_found and (current_time - start_time > watchdog_timeout):
            if tunnel_id in active_tunnels and active_tunnels[tunnel_id]["status"] == "starting":
                logger.error(
                    f"Watchdog timeout: Tunnel failed to generate URL in {watchdog_timeout}s",
                    extra={"tunnel_id": tunnel_id, "timeout": watchdog_timeout}
                )
                active_tunnels[tunnel_id]["status"] = "error"
                active_tunnels[tunnel_id]["error"] = "Timeout: Public URL was not generated in time."
                
                # Increment failure metrics
                failed_tunnels_count += 1
                
                # Update Metrics
                metrics.tunnel_connection_errors_total.labels(error_type="watchdog_timeout").inc()
                metrics.tunnel_operations_total.labels(operation="start", status="failure").inc()
            # We don't break yet, keep reading logs until process dies
            url_found = True # Prevent duplicate timeout logs

        try:
            line = await asyncio.wait_for(process.stderr.readline(), timeout=1.0)
            if not line:
                break
        except asyncio.TimeoutError:
            if process.returncode is not None:
                break
            continue

        line_decoded = line.decode('utf-8', errors='replace').strip()
        
        # Buffer logs
        if tunnel_id in active_tunnels:
            active_tunnels[tunnel_id]["logs"].append(line_decoded)

        logger.debug(f"cloudflared output: {line_decoded}", extra={"tunnel_id": tunnel_id})

        if not url_found:
            pattern = r"https://[a-zA-Z0-9-]+\.trycloudflare\.com"
            match = re.search(pattern, line_decoded)
            if match:
                if tunnel_id in active_tunnels:
                    active_tunnels[tunnel_id]["url"] = match.group(0)
                    active_tunnels[tunnel_id]["status"] = "connected"
                    # Sync to DB
                    await _update_tunnel_in_db(tunnel_id, url=match.group(0), status="connected")
                    
                    # Update Metrics
                    duration = asyncio.get_running_loop().time() - active_tunnels[tunnel_id]["start_time_loop"]
                    metrics.tunnel_start_duration_seconds.observe(duration)
                    metrics.tunnel_active_count.inc()
                    metrics.tunnel_operations_total.labels(operation="start", status="success").inc()
                    
                    logger.info(
                        f"Tunnel {tunnel_id} connected", 
                        extra={"tunnel_id": tunnel_id, "url": match.group(0), "duration_s": duration}
                    )
                url_found = True

    # If the process terminates, handle the failure/error status
    if tunnel_id in active_tunnels:
        tdata = active_tunnels[tunnel_id]
        if tdata["status"] != "error":
            returncode = process.returncode if process.returncode is not None else -1
            error_msg = get_cloudflared_error(returncode)
            tdata["status"] = "error"
            tdata["error"] = error_msg
            # Sync to DB
            await _update_tunnel_in_db(tunnel_id, status="error", error=error_msg, ended_at=datetime.utcnow())
            
            # Update Metrics
            metrics.tunnel_connection_errors_total.labels(error_type=f"exit_{returncode}").inc()
            if tdata["status"] == "connected":
                metrics.tunnel_active_count.dec()
            else:
                metrics.tunnel_operations_total.labels(operation="start", status="failure").inc()

            logger.error(
                f"Tunnel process terminated: {error_msg}", 
                extra={"tunnel_id": tunnel_id, "exit_code": returncode, "error": error_msg}
            )
            failed_tunnels_count += 1


async def start_tunnel(port: int, alias: Optional[str] = None) -> dict:
    """Spawns a cloudflared process to expose the given port using a unique tunnel_id."""
    logger.info(f"Initiating tunnel request for local port {port} (Alias: {alias or 'None'})")

    # Validate port range and reachability
    validation = validate_tunnel_request(port)
    if validation["status"] == "error":
        logger.warning(
            f"Validation failed for port {port}", 
            extra={"port": port, "error": validation['message']}
        )
        return {"status": "error", "message": validation["message"], "status_code": 400}

    # Check if a tunnel for this port already exists in memory
    for tid, tstate in active_tunnels.items():
        if tstate["port"] == port and tstate["process"].returncode is None:
            logger.info(
                f"Tunnel for port {port} is already running", 
                extra={"port": port, "tunnel_id": tid}
            )
            return {"status": "error", "message": f"Tunnel for port {port} already running!", "status_code": 409, "tunnel_id": tid}

    try:
        # Initialize session clock if this is the first tunnel
        global _session_start_time
        if not active_tunnels and _session_start_time is None:
            _session_start_time = asyncio.get_event_loop().time()

        tunnel_id = str(uuid.uuid4())
        cmd = ["cloudflared", "tunnel", "--url", f"http://localhost:{port}"]

        # Priority 1: User-defined path in .env
        if settings.CLOUDFLARED_PATH:
            cmd[0] = settings.CLOUDFLARED_PATH
        # Priority 2: Use shutil.which to find binary in PATH (Cross-platform)
        else:
            detected_path = shutil.which("cloudflared")
            if detected_path:
                cmd[0] = detected_path
            # Priority 3: Common macOS paths (legacy fallbacks)
            elif os.path.exists("/opt/homebrew/bin/cloudflared"):
                cmd[0] = "/opt/homebrew/bin/cloudflared"
            elif os.path.exists("/usr/local/bin/cloudflared"):
                cmd[0] = "/usr/local/bin/cloudflared"

        logger.info(f"Executing cloudflared command", extra={"command": ' '.join(cmd)})
        try:
            # Main Method: asyncio native subprocess
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            # Start background task to read output
            asyncio.create_task(_read_process_output(process, tunnel_id))
            is_async = True
        except NotImplementedError:
            logger.warning("NotImplementedError: Falling back to threaded subprocess.Popen for Windows compatibility.")
            # Fallback Method: subprocess.Popen in a thread
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT, # Merge stderr into stdout for fallback reader
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            )
            # Use a thread to read output since this loop doesn't support subprocess pipes
            threading.Thread(target=_sync_read_output, args=(process.stdout, tunnel_id), daemon=True).start()
            is_async = False
        except Exception as e:
            error_msg = str(e) or f"Unexpected error spawning process: {type(e).__name__}"
            logger.error(f"Error during subprocess creation: {error_msg}")
            return {"status": "error", "message": error_msg, "status_code": 500}

        active_tunnels[tunnel_id] = {
            "process": process,
            "port": port,
            "alias": alias,
            "url": None,
            "status": "starting",
            "error": None,
            "start_time": asyncio.get_event_loop().time(), # Legacy metrics usage
            "start_time_loop": asyncio.get_running_loop().time(), # For duration histogram
            "is_async_process": is_async,
            "logs": deque(maxlen=100)
        }

        # Persist to DB
        async with AsyncSessionLocal() as session:
            new_tunnel = Tunnel(
                id=tunnel_id,
                port=port,
                alias=alias,
                status="starting"
            )
            session.add(new_tunnel)
            await session.commit()

        logger.info(
            f"Spawned Cloudflare Tunnel process", 
            extra={"tunnel_id": tunnel_id, "port": port, "mode": 'Async' if is_async else 'Threaded Fallback'}
        )

        # Increment metrics
        global total_tunnels_created
        total_tunnels_created += 1

        # Wait briefly for the URL to be generated
        for _ in range(50):
            if tunnel_id in active_tunnels and active_tunnels[tunnel_id]["url"]:
                return {
                    "tunnel_id": tunnel_id,
                    "status": "starting"
                }
            
            # Check if process died
            if is_async:
                if process.returncode is not None:
                    break
            else:
                if process.poll() is not None:
                    break
            
            await asyncio.sleep(0.1)

        # Handle immediate failure
        exit_code = process.returncode if is_async else process.poll()
        if exit_code is not None:
            error_msg = get_cloudflared_error(exit_code)
            logger.error(
                f"Tunnel process failed immediately", 
                extra={"tunnel_id": tunnel_id, "exit_code": exit_code, "error": error_msg}
            )
            if tunnel_id in active_tunnels:
                active_tunnels[tunnel_id]["status"] = "error"
                active_tunnels[tunnel_id]["error"] = error_msg
                # Sync to DB
                await _update_tunnel_in_db(tunnel_id, status="error", error=error_msg, ended_at=datetime.utcnow())
            total_tunnels_created -= 1 # Revert count if it failed instantly
            failed_tunnels_count += 1
            return {"status": "error", "message": error_msg, "status_code": 500}

        return {
            "tunnel_id": tunnel_id,
            "status": "starting"
        }

    except Exception as e:
        error_msg = str(e) or f"Unexpected internal error: {type(e).__name__}"
        logger.exception(f"Unexpected error starting tunnel for port {port}: {error_msg}")
        return {"status": "error", "message": error_msg, "status_code": 500}


def get_status(tunnel_id: str) -> dict:
    """Returns the tunnel status for a specific tunnel_id."""
    global failed_tunnels_count
    if tunnel_id not in active_tunnels:
        return {"status": "error", "message": "Tunnel ID not found", "status_code": 404, "active": False}

    tdata = active_tunnels[tunnel_id]
    process = tdata["process"]

    is_async = tdata.get("is_async_process", True)
    exit_code = process.returncode if is_async else process.poll()

    if exit_code is not None:
        if tdata.get("status") != "error":
            tdata["status"] = "error"
            tdata["error"] = get_cloudflared_error(exit_code)
            failed_tunnels_count += 1

    start_time = tdata.get("start_time")
    tunnel_uptime = 0
    if start_time:
        tunnel_uptime = int(asyncio.get_event_loop().time() - start_time)

    # Determine final status for API (connected -> warning if local service is down)
    current_status = tdata["status"]
    is_local_down = tdata.get("local_service_down", False)
    
    if current_status == "connected" and is_local_down:
        current_status = "warning"

    return {
        "active": True,
        "tunnel_id": tunnel_id,
        "url": tdata["url"],
        "port": tdata["port"],
        "alias": tdata.get("alias"),
        "status": current_status,
        "is_service_reachable": not is_local_down,
        "error": tdata.get("error"),
        "uptime_seconds": tunnel_uptime
    }


def list_active_tunnels() -> list:
    """Returns a list of all currently active tunnels."""
    results = []
    # Use a list of keys to avoid modification errors during iteration
    for tunnel_id in list(active_tunnels.keys()):
        status = get_status(tunnel_id)
        if status.get("active"):
            results.append(status)
    return results


async def stop_tunnel(tunnel_id: str) -> dict:
    """Gracefully stops a specific cloudflared process."""
    if tunnel_id not in active_tunnels:
        logger.warning(f"Stop request failed: Tunnel ID not found", extra={"tunnel_id": tunnel_id})
        return {"status": "error", "message": "Tunnel ID not found", "status_code": 404}

    logger.info(f"Stopping tunnel", extra={"tunnel_id": tunnel_id})
    tdata = active_tunnels[tunnel_id]
    process = tdata["process"]

    is_async = tdata.get("is_async_process", True)

    # Send termination signal
    if os.name == 'nt':
        process.terminate()
    else:
        if is_async:
            process.send_signal(signal.SIGTERM)
        else:
            process.terminate()

    # Wait for exit
    try:
        if is_async:
            await asyncio.wait_for(process.wait(), timeout=5)
        else:
            # For sync process, poll with sleep to avoid blocking
            for _ in range(50):
                if process.poll() is not None:
                    break
                await asyncio.sleep(0.1)
            if process.poll() is None:
                process.kill()
    except asyncio.TimeoutError:
        logger.warning(f"Tunnel {tunnel_id} did not stop gracefully, killing it.")
        process.kill()

        if tdata["status"] == "connected":
            metrics.tunnel_active_count.dec()
        
        del active_tunnels[tunnel_id]
        # Sync to DB
        await _update_tunnel_in_db(tunnel_id, status="stopped", ended_at=datetime.utcnow())
        
        # Update Metrics
        metrics.tunnel_operations_total.labels(operation="stop", status="success").inc()
        
    # Reset session clock if this was the last tunnel
    if not active_tunnels:
        global _session_start_time
        _session_start_time = None

    logger.info(f"Tunnel stopped successfully", extra={"tunnel_id": tunnel_id})
    return {"success": True, "message": f"Tunnel {tunnel_id} stopped"}


async def cleanup():
    """Cleanup handler to terminate ALL active tunnels on shutdown."""
    ids = list(active_tunnels.keys())
    if ids:
        logger.info(f"Cleaning up {len(ids)} active tunnels during shutdown...")
    for tunnel_id in ids:
        await stop_tunnel(tunnel_id)


def check_port_open(port: int) -> bool:
    """Checks if a local port is open (TCP)."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex(('127.0.0.1', port)) == 0


async def monitor_service_health():
    """Background task to periodically check local service health for active tunnels."""
    logger.info("Service health monitor started")
    while True:
        try:
            # Create a copy of IDs to avoid concurrent modification errors
            for tid in list(active_tunnels.keys()):
                tdata = active_tunnels.get(tid)
                if not tdata or tdata["status"] == "error":
                    continue
                
                port = tdata["port"]
                is_open = check_port_open(port)
                
                # Update the health state
                tdata["local_service_down"] = not is_open
                
            # Update Metrics
            down_count = sum(1 for t in active_tunnels.values() if t.get("local_service_down"))
            metrics.tunnel_local_service_down_count.set(down_count)
            metrics.update_uptime()
                
            await asyncio.sleep(5) # Check every 5 seconds
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Error in health monitor: {e}")
            await asyncio.sleep(5)


async def _update_tunnel_in_db(tunnel_id: str, **kwargs):
    """Helper to update a tunnel record in the database."""
    try:
        async with AsyncSessionLocal() as session:
            stmt = update(Tunnel).where(Tunnel.id == tunnel_id).values(**kwargs)
            await session.execute(stmt)
            await session.commit()
    except Exception as e:
        logger.error(f"Database update failed for tunnel {tunnel_id}: {e}")


async def cleanup_stale_tunnels():
    """Marks any non-stopped tunnels from previous sessions as 'stale'."""
    try:
        async with AsyncSessionLocal() as session:
            # Mark all tunnels that don't have 'stopped' or 'error' status as 'stale'
            # (Assuming any tunnel from a previous run is now stale)
            stmt = update(Tunnel).where(
                Tunnel.status.in_(["starting", "connected", "warning"])
            ).values(status="stale", ended_at=datetime.utcnow())
            await session.execute(stmt)
            await session.commit()
            logger.info("Marked stale tunnels from previous session.")
    except Exception as e:
        logger.error(f"Error during stale tunnel cleanup: {e}")


async def get_historical_metrics():
    """Returns historical metrics from the database."""
    try:
        async with AsyncSessionLocal() as session:
            # Total tunnels created (all time)
            total_stmt = select(Tunnel)
            total_res = await session.execute(total_stmt)
            total_count = len(total_res.all())

            # Failed tunnels (status is 'error' or 'stale')
            failed_stmt = select(Tunnel).where(Tunnel.status.in_(["error", "stale"]))
            failed_res = await session.execute(failed_stmt)
            failed_count = len(failed_res.all())

            return {
                "total": total_count,
                "failed": failed_count
            }
    except Exception as e:
        logger.error(f"Error fetching historical metrics: {e}")
        return {"total": 0, "failed": 0}



