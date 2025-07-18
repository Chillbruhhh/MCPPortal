"""
FastAPI Dependencies.

This module defines dependency injection functions for the FastAPI application,
including authentication, rate limiting, and gateway access.
"""

from typing import Optional

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from ..config.settings import Settings, get_settings
from ..core.gateway import MCPGateway

# Global gateway instance
_gateway: Optional[MCPGateway] = None

# Security scheme
security = HTTPBearer(auto_error=False)


def get_gateway() -> MCPGateway:
    """
    Get the global gateway instance.

    Returns:
        MCPGateway instance

    Raises:
        HTTPException: If gateway is not initialized
    """
    global _gateway
    if _gateway is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Gateway not initialized"
        )
    return _gateway


def set_gateway(gateway: MCPGateway):
    """
    Set the global gateway instance.

    Args:
        gateway: MCPGateway instance to set
    """
    global _gateway
    _gateway = gateway


async def verify_api_key(
    settings: Settings = Depends(get_settings),
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    x_api_key: Optional[str] = Header(None)
) -> bool:
    """
    Verify API key if authentication is enabled.

    Args:
        settings: Application settings
        credentials: HTTP Bearer credentials
        x_api_key: API key from header

    Returns:
        True if authenticated or authentication disabled

    Raises:
        HTTPException: If authentication fails
    """
    # If no API key is configured, skip authentication
    if not settings.api_key:
        return True

    # Check Bearer token
    if credentials and credentials.credentials == settings.api_key:
        return True

    # Check API key header
    if x_api_key == settings.api_key:
        return True

    # Authentication failed
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or missing API key",
        headers={"WWW-Authenticate": "Bearer"}
    )


async def get_authenticated_gateway(
    authenticated: bool = Depends(verify_api_key),
    gateway: MCPGateway = Depends(get_gateway)
) -> MCPGateway:
    """
    Get authenticated gateway instance.

    Args:
        authenticated: Authentication verification result
        gateway: Gateway instance

    Returns:
        MCPGateway instance
    """
    return gateway


# Rate limiting (simple in-memory implementation)
from collections import defaultdict
from time import time

_request_counts = defaultdict(list)
RATE_LIMIT_REQUESTS = 100
RATE_LIMIT_WINDOW = 60  # seconds


async def rate_limit_check(
    x_forwarded_for: Optional[str] = Header(None),
    x_real_ip: Optional[str] = Header(None)
) -> bool:
    """
    Simple rate limiting check.

    Args:
        x_forwarded_for: Forwarded IP header
        x_real_ip: Real IP header

    Returns:
        True if request allowed

    Raises:
        HTTPException: If rate limit exceeded
    """
    # Get client IP
    client_ip = x_real_ip or x_forwarded_for or "unknown"

    current_time = time()

    # Clean old requests
    _request_counts[client_ip] = [
        req_time for req_time in _request_counts[client_ip]
        if current_time - req_time < RATE_LIMIT_WINDOW
    ]

    # Check rate limit
    if len(_request_counts[client_ip]) >= RATE_LIMIT_REQUESTS:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded: {RATE_LIMIT_REQUESTS} requests per {RATE_LIMIT_WINDOW} seconds"
        )

    # Record this request
    _request_counts[client_ip].append(current_time)

    return True


async def get_rate_limited_gateway(
    rate_limited: bool = Depends(rate_limit_check),
    gateway: MCPGateway = Depends(get_authenticated_gateway)
) -> MCPGateway:
    """
    Get rate-limited and authenticated gateway instance.

    Args:
        rate_limited: Rate limiting check result
        gateway: Authenticated gateway instance

    Returns:
        MCPGateway instance
    """
    return gateway
