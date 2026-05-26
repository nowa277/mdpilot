"""Health check router for database and system status."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import text

from mdpilot.database import get_engine

router = APIRouter(prefix="/api/v1/health", tags=["health"])


class DatabaseHealth(BaseModel):
    """Database health check response."""

    status: str
    connected: bool
    pool_size: int
    checked_in: int
    checked_out: int
    overflow: int
    message: str | None = None


class HealthResponse(BaseModel):
    """Overall health check response."""

    status: str
    database: DatabaseHealth


@router.get("/db", response_model=DatabaseHealth)
async def check_database_health() -> DatabaseHealth:
    """Check database connectivity and pool statistics.

    Returns:
        Database health information including connection status and pool stats.

    Raises:
        HTTPException: If database connection fails.
    """
    try:
        engine = get_engine()

        # Test connection with a simple query
        async with engine.connect() as conn:
            result = await conn.execute(text("SELECT 1"))
            result.scalar()

        # Get pool statistics
        pool = engine.pool
        pool_size = pool.size()
        checked_in = pool.checkedin()
        checked_out = pool.checkedout()
        overflow = pool.overflow()

        return DatabaseHealth(
            status="healthy",
            connected=True,
            pool_size=pool_size,
            checked_in=checked_in,
            checked_out=checked_out,
            overflow=overflow,
            message="Database connection successful",
        )

    except Exception as e:
        return DatabaseHealth(
            status="unhealthy",
            connected=False,
            pool_size=0,
            checked_in=0,
            checked_out=0,
            overflow=0,
            message=f"Database connection failed: {str(e)}",
        )


@router.get("", response_model=HealthResponse)
async def check_health() -> HealthResponse:
    """Check overall system health including database.

    Returns:
        Overall health status with database information.
    """
    db_health = await check_database_health()

    overall_status = "healthy" if db_health.status == "healthy" else "degraded"

    return HealthResponse(
        status=overall_status,
        database=db_health,
    )
