"""
API Middleware Configuration.

This module provides middleware configuration for the MCP Gateway API,
including CORS, logging, and security headers.
"""

import logging
import time
from typing import Callable

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

logger = logging.getLogger(__name__)


def setup_middleware(app: FastAPI):
    """
    Setup middleware for the FastAPI application.

    Args:
        app: FastAPI application instance
    """
    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Request logging middleware
    @app.middleware("http")
    async def log_requests(request: Request, call_next: Callable):
        """Log HTTP requests and responses."""
        start_time = time.time()
        
        # Log request
        logger.info(f"Request: {request.method} {request.url.path} from {request.client.host} ({request.headers.get('user-agent', 'Unknown')})")
        
        # Process request
        response = await call_next(request)
        
        # Calculate response time
        process_time = time.time() - start_time
        
        # Log response
        logger.info(f"Response: {response.status_code} in {process_time:.3f}s")
        
        return response

    # Security headers middleware
    @app.middleware("http")
    async def add_security_headers(request: Request, call_next: Callable):
        """Add security headers to responses."""
        response = await call_next(request)
        
        # Add CSP header that allows SVG data URIs
        csp_policy = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; "
            "font-src 'self' data:; "
            "connect-src 'self'"
        )
        response.headers["Content-Security-Policy"] = csp_policy
        
        # Add other security headers
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        
        return response
