import time
from collections import defaultdict
from typing import Dict, List

# In-memory storage for request timestamps per user IP
# Format: { ip_address: [timestamp1, timestamp2, ...] }
_request_history: Dict[str, List[float]] = defaultdict(list)

# Configuration: max 5 requests per 60 seconds
RATE_LIMIT_COUNT = 5
RATE_LIMIT_WINDOW = 60

def is_rate_limited(user_ip: str) -> bool:
    """
    Checks if a user has exceeded the rate limit.
    Uses a sliding window approach.
    
    Returns:
        True if the user should be rate limited, False otherwise.
    """
    now = time.time()
    
    # Clean up old timestamps for this IP
    _request_history[user_ip] = [
        ts for ts in _request_history[user_ip] 
        if now - ts < RATE_LIMIT_WINDOW
    ]
    
    # Check if limit exceeded
    if len(_request_history[user_ip]) >= RATE_LIMIT_COUNT:
        return True
    
    # Record current request
    _request_history[user_ip].append(now)
    return False
