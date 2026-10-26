"""End-to-end integration test demonstrating anomalous error burst produces AnomalySignal
and DETECTED Incident.
"""

import uuid
from datetime import UTC, datetime, timedelta

import sqlalchemy as sa
from httpx import AsyncClient

from logpilot_api.core.security import create_access_token, hash_password
from logpilot_api.db import session as db_session
from logpilot_api.modules.analysis.models import AnomalySignal
from logpilot_api.modules.identity.models import User
from logpilot_api.modules.incidents.models import Incident, IncidentEvent, IncidentState
from logpilot_api.modules.ingestion.schemas import LogSourceCreate
from logpilot_api.modules.ingestion.service import IngestionService
from logpilot_api.modules.projects.models import ProjectMembership
from logpilot_api.modules.projects.schemas import ProjectCreate
from logpilot_api.modules.projects.service import ProjectService


async def test_end_to_end_anomalous_burst_produces_incident(client: AsyncClient) -> None:
    """Verify that an anomalous burst of critical errors produces AnomalySignal and Incident."""
    sessionmaker = db_session.get_async_sessionmaker()

    # 1. Setup Project, User, and LogSource
    async with sessionmaker() as session:
        proj_service = ProjectService(session)
        project = await proj_service.project_repo.create(
            ProjectCreate(name="E2E Pipeline Project", slug=f"e2e-{uuid.uuid4().hex[:6]}")
        )
        user = User(
            email=f"e2e-{uuid.uuid4().hex[:6]}@example.com",
            password_hash=hash_password("Password123!"),
            full_name="E2E Lead",
        )
        session.add(user)
        await session.flush()

        membership = ProjectMembership(project_id=project.id, user_id=user.id, role="OWNER")
        session.add(membership)

        ingestion_service = IngestionService(session)
        source, source_key = await ingestion_service.register_log_source(
            project_id=project.id,
            data=LogSourceCreate(
                name="order-processor",
                source_type="CONTAINER",
                environment="production",
            ),
        )
        await session.commit()
        pid = project.id
        sid = source.id
        auth_token = create_access_token(user_id=user.id, email=user.email)

    # 2. Submit anomalous burst batch (5 critical / error failures)
    now = datetime.now(UTC)
    batch_payload = {
        "events": [
            {
                "timestamp": (now - timedelta(seconds=i * 5)).isoformat(),
                "message": f"CRITICAL: Payment service failure transaction #{i}",
                "level": "CRITICAL",
                "attributes": {"attempt": i, "cluster": "prod-us-east-1"},
            }
            for i in range(5)
        ]
    }

    # Submit batch to ingestion endpoint
    ingest_res = await client.post(
        f"/api/v1/projects/{pid}/log-sources/{sid}/ingest",
        json=batch_payload,
        headers={"X-LogPilot-Source-Key": source_key},
    )
    # Reconciled D06 contract: HTTP 202 Accepted with status QUEUED
    assert ingest_res.status_code == 202
    res_data = ingest_res.json()
    assert res_data["status"] == "QUEUED"
    assert res_data["received_count"] == 5
    run_id = uuid.UUID(res_data["ingestion_run_id"])

    # 3. Verify in database: IngestionRun completed, AnomalySignal persisted, Incident created
    async with sessionmaker() as session:
        ing_service = IngestionService(session)
        run = await ing_service.get_ingestion_run(pid, run_id)
        assert run.status == "COMPLETED"
        assert run.events_processed == 5

        # Check AnomalySignal
        sig_stmt = sa.select(AnomalySignal).where(AnomalySignal.project_id == pid)
        signals = (await session.execute(sig_stmt)).scalars().all()
        assert len(signals) >= 1
        signal = signals[0]
        assert signal.confidence_score >= 0.70
        assert signal.log_source_id == sid

        # Check Incident
        inc_stmt = sa.select(Incident).where(Incident.project_id == pid)
        incidents = (await session.execute(inc_stmt)).scalars().all()
        assert len(incidents) == 1
        incident = incidents[0]
        assert incident.state == IncidentState.DETECTED.value
        assert incident.incident_number.startswith("INC-")

        # Check IncidentEvent link
        evt_stmt = sa.select(IncidentEvent).where(IncidentEvent.incident_id == incident.id)
        linked_events = (await session.execute(evt_stmt)).scalars().all()
        assert len(linked_events) >= 1
        roles = [le.event_role for le in linked_events]
        assert "TRIGGER" in roles

    # 4. Verify Incident API returns the newly created incident
    api_res = await client.get(
        f"/api/v1/projects/{pid}/incidents",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert api_res.status_code == 200
    api_data = api_res.json()
    assert api_data["total"] == 1
    assert api_data["items"][0]["incident_number"] == incident.incident_number
    assert api_data["items"][0]["state"] == "DETECTED"
