"""Structured logging middleware for FastAPI."""

from __future__ import annotations

import time

import structlog
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

logger = structlog.get_logger()


class LoggingMiddleware(BaseHTTPMiddleware):
    """Middleware that logs all HTTP requests with structured data.
    
    Logs request start, completion, and errors with timing information.
    """

    async def dispatch(self, request: Request, call_next):
        """Process request and log timing/status information."""
        start_time = time.time()
        
        logger.info(
            "request_start",
            method=request.method,
            path=request.url.path,
            client=request.client.host if request.client else None,
        )
        
        try:
            response = await call_next(request)
            duration = time.time() - start_time
            
            logger.info(
                "request_complete",
                method=request.method,
                path=request.url.path,
                status_code=response.status_code,
                duration_ms=int(duration * 1000),
            )
            
            return response
        except Exception as exc:
            duration = time.time() - start_time
            logger.error(
                "request_error",
                method=request.method,
                path=request.url.path,
                error=str(exc),
                error_type=type(exc).__name__,
                duration_ms=int(duration * 1000),
            )
            raise
