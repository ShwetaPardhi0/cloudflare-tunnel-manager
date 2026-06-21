from contextvars import ContextVar
from typing import Optional
import uuid

# Context variable to store the correlation ID for the current request context
_correlation_id_ctx_var: ContextVar[Optional[str]] = ContextVar("correlation_id", default=None)

def set_correlation_id(id_val: str) -> None:
    """Sets the correlation ID for the current context."""
    _correlation_id_ctx_var.set(id_val)

def get_correlation_id() -> Optional[str]:
    """Retrieves the correlation ID for the current context."""
    return _correlation_id_ctx_var.get()

def reset_correlation_id() -> None:
    """Resets the correlation ID to None."""
    _correlation_id_ctx_var.set(None)

def ensure_correlation_id() -> str:
    """Retrieves the current correlation ID or generates a new one if missing."""
    curr = get_correlation_id()
    if not curr:
        curr = str(uuid.uuid4())
        set_correlation_id(curr)
    return curr
