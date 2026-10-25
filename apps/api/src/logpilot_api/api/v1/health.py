"""Health, liveness, and readiness endpoints conforming to D06 § 7.1."""

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Response, status
from pydantic import BaseModel, Field

from logpilot_api import __version__
from logpilot_api.db.session import check_database_connection

router = APIRouter(tags=["Health & Meta"])


class HealthResponse(BaseModel):
    """Schema for GET /api/v1/health conforming to D06 § 7.1."""

    status: str = Field(..., description="Overall service status: HEALTHY or UNHEALTHY")
    version: str = Field(..., description="Application semantic version")
    timestamp: str = Field(..., description="ISO 8601 UTC timestamp")


class ReadinessResponse(BaseModel):
    """Detailed dependency readiness state."""

    status: str
    checks: dict[str, str]


@router.get(
    "/api/v1/health",
    response_model=HealthResponse,
    status_code=status.HTTP_200_OK,
    summary="Service Health & Liveness Probe",
    description="Public liveness check conforming to D06 § 7.1 without credential leakage.",
)
async def get_service_health() -> HealthResponse:
    """Return application health state."""
    return HealthResponse(
        status="HEALTHY",
        version=__version__,
        timestamp=datetime.now(UTC).isoformat(),
    )


@router.get(
    "/health",
    status_code=status.HTTP_200_OK,
    summary="Application Liveness Probe",
    description="Lightweight liveness probe for orchestrators and load balancers.",
)
async def liveness_probe() -> dict[str, Any]:
    """Lightweight process liveness probe."""
    return {
        "status": "UP",
        "timestamp": datetime.now(UTC).isoformat(),
    }


@router.get(
    "/ready",
    response_model=ReadinessResponse,
    summary="Dependency Readiness Probe",
    description="Verifies operational connectivity to critical backing infrastructure.",
)
async def readiness_probe(response: Response) -> ReadinessResponse:
    """Readiness probe checking storage and backing service connectivity."""
    db_ok = await check_database_connection()

    checks = {
        "database": "UP" if db_ok else "DOWN",
    }

    is_ready = db_ok
    if not is_ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return ReadinessResponse(
        status="READY" if is_ready else "NOT_READY",
        checks=checks,
    )
