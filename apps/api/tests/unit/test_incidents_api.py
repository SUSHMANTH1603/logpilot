"""Integration tests for Incident REST API endpoints and RBAC conforming to D06 § 7.5."""

import uuid
from datetime import UTC, datetime, timedelta

from httpx import AsyncClient

from logpilot_api.core.security import create_access_token, hash_password
from logpilot_api.db import session as db_session
from logpilot_api.modules.identity.models import User
from logpilot_api.modules.incidents.models import (
    Incident,
    IncidentEvent,
    IncidentEventRole,
    IncidentSeverity,
    IncidentState,
)
from logpilot_api.modules.ingestion.models import LogEvent, LogSource
from logpilot_api.modules.projects.models import ProjectMembership
from logpilot_api.modules.projects.schemas import ProjectCreate
from logpilot_api.modules.projects.service import ProjectService


async def _setup_test_project_with_members():
    sessionmaker = db_session.get_async_sessionmaker()
    async with sessionmaker() as session:
        # 1. Create project
        proj_service = ProjectService(session)
        project = await proj_service.project_repo.create(
            ProjectCreate(name="Incidents Workspace", slug=f"ws-{uuid.uuid4().hex[:6]}")
        )

        # 2. Create users (Owner, Engineer, Viewer, Outsider)
        owner = User(
            email=f"owner-{uuid.uuid4().hex[:6]}@example.com",
            password_hash=hash_password("Password123!"),
            full_name="Workspace Owner",
        )
        engineer = User(
            email=f"eng-{uuid.uuid4().hex[:6]}@example.com",
            password_hash=hash_password("Password123!"),
            full_name="Software Engineer",
        )
        viewer = User(
            email=f"viewer-{uuid.uuid4().hex[:6]}@example.com",
            password_hash=hash_password("Password123!"),
            full_name="Auditor Viewer",
        )
        outsider = User(
            email=f"outsider-{uuid.uuid4().hex[:6]}@example.com",
            password_hash=hash_password("Password123!"),
            full_name="Tenant Outsider",
        )
        session.add_all([owner, engineer, viewer, outsider])
        await session.flush()

        # 3. Create memberships
        m_owner = ProjectMembership(project_id=project.id, user_id=owner.id, role="OWNER")
        m_eng = ProjectMembership(project_id=project.id, user_id=engineer.id, role="ENGINEER")
        m_viewer = ProjectMembership(project_id=project.id, user_id=viewer.id, role="VIEWER")
        session.add_all([m_owner, m_eng, m_viewer])
        await session.flush()

        # 4. Create sample incident
        incident = Incident(
            project_id=project.id,
            incident_number="INC-2026-0001",
            title="Authentication Latency Surge",
            state=IncidentState.DETECTED.value,
            severity=IncidentSeverity.HIGH.value,
            window_start=datetime.now(UTC) - timedelta(minutes=5),
            window_end=datetime.now(UTC),
            detected_at=datetime.now(UTC),
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        session.add(incident)
        await session.flush()

        # 5. Create log source and event
        source = LogSource(
            project_id=project.id,
            name="auth-service",
            source_type="CONTAINER",
            environment="production",
        )
        session.add(source)
        await session.flush()

        event = LogEvent(
            project_id=project.id,
            log_source_id=source.id,
            timestamp=datetime.now(UTC),
            level="ERROR",
            message_raw="Database query timeout: 5000ms",
            attributes={"service": "auth"},
            event_hash="evt_hash_123",
            ingested_at=datetime.now(UTC),
        )
        session.add(event)
        await session.flush()

        inc_event = IncidentEvent(
            incident_id=incident.id,
            project_id=project.id,
            log_event_id=event.id,
            event_role=IncidentEventRole.TRIGGER.value,
            linked_at=datetime.now(UTC),
        )
        session.add(inc_event)
        await session.commit()

        tokens = {
            "owner": create_access_token(user_id=owner.id, email=owner.email),
            "engineer": create_access_token(user_id=engineer.id, email=engineer.email),
            "viewer": create_access_token(user_id=viewer.id, email=viewer.email),
            "outsider": create_access_token(user_id=outsider.id, email=outsider.email),
        }
        return project.id, incident.id, tokens


async def test_list_and_get_incidents(client: AsyncClient) -> None:
    """Validate GET /incidents and GET /incidents/{id} endpoints (D06 § 7.5)."""
    pid, inc_id, tokens = await _setup_test_project_with_members()

    # 1. Unauthenticated request -> 401
    res_unauth = await client.get(f"/api/v1/projects/{pid}/incidents")
    assert res_unauth.status_code == 401

    # 2. Outsider tenant isolation -> 404
    res_out = await client.get(
        f"/api/v1/projects/{pid}/incidents",
        headers={"Authorization": f"Bearer {tokens['outsider']}"},
    )
    assert res_out.status_code == 404

    # 3. Viewer can list incidents
    res_list = await client.get(
        f"/api/v1/projects/{pid}/incidents",
        headers={"Authorization": f"Bearer {tokens['viewer']}"},
    )
    assert res_list.status_code == 200
    data = res_list.json()
    assert data["total"] == 1
    assert data["items"][0]["incident_number"] == "INC-2026-0001"
    assert data["items"][0]["state"] == "DETECTED"

    # 4. Get incident details
    res_get = await client.get(
        f"/api/v1/projects/{pid}/incidents/{inc_id}",
        headers={"Authorization": f"Bearer {tokens['viewer']}"},
    )
    assert res_get.status_code == 200
    assert res_get.json()["id"] == str(inc_id)


async def test_get_incident_events(client: AsyncClient) -> None:
    """Validate GET /incidents/{id}/events returns linked log events."""
    pid, inc_id, tokens = await _setup_test_project_with_members()

    res = await client.get(
        f"/api/v1/projects/{pid}/incidents/{inc_id}/events",
        headers={"Authorization": f"Bearer {tokens['engineer']}"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 1
    assert data["items"][0]["event_role"] == "TRIGGER"


async def test_patch_incident_state_rbac(client: AsyncClient) -> None:
    """Validate PATCH /incidents/{id}/state requires ENGINEER or OWNER."""
    pid, inc_id, tokens = await _setup_test_project_with_members()

    # Viewer CANNOT update incident state -> 403 Forbidden
    res_viewer = await client.patch(
        f"/api/v1/projects/{pid}/incidents/{inc_id}/state",
        json={"state": "INVESTIGATING"},
        headers={"Authorization": f"Bearer {tokens['viewer']}"},
    )
    assert res_viewer.status_code == 403
    assert res_viewer.json()["error"]["code"] == "FORBIDDEN"

    # Engineer CAN update incident state -> 200 OK
    res_eng = await client.patch(
        f"/api/v1/projects/{pid}/incidents/{inc_id}/state",
        json={"state": "INVESTIGATING"},
        headers={"Authorization": f"Bearer {tokens['engineer']}"},
    )
    assert res_eng.status_code == 200
    assert res_eng.json()["state"] == "INVESTIGATING"

    # Moving to RESOLVED
    res_res = await client.patch(
        f"/api/v1/projects/{pid}/incidents/{inc_id}/state",
        json={"state": "RESOLVED"},
        headers={"Authorization": f"Bearer {tokens['owner']}"},
    )
    assert res_res.status_code == 200
    assert res_res.json()["state"] == "RESOLVED"
    assert res_res.json()["resolved_at"] is not None
