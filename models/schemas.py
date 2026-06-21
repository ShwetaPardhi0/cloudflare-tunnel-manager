from typing import Optional
from pydantic import BaseModel


class TunnelRequest(BaseModel):
    """Schema for requesting a new Cloudflare tunnel."""
    port: int
    alias: Optional[str] = None
