from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from config import settings

security = HTTPBearer()

async def validate_api_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """
    Validates the Bearer token provided in the Authorization header.
    Returns the token if valid, otherwise raises a 401 Unauthorized error.
    """
    if credentials.credentials != settings.API_TOKEN:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API Token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return credentials.credentials
