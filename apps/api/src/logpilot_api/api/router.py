"""Top-level router aggregating API module routes."""

from fastapi import APIRouter

from logpilot_api.api.v1.health import router as health_router
from logpilot_api.modules.identity.router import router as identity_router
from logpilot_api.modules.incidents.router import router as incidents_router
from logpilot_api.modules.ingestion.router import router as ingestion_router
from logpilot_api.modules.projects.router import router as projects_router

api_router = APIRouter()

# Mount health endpoints
api_router.include_router(health_router)

# Mount domain module endpoints
api_router.include_router(identity_router)
api_router.include_router(projects_router)
api_router.include_router(ingestion_router)
api_router.include_router(incidents_router)
