"""Top-level router aggregating API module routes."""

from fastapi import APIRouter

from logpilot_api.api.v1.health import router as health_router

api_router = APIRouter()

# Mount health endpoints
api_router.include_router(health_router)
