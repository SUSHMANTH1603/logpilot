"""Pytest fixtures for unit and integration testing."""

from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from logpilot_api.core.config import Settings
from logpilot_api.db import session as db_session
from logpilot_api.db.base import Base
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


@pytest.fixture(autouse=True)
async def init_test_db(test_settings: Settings) -> AsyncGenerator[None, None]:
    """Ensure database schema is created in isolated in-memory database."""
    engine = create_async_engine(
        test_settings.database_url,
        echo=False,
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    from typing import Any

    from sqlalchemy import event

    @event.listens_for(engine.sync_engine, "connect")
    def _set_sqlite_pragma(dbapi_connection: Any, _connection_record: Any) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    db_session._engine = engine
    db_session._sessionmaker = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()
    db_session._engine = None
    db_session._sessionmaker = None


@pytest.fixture
async def client(test_settings: Settings) -> AsyncGenerator[AsyncClient, None]:
    """Provide an asynchronous HTTP client bound to the test application."""
    app = create_app(settings=test_settings)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac
