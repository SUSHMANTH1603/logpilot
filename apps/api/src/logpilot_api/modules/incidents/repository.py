"""Repository for incident persistence, atomic numbering, and event linkage."""

import re
import uuid
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from logpilot_api.modules.incidents.models import Incident, IncidentEvent, IncidentState
from logpilot_api.modules.projects.models import Project


class IncidentRepository:
    """Repository handling database operations for incidents and incident events."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def allocate_incident_number(self, project_id: uuid.UUID) -> str:
        """Atomically generate the next project-scoped incident number INC-YYYY-XXXX.

        Acquires a row-level lock on the parent project row using SELECT ... FOR UPDATE
        to serialize concurrent incident allocations for the same project.
        """
        # 1. Lock project row
        lock_stmt = sa.select(Project).where(Project.id == project_id).with_for_update()
        await self.session.execute(lock_stmt)

        # 2. Find highest existing incident number for current year
        current_year = datetime.now(UTC).year
        prefix = f"INC-{current_year}-"

        stmt = (
            sa.select(Incident.incident_number)
            .where(
                Incident.project_id == project_id,
                Incident.incident_number.like(f"{prefix}%"),
            )
            .order_by(Incident.incident_number.desc())
            .limit(1)
        )
        result = await self.session.execute(stmt)
        latest_num = result.scalar_one_or_none()

        next_seq = 1
        if latest_num:
            match = re.search(r"INC-\d{4}-(\d+)", latest_num)
            if match:
                next_seq = int(match.group(1)) + 1

        return f"INC-{current_year}-{next_seq:04d}"

    async def get_active_incident_in_correlation_window(
        self,
        project_id: uuid.UUID,
        window_start: datetime,
        correlation_window_seconds: int,
    ) -> Incident | None:
        """Find an active incident within the correlation threshold window."""
        cutoff = window_start - timedelta(seconds=correlation_window_seconds)
        stmt = (
            sa.select(Incident)
            .where(
                Incident.project_id == project_id,
                Incident.state.in_(
                    [IncidentState.DETECTED.value, IncidentState.INVESTIGATING.value]
                ),
                Incident.window_end >= cutoff,
            )
            .order_by(Incident.window_end.desc())
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def create_incident(self, incident: Incident) -> Incident:
        """Persist a newly created incident."""
        self.session.add(incident)
        await self.session.flush()
        return incident

    async def get_incident(
        self,
        project_id: uuid.UUID,
        incident_id: uuid.UUID,
    ) -> Incident | None:
        """Retrieve an incident strictly scoped to a project."""
        stmt = sa.select(Incident).where(
            Incident.id == incident_id,
            Incident.project_id == project_id,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_incidents(
        self,
        project_id: uuid.UUID,
        state: str | None = None,
        severity: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[Sequence[Incident], int]:
        """List incidents with filtering and pagination for a project."""
        base_query = sa.select(Incident).where(Incident.project_id == project_id)

        if state:
            base_query = base_query.where(Incident.state == state)
        if severity:
            base_query = base_query.where(Incident.severity == severity)

        # Count total
        count_stmt = sa.select(sa.func.count()).select_from(base_query.subquery())
        total = (await self.session.execute(count_stmt)).scalar_one()

        # Fetch page
        paged_stmt = base_query.order_by(Incident.created_at.desc()).limit(limit).offset(offset)
        result = await self.session.execute(paged_stmt)
        return result.scalars().all(), total

    async def get_linked_log_event_ids(
        self,
        incident_id: uuid.UUID,
    ) -> set[uuid.UUID]:
        """Fetch all log_event_ids already linked to a specific incident."""
        stmt = sa.select(IncidentEvent.log_event_id).where(
            IncidentEvent.incident_id == incident_id,
        )
        result = await self.session.execute(stmt)
        return set(result.scalars().all())

    async def link_incident_event(
        self,
        incident_event: IncidentEvent,
    ) -> IncidentEvent:
        """Link a log event to an incident."""
        self.session.add(incident_event)
        await self.session.flush()
        return incident_event

    async def list_incident_events(
        self,
        project_id: uuid.UUID,
        incident_id: uuid.UUID,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[Sequence[IncidentEvent], int]:
        """List events linked to an incident."""
        base_query = sa.select(IncidentEvent).where(
            IncidentEvent.incident_id == incident_id,
            IncidentEvent.project_id == project_id,
        )

        count_stmt = sa.select(sa.func.count()).select_from(base_query.subquery())
        total = (await self.session.execute(count_stmt)).scalar_one()

        paged_stmt = base_query.order_by(IncidentEvent.linked_at.asc()).limit(limit).offset(offset)
        result = await self.session.execute(paged_stmt)
        return result.scalars().all(), total

    async def get_incident_events_count(
        self,
        project_id: uuid.UUID,
        incident_id: uuid.UUID,
    ) -> int:
        """Get total count of events linked to an incident."""
        stmt = (
            sa.select(sa.func.count())
            .select_from(IncidentEvent)
            .where(
                IncidentEvent.incident_id == incident_id,
                IncidentEvent.project_id == project_id,
            )
        )
        return (await self.session.execute(stmt)).scalar_one()
