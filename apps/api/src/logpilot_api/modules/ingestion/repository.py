"""Repository for LogSource, IngestionRun, and LogEvent database operations.

Conforms to D05 and D06.
"""

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from logpilot_api.modules.ingestion.models import IngestionRun, LogEvent, LogSource
from logpilot_api.modules.ingestion.schemas import LogSourceCreate


class IngestionRepository:
    """Repository managing database persistence and queries for the ingestion domain."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_log_source(
        self, project_id: uuid.UUID, log_source_id: uuid.UUID
    ) -> LogSource | None:
        """Retrieve a specific log source scoped to its owning project (D05 § 10 / D06 § 7.4)."""
        stmt = (
            select(LogSource)
            .where(LogSource.id == log_source_id)
            .where(LogSource.project_id == project_id)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_log_source_by_name(
        self, project_id: uuid.UUID, name: str, environment: str
    ) -> LogSource | None:
        """Check uniqueness of log source within project and environment."""
        stmt = (
            select(LogSource)
            .where(LogSource.project_id == project_id)
            .where(LogSource.name == name)
            .where(LogSource.environment == environment)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_log_sources(self, project_id: uuid.UUID) -> Sequence[LogSource]:
        """List all log sources scoped strictly to a project."""
        stmt = (
            select(LogSource)
            .where(LogSource.project_id == project_id)
            .order_by(LogSource.created_at.desc())
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def create_log_source(
        self,
        project_id: uuid.UUID,
        data: LogSourceCreate,
        ingestion_key_hash: str | None = None,
    ) -> LogSource:
        """Register a new log source under a project."""
        source = LogSource(
            project_id=project_id,
            name=data.name,
            source_type=data.source_type,
            environment=data.environment,
            is_active=True,
            ingestion_key_hash=ingestion_key_hash,
        )
        self.session.add(source)
        await self.session.flush()
        return source

    async def create_ingestion_run(
        self, log_source_id: uuid.UUID, status: str = "STARTED"
    ) -> IngestionRun:
        """Create an ingestion run record tracking batch execution."""
        run = IngestionRun(
            log_source_id=log_source_id,
            status=status,
            events_processed=0,
            errors_count=0,
            started_at=datetime.now(UTC),
        )
        self.session.add(run)
        await self.session.flush()
        return run

    async def get_ingestion_run(
        self, project_id: uuid.UUID, ingestion_run_id: uuid.UUID
    ) -> IngestionRun | None:
        """Retrieve an ingestion run verifying project ownership (D05 § 10 / D06 § 7.4)."""
        stmt = (
            select(IngestionRun)
            .join(LogSource, IngestionRun.log_source_id == LogSource.id)
            .where(IngestionRun.id == ingestion_run_id)
            .where(LogSource.project_id == project_id)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def update_ingestion_run(
        self,
        run: IngestionRun,
        status: str,
        events_processed: int,
        errors_count: int,
    ) -> IngestionRun:
        """Update ingestion run status, metrics, and completion timestamp."""
        run.status = status
        run.events_processed = events_processed
        run.errors_count = errors_count
        run.completed_at = datetime.now(UTC)
        await self.session.flush()
        return run

    async def persist_events(
        self,
        project_id: uuid.UUID,
        log_source_id: uuid.UUID,
        events: list[LogEvent],
    ) -> int:
        """Persist normalized log events with deduplication check (D07 § 9.3)."""
        if not events:
            return 0

        # Query existing event hashes within the current batch to prevent duplication
        event_hashes = [e.event_hash for e in events]
        stmt = (
            select(LogEvent.event_hash)
            .where(LogEvent.project_id == project_id)
            .where(LogEvent.log_source_id == log_source_id)
            .where(LogEvent.event_hash.in_(event_hashes))
        )
        result = await self.session.execute(stmt)
        existing_hashes = set(result.scalars().all())

        new_events = [e for e in events if e.event_hash not in existing_hashes]
        if new_events:
            self.session.add_all(new_events)
            await self.session.flush()

        return len(new_events)

    async def get_events_by_source(self, log_source_id: uuid.UUID) -> Sequence[LogEvent]:
        """Retrieve persisted events for a log source."""
        stmt = (
            select(LogEvent)
            .where(LogEvent.log_source_id == log_source_id)
            .order_by(LogEvent.timestamp.asc())
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()
