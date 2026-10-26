"""Repository for persisting anomaly signals and retrieving historical windows."""

import uuid
from collections.abc import Sequence
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from logpilot_api.modules.analysis.models import AnomalySignal
from logpilot_api.modules.ingestion.models import LogEvent


class AnalysisRepository:
    """Repository handling database access for anomaly signals and event series."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_signal(self, signal: AnomalySignal) -> AnomalySignal:
        """Persist a new AnomalySignal record."""
        self.session.add(signal)
        await self.session.flush()
        return signal

    async def get_log_events_in_range(
        self,
        project_id: uuid.UUID,
        log_source_id: uuid.UUID,
        start_time: datetime,
        end_time: datetime,
    ) -> Sequence[LogEvent]:
        """Fetch all log events for a given source within a time window [start_time, end_time]."""
        stmt = (
            sa.select(LogEvent)
            .where(
                LogEvent.project_id == project_id,
                LogEvent.log_source_id == log_source_id,
                LogEvent.timestamp >= start_time,
                LogEvent.timestamp <= end_time,
            )
            .order_by(LogEvent.timestamp.asc())
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_signals_in_range(
        self,
        project_id: uuid.UUID,
        start_time: datetime,
        end_time: datetime,
    ) -> Sequence[AnomalySignal]:
        """Fetch all anomaly signals in a project within a time window."""
        stmt = (
            sa.select(AnomalySignal)
            .where(
                AnomalySignal.project_id == project_id,
                AnomalySignal.detected_at >= start_time,
                AnomalySignal.detected_at <= end_time,
            )
            .order_by(AnomalySignal.detected_at.asc())
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()
