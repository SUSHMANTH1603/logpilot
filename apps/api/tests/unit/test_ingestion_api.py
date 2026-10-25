"""Integration tests for log ingestion vertical slice (D05, D06, D07, D11).

Tests prove:
1. User Bearer auth rejects missing, malformed, and arbitrary tokens (prevents false security).
2. Telemetry ingestion strictly requires valid source-key authentication.
3. Cross-project database constraints strictly enforce tenant boundaries.
4. Deterministic deduplication and secret redaction operate as documented.
"""

import uuid
from datetime import UTC, datetime

import pytest
from httpx import AsyncClient
from sqlalchemy.exc import IntegrityError

from logpilot_api.core.security import create_access_token
from logpilot_api.db import session as db_session
from logpilot_api.modules.identity.repository import UserRepository
from logpilot_api.modules.ingestion.models import LogEvent, LogSource, LogTemplate
from logpilot_api.modules.ingestion.schemas import LogSourceCreate
from logpilot_api.modules.ingestion.service import IngestionService
from logpilot_api.modules.projects.models import Project
from logpilot_api.modules.projects.repository import ProjectMembershipRepository
from logpilot_api.modules.projects.schemas import ProjectCreate


async def test_full_ingestion_slice_with_source_key_auth(client: AsyncClient) -> None:
    """Validate full ingestion slice via HTTP using source-key authentication (D06 § 7.4)."""
    # 1. Setup isolated Project and LogSource in database
    sessionmaker = db_session.get_async_sessionmaker()
    async with sessionmaker() as session:
        service = IngestionService(session)
        project = await service.project_repo.create(
            ProjectCreate(
                name="Checkout Service",
                slug=f"checkout-{uuid.uuid4().hex[:6]}",
                description="Payment and checkout pipeline",
            )
        )
        source, source_key = await service.register_log_source(
            project_id=project.id,
            data=LogSourceCreate(
                name="payment-api-stdout",
                source_type="FILE",
                environment="production",
            ),
        )
        await session.commit()
        project_id = project.id
        source_id = source.id

    assert source_key.startswith("lp_sk_")

    # 2. Ingest Batch via HTTP with X-LogPilot-Source-Key (D06 § 7.4 & D11 § 7.1)
    batch_payload = {
        "events": [
            {
                "timestamp": "2026-10-25T16:04:12.102Z",
                "message": (
                    "PaymentGatewayTimeout: Connection dropped after 3000ms "
                    "with token Bearer secret-token-xyz"
                ),
                "level": "ERROR",
                "attributes": {
                    "service": "payment-gateway",
                    "trace_id": "4bf92f3577b34da6a3ce929d0e0e4736",
                },
            }
        ]
    }

    ingest_res = await client.post(
        f"/api/v1/projects/{project_id}/log-sources/{source_id}/ingest",
        json=batch_payload,
        headers={"X-LogPilot-Source-Key": source_key},
    )
    assert ingest_res.status_code == 202
    ingest_data = ingest_res.json()
    run_id = ingest_data["ingestion_run_id"]
    assert ingest_data["status"] == "COMPLETED"
    assert ingest_data["received_count"] == 1

    # 3. Verify IngestionRun and LogEvent persisted in database with secrets redacted
    async with sessionmaker() as session:
        service = IngestionService(session)
        run = await service.get_ingestion_run(project_id, uuid.UUID(run_id))
        assert run.events_processed == 1
        assert run.errors_count == 0
        assert run.status == "COMPLETED"

        events = await service.ingestion_repo.get_events_by_source(source_id)
        assert len(events) == 1
        event = events[0]
        assert event.level == "ERROR"
        assert "secret-token-xyz" not in event.message_raw
        assert "[REDACTED_SECRET:BEARER_TOKEN]" in event.message_raw


async def test_idempotent_ingestion_deduplication(client: AsyncClient) -> None:
    """Verify repeated submissions of identical event batch do not duplicate (D07 § 9.3)."""
    sessionmaker = db_session.get_async_sessionmaker()
    async with sessionmaker() as session:
        service = IngestionService(session)
        project = await service.project_repo.create(
            ProjectCreate(name="Dedup App", slug=f"dedup-{uuid.uuid4().hex[:6]}")
        )
        source, source_key = await service.register_log_source(
            project_id=project.id,
            data=LogSourceCreate(name="app-logs", source_type="HTTP", environment="production"),
        )
        await session.commit()
        pid = project.id
        sid = source.id

    batch = {
        "events": [
            {
                "timestamp": "2026-10-25T16:00:00Z",
                "message": "Transaction committed",
                "level": "INFO",
                "attributes": {"tx_id": "tx_123"},
            }
        ]
    }

    # First submission -> processes 1 event
    res1 = await client.post(
        f"/api/v1/projects/{pid}/log-sources/{sid}/ingest",
        json=batch,
        headers={"X-LogPilot-Source-Key": source_key},
    )
    assert res1.status_code == 202

    # Second submission (identical batch retry) -> accepted with 0 new events processed
    res2 = await client.post(
        f"/api/v1/projects/{pid}/log-sources/{sid}/ingest",
        json=batch,
        headers={"X-LogPilot-Source-Key": source_key},
    )
    assert res2.status_code == 202
    run2_id = uuid.UUID(res2.json()["ingestion_run_id"])

    async with sessionmaker() as session:
        service = IngestionService(session)
        run2 = await service.get_ingestion_run(pid, run2_id)
        assert run2.events_processed == 0
        events = await service.ingestion_repo.get_events_by_source(sid)
        assert len(events) == 1


async def test_bearer_authentication_edge_cases_prevent_false_security(
    client: AsyncClient,
) -> None:
    """Verify missing, malformed, and arbitrary tokens are rejected (preventing false security)."""
    fake_pid = uuid.uuid4()

    # Case 1: Missing Authorization header -> 401
    res_no_auth = await client.post("/api/v1/projects", json={"name": "P", "slug": "p"})
    assert res_no_auth.status_code == 401
    err = res_no_auth.json()["error"]
    assert err["code"] == "UNAUTHORIZED"
    assert "Authorization" in err["message"]

    # Case 2: Malformed headers -> 401
    for bad_header in ["Basic dXNlcjpwYXNz", "Bearer", "Token abc", "Bearer    "]:
        res_malformed = await client.post(
            "/api/v1/projects",
            json={"name": "P", "slug": "p"},
            headers={"Authorization": bad_header},
        )
        assert res_malformed.status_code == 401
        assert res_malformed.json()["error"]["code"] == "UNAUTHORIZED"

    # Case 3: Syntactically valid but arbitrary / unrecognized token -> 401
    # Proves arbitrary tokens are NOT treated as authenticated users
    res_arbitrary = await client.post(
        "/api/v1/projects",
        json={"name": "P", "slug": "p"},
        headers={"Authorization": "Bearer arbitrary-unauthenticated-token-12345"},
    )
    assert res_arbitrary.status_code == 401
    assert res_arbitrary.json()["error"]["code"] == "UNAUTHORIZED"
    assert "token" in res_arbitrary.json()["error"]["message"].lower()

    # Case 4: Log source administrative routes reject arbitrary tokens -> 401
    res_src = await client.post(
        f"/api/v1/projects/{fake_pid}/log-sources",
        json={"name": "src", "source_type": "FILE", "environment": "production"},
        headers={"Authorization": "Bearer arbitrary-token"},
    )
    assert res_src.status_code == 401

    # Case 5: Unrelated administrative routes reject X-LogPilot-Source-Key -> 401
    res_src_key_on_admin = await client.post(
        "/api/v1/projects",
        json={"name": "P", "slug": "p"},
        headers={"X-LogPilot-Source-Key": "lp_sk_test_key"},
    )
    assert res_src_key_on_admin.status_code == 401


async def test_telemetry_ingestion_credential_validation(client: AsyncClient) -> None:
    """Verify ingestion endpoint rejects missing, invalid, and arbitrary credentials."""
    sessionmaker = db_session.get_async_sessionmaker()
    async with sessionmaker() as session:
        service = IngestionService(session)
        project = await service.project_repo.create(
            ProjectCreate(name="Ingest Auth Test", slug=f"ingest-auth-{uuid.uuid4().hex[:6]}")
        )
        source, valid_key = await service.register_log_source(
            project_id=project.id,
            data=LogSourceCreate(name="auth-src", source_type="CONTAINER", environment="staging"),
        )
        await session.commit()
        pid = project.id
        sid = source.id

    batch = {"events": [{"timestamp": "2026-10-25T16:00:00Z", "message": "ping", "level": "DEBUG"}]}

    # Missing all credentials -> 401
    res_missing = await client.post(f"/api/v1/projects/{pid}/log-sources/{sid}/ingest", json=batch)
    assert res_missing.status_code == 401
    assert res_missing.json()["error"]["code"] == "UNAUTHORIZED"

    # Invalid source key -> 401
    res_bad_key = await client.post(
        f"/api/v1/projects/{pid}/log-sources/{sid}/ingest",
        json=batch,
        headers={"X-LogPilot-Source-Key": "lp_sk_invalid_bogus_key"},
    )
    assert res_bad_key.status_code == 401
    assert res_bad_key.json()["error"]["code"] == "UNAUTHORIZED"

    # Arbitrary Bearer token on ingestion -> 401 (does NOT treat arbitrary token as authenticated)
    res_bearer = await client.post(
        f"/api/v1/projects/{pid}/log-sources/{sid}/ingest",
        json=batch,
        headers={"Authorization": "Bearer arbitrary-bearer-token"},
    )
    assert res_bearer.status_code == 401
    assert res_bearer.json()["error"]["code"] == "UNAUTHORIZED"

    # Valid source key -> 202 Accepted
    res_valid = await client.post(
        f"/api/v1/projects/{pid}/log-sources/{sid}/ingest",
        json=batch,
        headers={"X-LogPilot-Source-Key": valid_key},
    )
    assert res_valid.status_code == 202

    # Valid human Bearer token belonging to non-member -> 404 RESOURCE_NOT_FOUND (tenant isolation)
    async with sessionmaker() as session:
        user_repo = UserRepository(session)
        non_member = await user_repo.create("nonmember.ingest@test.com", "hash", "Non Member")
        member_eng = await user_repo.create("engineer.ingest@test.com", "hash", "Eng Member")
        await session.commit()
        non_member_id = non_member.id
        member_eng_id = member_eng.id

    async with sessionmaker() as session:
        member_repo = ProjectMembershipRepository(session)
        await member_repo.create_membership(pid, member_eng_id, "ENGINEER")
        await session.commit()

    non_member_token = create_access_token(non_member_id, "nonmember.ingest@test.com")
    member_eng_token = create_access_token(member_eng_id, "engineer.ingest@test.com")

    res_non_member = await client.post(
        f"/api/v1/projects/{pid}/log-sources/{sid}/ingest",
        json=batch,
        headers={"Authorization": f"Bearer {non_member_token}"},
    )
    assert res_non_member.status_code == 404
    assert res_non_member.json()["error"]["code"] == "RESOURCE_NOT_FOUND"

    # Valid human Bearer token belonging to member with ENGINEER role -> 202 Accepted
    res_eng = await client.post(
        f"/api/v1/projects/{pid}/log-sources/{sid}/ingest",
        json=batch,
        headers={"Authorization": f"Bearer {member_eng_token}"},
    )
    assert res_eng.status_code == 202


async def test_empty_and_malformed_payload_validation(client: AsyncClient) -> None:
    """Verify empty and malformed payloads return canonical D06 validation errors."""
    sessionmaker = db_session.get_async_sessionmaker()
    async with sessionmaker() as session:
        service = IngestionService(session)
        project = await service.project_repo.create(
            ProjectCreate(name="Validation App", slug=f"val-{uuid.uuid4().hex[:6]}")
        )
        source, valid_key = await service.register_log_source(
            project_id=project.id,
            data=LogSourceCreate(name="val-src", source_type="FILE", environment="production"),
        )
        await session.commit()
        pid = project.id
        sid = source.id

    # Empty events array -> 400 or 422
    empty_res = await client.post(
        f"/api/v1/projects/{pid}/log-sources/{sid}/ingest",
        json={"events": []},
        headers={"X-LogPilot-Source-Key": valid_key},
    )
    assert empty_res.status_code in (400, 422)
    err = empty_res.json()["error"]
    assert err["code"] in ("VALIDATION_ERROR", "BAD_REQUEST")

    # Missing required message -> 422
    invalid_event = await client.post(
        f"/api/v1/projects/{pid}/log-sources/{sid}/ingest",
        json={"events": [{"timestamp": "2026-10-25T16:00:00Z"}]},
        headers={"X-LogPilot-Source-Key": valid_key},
    )
    assert invalid_event.status_code == 422
    assert invalid_event.json()["error"]["code"] == "VALIDATION_ERROR"


async def test_project_isolation_enforcement(client: AsyncClient) -> None:
    """Verify cross-project resource access is prohibited and returns 404 (D05 § 10 / D06 § 4.3)."""
    sessionmaker = db_session.get_async_sessionmaker()
    async with sessionmaker() as session:
        service = IngestionService(session)
        p1 = await service.project_repo.create(
            ProjectCreate(name="P1", slug=f"p1-{uuid.uuid4().hex[:6]}")
        )
        p2 = await service.project_repo.create(
            ProjectCreate(name="P2", slug=f"p2-{uuid.uuid4().hex[:6]}")
        )
        s1, s1_key = await service.register_log_source(
            project_id=p1.id,
            data=LogSourceCreate(name="p1-src", source_type="HTTP", environment="production"),
        )
        await session.commit()
        p1_id = p1.id
        p2_id = p2.id
        s1_id = s1.id

    # Ingest event under P1 -> 202
    ingest1 = await client.post(
        f"/api/v1/projects/{p1_id}/log-sources/{s1_id}/ingest",
        json={"events": [{"timestamp": "2026-10-25T16:00:00Z", "message": "msg1"}]},
        headers={"X-LogPilot-Source-Key": s1_key},
    )
    assert ingest1.status_code == 202

    # Attempt to ingest using Project 2 URL with Source 1 ID -> 404 Not Found
    cross_ingest = await client.post(
        f"/api/v1/projects/{p2_id}/log-sources/{s1_id}/ingest",
        json={"events": [{"timestamp": "2026-10-25T16:00:00Z", "message": "msg2"}]},
        headers={"X-LogPilot-Source-Key": s1_key},
    )
    assert cross_ingest.status_code == 404
    assert cross_ingest.json()["error"]["code"] == "RESOURCE_NOT_FOUND"


async def test_database_level_cross_tenant_constraint_enforcement() -> None:
    """Verify composite foreign keys reject mismatched project_id at the database engine level."""
    sessionmaker = db_session.get_async_sessionmaker()
    async with sessionmaker() as session:
        p1 = Project(id=uuid.uuid4(), name="Tenant P1", slug=f"p1-{uuid.uuid4().hex[:6]}")
        p2 = Project(id=uuid.uuid4(), name="Tenant P2", slug=f"p2-{uuid.uuid4().hex[:6]}")
        session.add_all([p1, p2])
        await session.commit()

    async with sessionmaker() as session:
        s1 = LogSource(
            id=uuid.uuid4(),
            project_id=p1.id,
            name="s1-emitter",
            source_type="FILE",
            environment="production",
        )
        t1 = LogTemplate(
            id=uuid.uuid4(),
            project_id=p1.id,
            template_hash="tmpl-hash-1",
            pattern_raw="Pattern <*> error",
        )
        session.add_all([s1, t1])
        await session.commit()

    async with sessionmaker() as session:
        # Valid event: project_id matches both log_source.project_id and template.project_id
        valid_event = LogEvent(
            id=uuid.uuid4(),
            project_id=p1.id,
            log_source_id=s1.id,
            template_id=t1.id,
            timestamp=datetime.now(UTC),
            level="INFO",
            message_raw="Valid event",
            attributes={},
            event_hash="hash-1",
        )
        session.add(valid_event)
        await session.commit()

    async with sessionmaker() as session:
        # Test 1: project_id (p2) DISAGREES with log_source.project_id (p1)
        # Database composite FK fk_log_events_source_project must reject this with IntegrityError
        invalid_source_event = LogEvent(
            id=uuid.uuid4(),
            project_id=p2.id,
            log_source_id=s1.id,
            template_id=None,
            timestamp=datetime.now(UTC),
            level="ERROR",
            message_raw="Mismatched cross-project source event",
            attributes={},
            event_hash="hash-2",
        )
        session.add(invalid_source_event)
        with pytest.raises(IntegrityError):
            await session.commit()

    async with sessionmaker() as session:
        # Test 2: project_id (p2) DISAGREES with log_template.project_id (p1)
        # Database composite FK fk_log_events_template_project must reject this with IntegrityError
        s2 = LogSource(
            id=uuid.uuid4(),
            project_id=p2.id,
            name="s2-emitter",
            source_type="FILE",
            environment="production",
        )
        session.add(s2)
        await session.commit()

        invalid_template_event = LogEvent(
            id=uuid.uuid4(),
            project_id=p2.id,
            log_source_id=s2.id,
            template_id=t1.id,  # t1 belongs to p1!
            timestamp=datetime.now(UTC),
            level="ERROR",
            message_raw="Mismatched cross-project template event",
            attributes={},
            event_hash="hash-3",
        )
        session.add(invalid_template_event)
        with pytest.raises(IntegrityError):
            await session.commit()
