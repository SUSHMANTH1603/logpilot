"""Pytest fixtures for unit and integration testing."""

from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient

from logpilot_api.core.config import Settings
from logpilot_api.main import create_app


@pytest.fixture
def test_settings() -> Settings:
    """Provide isolated testing settings with SQLite in-memory database."""
    return Settings(
        app_env="testing",
        debug=True,
        database_url="sqlite+aiosqlite:///:memory:",
        database_sync_url="sqlite:///:memory:",
        redis_url="redis://127.0.0.1:6379/15",
        qdrant_url="http://127.0.0.1:6333",
        secret_key="test-secret-key-for-unit-testing-min-32-chars",
    )


@pytest.fixture
async def client(test_settings: Settings) -> AsyncGenerator[AsyncClient, None]:
    """Provide an asynchronous HTTP client bound to the test application."""
    app = create_app(settings=test_settings)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac
