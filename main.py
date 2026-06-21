import sys
import asyncio

if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

import time
import uuid
from fastapi import Request
from utils import context
from utils.logger import logger

from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI, Response
from fastapi.staticfiles import StaticFiles
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

from fastapi.middleware.cors import CORSMiddleware

from api.tunnel_routes import router as tunnel_router
from services import tunnel_service

# Resolve the frontend directory safely - it's a sibling of the project folder
FRONTEND_DIR = Path(__file__).parent.parent.parent / "Cloudflare_frontend"


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize the database and cleanup stale tunnels
    await tunnel_service.init_db()
    await tunnel_service.cleanup_stale_tunnels()
    
    # Start the service health monitor
    monitor_task = asyncio.create_task(tunnel_service.monitor_service_health())
    
    loop = asyncio.get_running_loop()
    print(f"DEBUG: Active Event Loop: {type(loop).__name__}")
    yield
    # Cleanup on exit
    monitor_task.cancel()
    await tunnel_service.cleanup()


app = FastAPI(lifespan=lifespan)

# Add CORS middleware to allow separate frontend to communicate
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For local development, allow all origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def add_correlation_id_and_log_request(request: Request, call_next):
    """Middleware to inject correlation IDs and log requests/responses."""
    # Try to get correlation ID from headers or generate a new one
    cid = request.headers.get("X-Correlation-ID", str(uuid.uuid4()))
    context.set_correlation_id(cid)
    
    start_time = time.time()
    
    # Redact sensitive headers for logging
    safe_headers = {k: v for k, v in request.headers.items() if k.lower() not in ["authorization", "api-token", "cookie"]}
    
    logger.info(
        f"Incoming Request: {request.method} {request.url.path}",
        extra={
            "method": request.method,
            "path": request.url.path,
            "client_ip": request.client.host if request.client else "unknown",
            "headers": safe_headers
        }
    )
    
    response = await call_next(request)
    
    duration = time.time() - start_time
    
    logger.info(
        f"Outgoing Response: {response.status_code} {request.method} {request.url.path}",
        extra={
            "status_code": response.status_code,
            "duration_ms": int(duration * 1000)
        }
    )
    
    # Inject cid back into the response header
    response.headers["X-Correlation-ID"] = cid
    return response

# Register API routes
app.include_router(tunnel_router)

@app.get("/metrics")
async def metrics():
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)

# Serve frontend static files
app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")


if __name__ == "__main__":
    import uvicorn
    from config import settings
    
    print(f"Starting Cloudflare Tunnel Manager on port {settings.APP_PORT}...")
    uvicorn.run(app, host="0.0.0.0", port=settings.APP_PORT)
