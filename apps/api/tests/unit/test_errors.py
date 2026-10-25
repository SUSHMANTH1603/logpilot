"""Unit tests for global error handling and D06 error envelope conventions."""

import pytest
from httpx import AsyncClient

from logpilot_api.core.errors import (
    ConflictError,
    ForbiddenError,
    NotFoundError,
    ServiceUnavailableError,
    UnauthorizedError,
    ValidationError,
)
from logpilot_api.main import create_app


def test_app_error_hierarchy() -> None:
    """Verify custom exception inheritance and status code mapping."""
    err404 = NotFoundError("Item missing")
    assert err404.status_code == 404
    assert err404.code == "RESOURCE_NOT_FOUND"

    err422 = ValidationError("Schema mismatch", details=[{"field": "name", "issue": "required"}])
    assert err422.status_code == 422
    assert len(err422.details) == 1

    err401 = UnauthorizedError()
    assert err401.status_code == 401

    err403 = ForbiddenError()
    assert err403.status_code == 403

    err409 = ConflictError()
    assert err409.status_code == 409

    err503 = ServiceUnavailableError()
    assert err503.status_code == 503


@pytest.mark.asyncio
async def test_error_envelope_structure() -> None:
    """Verify FastAPI error response format matches D06 § 4.1 specification."""
    app = create_app()

    @app.get("/test-error")
    async def trigger_error() -> None:
        raise NotFoundError("Project not found.", code="PROJECT_NOT_FOUND")

    from httpx import ASGITransport

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        res = await client.get("/test-error")
        assert res.status_code == 404
        data = res.json()
        assert "error" in data
        err = data["error"]
        assert err["code"] == "PROJECT_NOT_FOUND"
        assert err["message"] == "Project not found."
        assert "request_id" in err
        assert err["request_id"].startswith("req_")
        assert isinstance(err["details"], list)
