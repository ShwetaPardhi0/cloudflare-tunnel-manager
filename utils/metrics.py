import time
from prometheus_client import Counter, Gauge, Histogram, Summary, REGISTRY

# --- Tunnel Lifecycle Metrics ---

# track total operations (start, stop, etc.)
tunnel_operations_total = Counter(
    "tunnel_operations_total",
    "Total number of tunnel operations performed",
    ["operation", "status"] # operation: start, stop, retry; status: success, failure
)

# track currently active tunnels
tunnel_active_count = Gauge(
    "tunnel_active_count",
    "Current number of connected Cloudflare tunnels"
)

# track connection errors by type
tunnel_connection_errors_total = Counter(
    "tunnel_connection_errors_total",
    "Total number of tunnel connection errors",
    ["error_type"]
)

# measure how long it takes to establish a tunnel connection
tunnel_start_duration_seconds = Histogram(
    "tunnel_start_duration_seconds",
    "Duration in seconds to establish a tunnel connection (until public URL is obtained)",
    buckets=(1, 2, 5, 10, 15, 20, 30, 45, 60)
)

# --- Runtime Metrics ---

# Application uptime
app_start_time = time.time()
app_uptime_seconds = Gauge(
    "app_uptime_seconds",
    "Application uptime in seconds"
)

def update_uptime():
    """Helper to update the uptime metric."""
    app_uptime_seconds.set(time.time() - app_start_time)

# Custom metric to track local service reachability
tunnel_local_service_down_count = Gauge(
    "tunnel_local_service_down_count",
    "Number of tunnels where the local service is currently unreachable"
)
