"""API authentication module."""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from mdpilot.config.settings import get_settings

security = HTTPBearer(auto_error=False)


async def verify_token(
    credentials: HTTPAuthorizationCredentials | None = Depends(security)
) -> str:
    """Verify API token.
    
    Args:
        credentials: HTTP Bearer credentials
        
    Returns:
        Token string if valid
        
    Raises:
        HTTPException: If token is invalid or missing
    """
    settings = get_settings()
    
    if settings.api_token is None:
        if credentials is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required but no token configured",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return credentials.credentials
    
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    expected_token = settings.api_token.get_secret_value()
    if credentials.credentials != expected_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return credentials.credentials


async def optional_verify_token(
    credentials: HTTPAuthorizationCredentials | None = Depends(security)
) -> str | None:
    """Optional token verification for endpoints that can work without auth.
    
    Args:
        credentials: HTTP Bearer credentials
        
    Returns:
        Token string if provided and valid, None if no token configured
        
    Raises:
        HTTPException: If token is provided but invalid
    """
    settings = get_settings()
    
    if settings.api_token is None:
        return None
    
    if credentials is None:
        return None
    
    expected_token = settings.api_token.get_secret_value()
    if credentials.credentials != expected_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return credentials.credentials
