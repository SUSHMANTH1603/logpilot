"""Unit tests for incident lifecycle state machine and transitions conforming to D05 § 5."""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from logpilot_api.core.errors import ConflictError, NotFoundError
from logpilot_api.db import session as db_session
from logpilot_api.modules.analysis.models import AnomalySignal, AnomalyType
from logpilot_api.modules.incidents.models import (
    Incident,
    IncidentEvent,
    IncidentEventRole,
    IncidentSeverity,
    IncidentState,
)
from logpilot_api.modules.incidents.service import IncidentService
from logpilot_api.modules.ingestion.models import LogEvent, LogSource
from logpilot_api.modules.projects.models import Project
from logpilot_api.modules.projects.schemas import ProjectCreate
from logpilot_api.modules.projects.service import ProjectService


async def _create_test_project(session: AsyncSession) -> Project:
    project_service = ProjectService(session)
    return await project_service.project_repo.create(
        ProjectCreate(
            name=f"Incident Project {uuid.uuid4().hex[:6]}",
            slug=f"inc-proj-{uuid.uuid4().hex[:6]}",
        )
    )


async def _create_test_log_source(session: AsyncSession, project_id: uuid.UUID) -> LogSource:
    source = LogSource(
        id=uuid.uuid4(),
        project_id=project_id,
        name=f"source-{uuid.uuid4().hex[:6]}",
        source_type="CONTAINER",
        environment="production",
        is_active=True,
        created_at=datetime.now(UTC),
    )
    session.add(source)
    await session.flush()
    return source


async def _create_test_log_event(
    session: AsyncSession,
    project_id: uuid.UUID,
    log_source_id: uuid.UUID,
) -> LogEvent:
    event = LogEvent(
        id=uuid.uuid4(),
        project_id=project_id,
        log_source_id=log_source_id,
        template_id=None,
        timestamp=datetime.now(UTC),
        level="ERROR",
        message_raw="Test error log message",
        attributes={"service": "test"},
        event_hash=uuid.uuid4().hex,
        ingested_at=datetime.now(UTC),
    )
    session.add(event)
    await session.flush()
    return event


async def test_atomic_incident_numbering() -> None:
    """Incident numbers are generated atomically with INC-YYYY-XXXX format."""
    sessionmaker = db_session.get_async_sessionmaker()
    async with sessionmaker() as session:
        project = await _create_test_project(session)
        service = IncidentService(session)

        # Allocate first incident number
        num1 = await service.repo.allocate_incident_number(project.id)
        current_year = datetime.now(UTC).year
        assert num1 == f"INC-{current_year}-0001"

        # Create an incident with num1
        inc1 = Incident(
            project_id=project.id,
            incident_number=num1,
            title="First Incident",
            state=IncidentState.DETECTED.value,
            severity=IncidentSeverity.HIGH.value,
            window_start=datetime.now(UTC) - timedelta(minutes=5),
            window_end=datetime.now(UTC),
            detected_at=datetime.now(UTC),
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        await service.repo.create_incident(inc1)
        await session.commit()

        # Allocate second incident number
        num2 = await service.repo.allocate_incident_number(project.id)
        assert num2 == f"INC-{current_year}-0002"


async def test_valid_incident_lifecycle_transitions() -> None:
    """Validate approved transitions: DETECTED -> INVESTIGATING -> RESOLVED -> REOPENED."""
    sessionmaker = db_session.get_async_sessionmaker()
    async with sessionmaker() as session:
        project = await _create_test_project(session)
        service = IncidentService(session)

        inc_num = await service.repo.allocate_incident_number(project.id)
        incident = Incident(
            project_id=project.id,
            incident_number=inc_num,
            title="Service Latency Degraded",
            state=IncidentState.DETECTED.value,
            severity=IncidentSeverity.HIGH.value,
            window_start=datetime.now(UTC) - timedelta(minutes=5),
            window_end=datetime.now(UTC),
            detected_at=datetime.now(UTC),
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        await service.repo.create_incident(incident)
        await session.commit()
        inc_id = incident.id

        # 1. DETECTED -> INVESTIGATING
        inc = await service.transition_state(project.id, inc_id, IncidentState.INVESTIGATING)
        assert inc.state == IncidentState.INVESTIGATING.value
        assert inc.resolved_at is None

        # 2. INVESTIGATING -> RESOLVED (sets resolved_at)
        inc = await service.transition_state(project.id, inc_id, IncidentState.RESOLVED)
        assert inc.state == IncidentState.RESOLVED.value
        assert inc.resolved_at is not None
        resolved_timestamp = inc.resolved_at

        # 3. RESOLVED -> INVESTIGATING (Reopening incident!)
        # Mandatory requirement: clear resolved_at and update updated_at
        inc = await service.transition_state(project.id, inc_id, IncidentState.INVESTIGATING)
        assert inc.state == IncidentState.INVESTIGATING.value
        assert inc.resolved_at is None
        assert inc.updated_at >= resolved_timestamp


async def test_illegal_state_transitions_rejected() -> None:
    """Illegal state machine transitions are rejected with 409 INVALID_STATE_TRANSITION."""
    sessionmaker = db_session.get_async_sessionmaker()
    async with sessionmaker() as session:
        project = await _create_test_project(session)
        service = IncidentService(session)

        inc_num = await service.repo.allocate_incident_number(project.id)
        incident = Incident(
            project_id=project.id,
            incident_number=inc_num,
            title="Database Connection Pool Exhausted",
            state=IncidentState.DETECTED.value,
            severity=IncidentSeverity.CRITICAL.value,
            window_start=datetime.now(UTC) - timedelta(minutes=5),
            window_end=datetime.now(UTC),
            detected_at=datetime.now(UTC),
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        await service.repo.create_incident(incident)
        await session.commit()
        inc_id = incident.id

        # 1. DETECTED -> RESOLVED is illegal (must investigate first)
        with pytest.raises(ConflictError) as exc_info:
            await service.transition_state(project.id, inc_id, IncidentState.RESOLVED)
        assert exc_info.value.code == "INVALID_STATE_TRANSITION"
        assert exc_info.value.status_code == 409

        # 2. Transitioning to same state is illegal
        with pytest.raises(ConflictError) as exc_info:
            await service.transition_state(project.id, inc_id, IncidentState.DETECTED)
        assert exc_info.value.code == "INVALID_STATE_TRANSITION"

        # 3. Move to terminal IGNORED state
        await service.transition_state(project.id, inc_id, IncidentState.IGNORED)

        # Transitioning out of terminal IGNORED is illegal
        with pytest.raises(ConflictError) as exc_info:
            await service.transition_state(project.id, inc_id, IncidentState.INVESTIGATING)
        assert exc_info.value.code == "INVALID_STATE_TRANSITION"


async def test_incident_tenant_isolation_get() -> None:
    """Accessing an incident belonging to another project returns NotFoundError (404)."""
    sessionmaker = db_session.get_async_sessionmaker()
    async with sessionmaker() as session:
        proj_a = await _create_test_project(session)
        proj_b = await _create_test_project(session)
        service = IncidentService(session)

        inc_num = await service.repo.allocate_incident_number(proj_a.id)
        incident_a = Incident(
            project_id=proj_a.id,
            incident_number=inc_num,
            title="Project A Incident",
            state=IncidentState.DETECTED.value,
            severity=IncidentSeverity.LOW.value,
            window_start=datetime.now(UTC),
            window_end=datetime.now(UTC),
            detected_at=datetime.now(UTC),
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        await service.repo.create_incident(incident_a)
        await session.commit()

        # Querying Project A's incident under Project B's scope must raise NotFoundError
        with pytest.raises(NotFoundError):
            await service.get_incident(proj_b.id, incident_a.id)


async def test_f01_duplicate_links_skipped_without_exception() -> None:
    """F-01: Existing event links are skipped without raising exceptions."""
    sessionmaker = db_session.get_async_sessionmaker()
    async with sessionmaker() as session:
        project = await _create_test_project(session)
        source = await _create_test_log_source(session, project.id)
        ev1 = await _create_test_log_event(session, project.id, source.id)
        ev2 = await _create_test_log_event(session, project.id, source.id)

        service = IncidentService(session)
        inc_num = await service.repo.allocate_incident_number(project.id)
        incident = Incident(
            project_id=project.id,
            incident_number=inc_num,
            title="Duplicate Link Test",
            state=IncidentState.DETECTED.value,
            severity=IncidentSeverity.MEDIUM.value,
            window_start=datetime.now(UTC) - timedelta(minutes=5),
            window_end=datetime.now(UTC),
            detected_at=datetime.now(UTC),
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        await service.repo.create_incident(incident)
        await session.flush()

        # Link first time
        await service._link_events_to_incident(
            incident=incident,
            events=[ev1, ev2],
            default_role=IncidentEventRole.TRIGGER,
        )
        await session.flush()

        count_1 = await service.repo.get_incident_events_count(project.id, incident.id)
        assert count_1 == 2

        # Link second time with same events - must not raise and count must remain 2
        await service._link_events_to_incident(
            incident=incident,
            events=[ev1, ev2],
            default_role=IncidentEventRole.EVIDENCE,
        )
        await session.flush()

        count_2 = await service.repo.get_incident_events_count(project.id, incident.id)
        assert count_2 == 2


async def test_f01_duplicate_batch_input_ids_deduplicated() -> None:
    """F-01: Duplicate event IDs within incoming batch do not produce duplicates."""
    sessionmaker = db_session.get_async_sessionmaker()
    async with sessionmaker() as session:
        project = await _create_test_project(session)
        source = await _create_test_log_source(session, project.id)
        ev1 = await _create_test_log_event(session, project.id, source.id)

        service = IncidentService(session)
        inc_num = await service.repo.allocate_incident_number(project.id)
        incident = Incident(
            project_id=project.id,
            incident_number=inc_num,
            title="Batch Dedup Test",
            state=IncidentState.DETECTED.value,
            severity=IncidentSeverity.MEDIUM.value,
            window_start=datetime.now(UTC) - timedelta(minutes=5),
            window_end=datetime.now(UTC),
            detected_at=datetime.now(UTC),
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        await service.repo.create_incident(incident)
        await session.flush()

        # Pass duplicate ev1 in the same batch
        await service._link_events_to_incident(
            incident=incident,
            events=[ev1, ev1, ev1],
            default_role=IncidentEventRole.TRIGGER,
        )
        await session.flush()

        count = await service.repo.get_incident_events_count(project.id, incident.id)
        assert count == 1


async def test_f01_duplicate_link_does_not_undo_incident_or_window_update() -> None:
    """F-01: Duplicate linking condition does not rollback outer transaction or window updates."""
    sessionmaker = db_session.get_async_sessionmaker()
    async with sessionmaker() as session:
        project = await _create_test_project(session)
        source = await _create_test_log_source(session, project.id)
        ev1 = await _create_test_log_event(session, project.id, source.id)

        service = IncidentService(session)
        now = datetime.now(UTC)
        signal1 = AnomalySignal(
            project_id=project.id,
            log_source_id=source.id,
            anomaly_type=AnomalyType.ERROR_RATE_SPIKE.value,
            confidence_score=0.85,
            window_start=now - timedelta(minutes=5),
            window_end=now,
            detected_at=now,
        )
        session.add(signal1)
        await session.flush()

        # Correlate or create incident with ev1
        inc = await service.correlate_and_create(
            project_id=project.id,
            signal=signal1,
            evidence_events=[ev1],
        )
        assert inc is not None
        await session.commit()
        inc_id = inc.id
        initial_window_end = inc.window_end

        # Second signal within correlation window with extended window_end
        new_window_end = now + timedelta(minutes=3)
        signal2 = AnomalySignal(
            project_id=project.id,
            log_source_id=source.id,
            anomaly_type=AnomalyType.FREQUENCY_SPIKE.value,
            confidence_score=0.88,
            window_start=now - timedelta(minutes=2),
            window_end=new_window_end,
            detected_at=now + timedelta(seconds=10),
        )
        session.add(signal2)
        await session.flush()

        # Same evidence event passed again
        correlated_inc = await service.correlate_and_create(
            project_id=project.id,
            signal=signal2,
            evidence_events=[ev1],
        )
        assert correlated_inc is not None
        await session.commit()

        assert correlated_inc.id == inc_id
        assert correlated_inc.window_end == new_window_end
        assert correlated_inc.window_end > initial_window_end

        # Incident is preserved and still queryable in database
        fetched = await service.get_incident(project.id, inc_id)
        assert fetched.id == inc_id
        assert fetched.window_end == new_window_end


async def test_f01_database_uniqueness_constraint_effective() -> None:
    """F-01: Direct duplicate insertion violates uq_incident_events_incident_log_event."""
    sessionmaker = db_session.get_async_sessionmaker()
    async with sessionmaker() as session:
        project = await _create_test_project(session)
        source = await _create_test_log_source(session, project.id)
        ev1 = await _create_test_log_event(session, project.id, source.id)

        service = IncidentService(session)
        inc_num = await service.repo.allocate_incident_number(project.id)
        incident = Incident(
            project_id=project.id,
            incident_number=inc_num,
            title="Direct Uniqueness Test",
            state=IncidentState.DETECTED.value,
            severity=IncidentSeverity.MEDIUM.value,
            window_start=datetime.now(UTC),
            window_end=datetime.now(UTC),
            detected_at=datetime.now(UTC),
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        await service.repo.create_incident(incident)
        await session.flush()

        link1 = IncidentEvent(
            incident_id=incident.id,
            project_id=project.id,
            log_event_id=ev1.id,
            event_role=IncidentEventRole.TRIGGER.value,
        )
        session.add(link1)
        await session.flush()

        link2 = IncidentEvent(
            incident_id=incident.id,
            project_id=project.id,
            log_event_id=ev1.id,
            event_role=IncidentEventRole.EVIDENCE.value,
        )
        session.add(link2)
        with pytest.raises(IntegrityError):
            await session.flush()


async def test_f02_anomaly_signal_rejects_cross_project_log_source() -> None:
    """F-02: AnomalySignal cannot reference a log source from another project at database level."""
    sessionmaker = db_session.get_async_sessionmaker()
    async with sessionmaker() as session:
        proj_a = await _create_test_project(session)
        proj_b = await _create_test_project(session)

        # Source belongs to proj_a
        source_a = await _create_test_log_source(session, proj_a.id)

        now = datetime.now(UTC)
        # Attempt to create AnomalySignal under proj_b referencing source_a
        invalid_signal = AnomalySignal(
            project_id=proj_b.id,
            log_source_id=source_a.id,
            anomaly_type=AnomalyType.ERROR_RATE_SPIKE.value,
            confidence_score=0.85,
            window_start=now - timedelta(minutes=5),
            window_end=now,
            detected_at=now,
        )
        session.add(invalid_signal)
        with pytest.raises(IntegrityError):
            await session.flush()


async def test_f03_incident_event_rejects_cross_project_log_event() -> None:
    """F-03: IncidentEvent cannot reference a log event from another project at database level."""
    sessionmaker = db_session.get_async_sessionmaker()
    async with sessionmaker() as session:
        proj_a = await _create_test_project(session)
        proj_b = await _create_test_project(session)

        source_a = await _create_test_log_source(session, proj_a.id)
        event_a = await _create_test_log_event(session, proj_a.id, source_a.id)

        service_b = IncidentService(session)
        inc_num_b = await service_b.repo.allocate_incident_number(proj_b.id)
        incident_b = Incident(
            project_id=proj_b.id,
            incident_number=inc_num_b,
            title="Project B Incident",
            state=IncidentState.DETECTED.value,
            severity=IncidentSeverity.LOW.value,
            window_start=datetime.now(UTC),
            window_end=datetime.now(UTC),
            detected_at=datetime.now(UTC),
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        await service_b.repo.create_incident(incident_b)
        await session.flush()

        # Attempt to link event_a (from proj_a) to incident_b (from proj_b)
        invalid_link = IncidentEvent(
            incident_id=incident_b.id,
            project_id=proj_b.id,
            log_event_id=event_a.id,
            event_role=IncidentEventRole.EVIDENCE.value,
        )
        session.add(invalid_link)
        with pytest.raises(IntegrityError):
            await session.flush()
