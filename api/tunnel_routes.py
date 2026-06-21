import asyncio
from fastapi import APIRouter, Request, Depends
from fastapi.responses import JSONResponse

from models.schemas import TunnelRequest
from services import tunnel_service
from utils.rate_limiter import is_rate_limited
from utils.auth import validate_api_token

router = APIRouter(prefix="/api")


@router.post("/tunnel", dependencies=[Depends(validate_api_token)])
async def start_tunnel(req: TunnelRequest, request: Request):
    """Start a new Cloudflare tunnel for the given port. Returns a unique tunnel_id."""
    client_ip = request.client.host
    
    # Check rate limit (max 5 per minute)
    if is_rate_limited(client_ip):
        return JSONResponse(
            status_code=429,
            content={"status": "error", "message": "Too many requests"}
        )

    result = await tunnel_service.start_tunnel(req.port, req.alias)

    if result.get("status") == "error":
        return JSONResponse(
            status_code=result.get("status_code", 500),
            content={"status": "error", "message": result.get("message")}
        )

    return result


@router.get("/tunnels")
async def list_tunnels():
    """List all active tunnels."""
    return tunnel_service.list_active_tunnels()


@router.get("/status/{tunnel_id}")
async def get_status(tunnel_id: str):
    """Check the status of a specific tunnel using its tunnel_id."""
    result = tunnel_service.get_status(tunnel_id)
    if result.get("status") == "error":
        return JSONResponse(
            status_code=result.get("status_code", 404),
            content={"status": "error", "message": result.get("message")}
        )
    return result


@router.delete("/tunnel/{tunnel_id}", dependencies=[Depends(validate_api_token)])
async def stop_tunnel(tunnel_id: str):
    """Stop a specific tunnel using its tunnel_id."""
    result = await tunnel_service.stop_tunnel(tunnel_id)
    if result.get("status") == "error":
        return JSONResponse(
            status_code=result.get("status_code", 404),
            content={"status": "error", "message": result.get("message")}
        )
    return result


@router.get("/tunnel/{tunnel_id}/logs", dependencies=[Depends(validate_api_token)])
async def get_tunnel_logs(tunnel_id: str):
    """Retrieve the last 100 log lines for a specific tunnel."""
    if tunnel_id not in tunnel_service.active_tunnels:
        return JSONResponse(
            status_code=404,
            content={"status": "error", "message": "Tunnel ID not found"}
        )
    
    logs = list(tunnel_service.active_tunnels[tunnel_id]["logs"])
    return {"status": "ok", "logs": logs}


@router.get("/health")
async def health_check():
    """Minimal health check endpoint returning system status and metrics."""
    now = asyncio.get_event_loop().time()
    start_time = tunnel_service.get_start_time()
    uptime = int(now - start_time) if start_time > 0 else 0
    
    active_count = len(tunnel_service.list_active_tunnels())
    
    # Get historical metrics from DB
    hist_metrics = await tunnel_service.get_historical_metrics()
    total = hist_metrics["total"]
    failed = hist_metrics["failed"]
    success_rate = round((total - failed) / total, 2) if total > 0 else 0.0

    return {
        "status": "ok",
        "uptime_seconds": uptime,
        "active_tunnels": active_count,
        "total_tunnels_created": total,
        "failed_tunnels_count": failed,
        "success_rate": success_rate
    }

