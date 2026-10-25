"""FastAPI application factory, lifespan management, and middleware setup."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from logpilot_api import __version__
from logpilot_api.api.router import api_router
from logpilot_api.core.config import Settings, get_settings
from logpilot_api.core.errors import register_error_handlers
from logpilot_api.core.logging import configure_logging, correlation_id_ctx
from logpilot_api.core.security import generate_request_id


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Middleware attaching a unique request ID to each request and response."""

    async def dispatch(self, request: Request, call_next) -> Response:
        req_id = request.headers.get("X-Request-ID") or generate_request_id()
        request.state.request_id = req_id
        token = correlation_id_ctx.set(req_id)

        try:
            response: Response = await call_next(request)
            response.headers["X-Request-ID"] = req_id
            return response
        finally:
            correlation_id_ctx.reset(token)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan context managing startup and shutdown tasks."""
    settings = getattr(app.state, "settings", get_settings())
    configure_logging(log_level=settings.log_level)
    yield
    # Cleanup on shutdown (e.g. dispose database engine if initialized)
    from logpilot_api.db import session as db_session

    if db_session._engine is not None:
        await db_session._engine.dispose()


def create_app(settings: Settings | None = None) -> FastAPI:
    """Application factory constructing the FastAPI backend modular monolith."""
    if settings is None:
        settings = get_settings()

    app = FastAPI(
        title="LogPilot API",
        description="Intelligent Observability and Root Cause Analysis Platform Backend",
        version=__version__,
        docs_url="/docs" if not settings.is_production else None,
        redoc_url="/redoc" if not settings.is_production else None,
        openapi_url="/openapi.json" if not settings.is_production else None,
        lifespan=lifespan,
    )

    app.state.settings = settings

    # Security & Correlation Middleware
    app.add_middleware(RequestIDMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register standardized error envelopes (D06 § 4.1)
    register_error_handlers(app)

    # Mount routes
    app.include_router(api_router)

    return app


# Default application instance for ASGI servers (e.g. uvicorn logpilot_api.main:app)
app = create_app()
