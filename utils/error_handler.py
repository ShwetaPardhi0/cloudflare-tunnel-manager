import socket

def is_service_listening(port: int) -> bool:
    """Checks if a local service is listening on the given port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(1.0)
        return s.connect_ex(('localhost', port)) == 0

def validate_tunnel_request(port: int) -> dict:
    """
    Validates the port range and ensures a local service is reachable.
    Returns: {"status": "success"} or {"status": "error", "message": "..."}
    """
    if not (1 <= port <= 65535):
        return {
            "status": "error", 
            "message": f"Invalid port: {port}. Port must be between 1 and 65535."
        }
    
    if not is_service_listening(port):
        return {
            "status": "error", 
            "message": f"No service found listening on port {port}. Please start your local server first."
        }
    
    return {"status": "success"}

def get_cloudflared_error(returncode: int) -> str:
    """Maps cloudflared exit codes to human-readable error messages."""
    error_map = {
        1: "General cloudflared error. Check binary permissions or installation.",
        64: "Invalid command line arguments.",
        65: "Configuration error.",
        69: "Service unavailable.",
        78: "Tunnel already exists or configuration overlap."
    }
    return error_map.get(returncode, f"cloudflared process exited with code {returncode}")
