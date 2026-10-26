"""Service enforcing incident correlation, atomic numbering, and lifecycle transitions."""

import logging
import uuid
from collections.abc import Sequence
from datetime import UTC, datetime

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from logpilot_api.core.config import settings
from logpilot_api.core.errors import ConflictError, NotFoundError
from logpilot_api.modules.analysis.models import AnomalySignal
from logpilot_api.modules.incidents.models import (
    Incident,
    IncidentEvent,
    IncidentEventRole,
    IncidentSeverity,
    IncidentState,
)
from logpilot_api.modules.incidents.repository import IncidentRepository
from logpilot_api.modules.ingestion.models import LogEvent

logger = logging.getLogger(__name__)

# Valid transitions conforming to D05 § 5
VALID_STATE_TRANSITIONS: dict[str, set[str]] = {
    IncidentState.DETECTED.value: {
        IncidentState.INVESTIGATING.value,
        IncidentState.IGNORED.value,
    },
    IncidentState.INVESTIGATING.value: {
        IncidentState.RESOLVED.value,
        IncidentState.IGNORED.value,
    },
    IncidentState.RESOLVED.value: {
        IncidentState.INVESTIGATING.value,  # Reopening
    },
    IncidentState.IGNORED.value: set(),  # Terminal state
}


class IncidentService:
    """Service handling incident correlation, atomic numbering, and lifecycle state enforcement."""

    def __init__(
        self,
        session: AsyncSession,
        repository: IncidentRepository | None = None,
    ) -> None:
        self.session = session
        self.repo = repository or IncidentRepository(session)
        self.correlation_window_seconds = settings.incident_correlation_window_seconds
        self.trigger_score = settings.incident_trigger_score

    async def correlate_and_create(
        self,
        project_id: uuid.UUID,
        signal: AnomalySignal,
        evidence_events: Sequence[LogEvent],
    ) -> Incident | None:
        """Correlate anomaly signal with existing active incident or create a new one."""
        # Only trigger an incident if confidence meets threshold
        if signal.confidence_score < self.trigger_score:
            return None

        # Check for active incident within the correlation window
        active_incident = await self.repo.get_active_incident_in_correlation_window(
            project_id=project_id,
            window_start=signal.window_start,
            correlation_window_seconds=self.correlation_window_seconds,
        )

        if active_incident:
            # Correlate into existing incident
            if signal.window_end > active_incident.window_end:
                active_incident.window_end = signal.window_end
            active_incident.updated_at = datetime.now(UTC)

            # Link new evidence events
            await self._link_events_to_incident(
                incident=active_incident,
                events=evidence_events,
                default_role=IncidentEventRole.EVIDENCE,
            )
            return active_incident

        # Otherwise allocate project-scoped incident number atomically
        incident_number = await self.repo.allocate_incident_number(project_id)

        # Determine severity based on signal properties
        severity = IncidentSeverity.MEDIUM
        if signal.confidence_score >= 0.90:
            severity = IncidentSeverity.CRITICAL
        elif signal.confidence_score >= 0.80:
            severity = IncidentSeverity.HIGH

        title = f"{signal.anomaly_type.replace('_', ' ').title()} detected"

        incident = Incident(
            project_id=project_id,
            incident_number=incident_number,
            title=title,
            state=IncidentState.DETECTED.value,
            severity=severity.value,
            window_start=signal.window_start,
            window_end=signal.window_end,
            detected_at=signal.detected_at,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        await self.repo.create_incident(incident)

        # Link triggering events
        await self._link_events_to_incident(
            incident=incident,
            events=evidence_events,
            default_role=IncidentEventRole.TRIGGER,
        )

        logger.info(
            "Incident created: number=%s, project=%s, severity=%s",
            incident.incident_number,
            project_id,
            incident.severity,
        )
        return incident

    async def _link_events_to_incident(
        self,
        incident: Incident,
        events: Sequence[LogEvent],
        default_role: IncidentEventRole,
    ) -> None:
        """Link log events to the incident with appropriate roles, avoiding duplicates."""
        existing_event_ids = await self.repo.get_linked_log_event_ids(incident.id)
        seen_in_batch: set[uuid.UUID] = set()

        for idx, event in enumerate(events):
            if event.id in existing_event_ids or event.id in seen_in_batch:
                continue
            seen_in_batch.add(event.id)

            # First error/critical event gets TRIGGER, remaining get EVIDENCE or CORRELATED_CONTEXT
            role = default_role.value
            if default_role == IncidentEventRole.TRIGGER and idx > 0:
                role = IncidentEventRole.EVIDENCE.value

            incident_event = IncidentEvent(
                incident_id=incident.id,
                project_id=incident.project_id,
                log_event_id=event.id,
                event_role=role,
                linked_at=datetime.now(UTC),
            )
            try:
                async with self.session.begin_nested():
                    await self.repo.link_incident_event(incident_event)
            except IntegrityError:
                # Concurrently linked by another transaction; savepoint rolled back safely
                logger.debug(
                    "Duplicate incident-event link ignored concurrently: incident=%s, event=%s",
                    incident.id,
                    event.id,
                )

    async def transition_state(
        self,
        project_id: uuid.UUID,
        incident_id: uuid.UUID,
        target_state: IncidentState,
    ) -> Incident:
        """Validate and transition incident state according to D05 § 5 state machine."""
        incident = await self.repo.get_incident(project_id, incident_id)
        if not incident:
            raise NotFoundError("The requested incident was not found.")

        current_state = incident.state
        target = target_state.value

        if current_state == target:
            raise ConflictError(
                message=f"Incident is already in state '{target}'.",
                code="INVALID_STATE_TRANSITION",
            )

        allowed = VALID_STATE_TRANSITIONS.get(current_state, set())
        if target not in allowed:
            raise ConflictError(
                message=f"Transition from '{current_state}' to '{target}' is not permitted.",
                code="INVALID_STATE_TRANSITION",
            )

        # Apply state transition rules
        incident.state = target
        incident.updated_at = datetime.now(UTC)

        if target == IncidentState.RESOLVED.value:
            incident.resolved_at = datetime.now(UTC)
        elif (
            target == IncidentState.INVESTIGATING.value
            and current_state == IncidentState.RESOLVED.value
        ):
            # Reopening incident: clear resolved_at
            incident.resolved_at = None

        await self.session.flush()
        return incident

    async def get_incident(
        self,
        project_id: uuid.UUID,
        incident_id: uuid.UUID,
    ) -> Incident:
        """Retrieve an incident ensuring cross-tenant isolation."""
        incident = await self.repo.get_incident(project_id, incident_id)
        if not incident:
            raise NotFoundError("The requested incident was not found.")
        return incident

    async def list_incidents(
        self,
        project_id: uuid.UUID,
        state: str | None = None,
        severity: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[Sequence[Incident], int]:
        """List incidents for a project with optional filters and pagination."""
        return await self.repo.list_incidents(
            project_id=project_id,
            state=state,
            severity=severity,
            limit=limit,
            offset=offset,
        )

    async def list_incident_events(
        self,
        project_id: uuid.UUID,
        incident_id: uuid.UUID,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[Sequence[IncidentEvent], int]:
        """List events associated with an incident."""
        # Ensure incident exists and belongs to project
        await self.get_incident(project_id, incident_id)
        return await self.repo.list_incident_events(
            project_id=project_id,
            incident_id=incident_id,
            limit=limit,
            offset=offset,
        )
