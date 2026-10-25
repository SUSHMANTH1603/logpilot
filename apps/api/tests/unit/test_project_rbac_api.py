"""Unit and integration tests for atomic project creation, tenant isolation, and RBAC."""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.exc import IntegrityError

from logpilot_api.core.errors import ConflictError
from logpilot_api.db import session as db_session
from logpilot_api.modules.identity.repository import UserRepository
from logpilot_api.modules.projects.repository import ProjectMembershipRepository, ProjectRepository
from logpilot_api.modules.projects.schemas import MemberAddRequest, ProjectCreate
from logpilot_api.modules.projects.service import ProjectService


async def _create_test_user_and_token(client: AsyncClient, email: str) -> tuple[dict, str]:
    """Helper creating user and returning user profile and access token."""
    reg = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "Password123!", "full_name": "Test User"},
    )
    assert reg.status_code == 201
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "Password123!"},
    )
    assert login.status_code == 200
    token = login.json()["access_token"]
    return reg.json(), token


async def test_atomic_project_creation_and_owner_assignment(client: AsyncClient) -> None:
    """Validate project creation and initial OWNER membership are atomic (D06 § 7.2)."""
    user_data, token = await _create_test_user_and_token(client, "owner.create@logpilot.io")
    user_id = uuid.UUID(user_data["id"])

    slug = f"atomic-proj-{uuid.uuid4().hex[:6]}"
    res = await client.post(
        "/api/v1/projects",
        json={"name": "Atomic Project", "slug": slug, "description": "Testing atomicity"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 201
    project_id = uuid.UUID(res.json()["id"])

    # Verify both Project and ProjectMembership exist with role=OWNER
    sessionmaker = db_session.get_async_sessionmaker()
    async with sessionmaker() as session:
        project_repo = ProjectRepository(session)
        member_repo = ProjectMembershipRepository(session)

        project = await project_repo.get_by_id(project_id)
        assert project is not None
        assert project.slug == slug

        membership = await member_repo.get_membership(project_id, user_id)
        assert membership is not None
        assert membership.role == "OWNER"


async def test_atomic_project_creation_rollback_boundary() -> None:
    """Validate failure during membership creation rolls back the project cleanly."""
    sessionmaker = db_session.get_async_sessionmaker()

    async with sessionmaker() as session:
        service = ProjectService(session)
        slug = f"rollback-{uuid.uuid4().hex[:6]}"

        # Attempt atomic creation with invalid foreign key user_id to force transaction rollback
        fake_user_id = uuid.uuid4()
        with pytest.raises(IntegrityError):
            await service.create_project_with_owner(
                ProjectCreate(name="Fail Project", slug=slug),
                creator_user_id=fake_user_id,
            )

    # Verify project was NOT committed to the database
    async with sessionmaker() as session:
        project_repo = ProjectRepository(session)
        persisted = await project_repo.get_by_slug(slug)
        assert persisted is None


async def test_user_specific_project_listing_isolation(client: AsyncClient) -> None:
    """Validate GET /api/v1/projects returns only projects the authenticated user belongs to."""
    u1, token1 = await _create_test_user_and_token(client, "user1@logpilot.io")
    u2, token2 = await _create_test_user_and_token(client, "user2@logpilot.io")

    # User 1 creates Project 1
    p1_res = await client.post(
        "/api/v1/projects",
        json={"name": "P1", "slug": f"p1-{uuid.uuid4().hex[:6]}"},
        headers={"Authorization": f"Bearer {token1}"},
    )
    p1_id = p1_res.json()["id"]

    # User 2 creates Project 2
    p2_res = await client.post(
        "/api/v1/projects",
        json={"name": "P2", "slug": f"p2-{uuid.uuid4().hex[:6]}"},
        headers={"Authorization": f"Bearer {token2}"},
    )
    p2_id = p2_res.json()["id"]

    # User 1 lists projects -> only P1
    u1_list = await client.get("/api/v1/projects", headers={"Authorization": f"Bearer {token1}"})
    assert u1_list.status_code == 200
    u1_pids = [p["id"] for p in u1_list.json()]
    assert p1_id in u1_pids
    assert p2_id not in u1_pids
    assert u1_list.json()[0]["role"] == "OWNER"

    # User 2 lists projects -> only P2
    u2_list = await client.get("/api/v1/projects", headers={"Authorization": f"Bearer {token2}"})
    assert u2_list.status_code == 200
    u2_pids = [p["id"] for p in u2_list.json()]
    assert p2_id in u2_pids
    assert p1_id not in u2_pids


async def test_cross_tenant_enumeration_prevention_404(client: AsyncClient) -> None:
    """Validate non-member accessing an existing project receives uniform 404 Not Found."""
    _, token1 = await _create_test_user_and_token(client, "alice.owner@logpilot.io")
    _, token2 = await _create_test_user_and_token(client, "mallory.outsider@logpilot.io")

    # Alice creates private project
    proj_res = await client.post(
        "/api/v1/projects",
        json={"name": "Alice Private Project", "slug": f"alice-{uuid.uuid4().hex[:6]}"},
        headers={"Authorization": f"Bearer {token1}"},
    )
    alice_pid = proj_res.json()["id"]

    # Mallory attempts to access Alice's project -> MUST receive 404 (not 403)
    get_proj = await client.get(
        f"/api/v1/projects/{alice_pid}",
        headers={"Authorization": f"Bearer {token2}"},
    )
    assert get_proj.status_code == 404
    assert get_proj.json()["error"]["code"] == "RESOURCE_NOT_FOUND"

    # Mallory attempts to list members -> 404
    get_members = await client.get(
        f"/api/v1/projects/{alice_pid}/members",
        headers={"Authorization": f"Bearer {token2}"},
    )
    assert get_members.status_code == 404

    # Mallory attempts to list log-sources -> 404
    get_sources = await client.get(
        f"/api/v1/projects/{alice_pid}/log-sources",
        headers={"Authorization": f"Bearer {token2}"},
    )
    assert get_sources.status_code == 404


async def test_rbac_role_permissions_and_anti_escalation(client: AsyncClient) -> None:
    """Validate OWNER, ENGINEER, and VIEWER permissions and prevent privilege escalation."""
    _, owner_token = await _create_test_user_and_token(client, "proj.owner@logpilot.io")
    eng_user, eng_token = await _create_test_user_and_token(client, "proj.eng@logpilot.io")
    viewer_user, viewer_token = await _create_test_user_and_token(client, "proj.viewer@logpilot.io")

    # Owner creates project
    p_res = await client.post(
        "/api/v1/projects",
        json={"name": "RBAC Project", "slug": f"rbac-{uuid.uuid4().hex[:6]}"},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    pid = p_res.json()["id"]

    # Owner adds Engineer
    add_eng = await client.post(
        f"/api/v1/projects/{pid}/members",
        json={"user_id": eng_user["id"], "role": "ENGINEER"},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert add_eng.status_code == 200
    assert add_eng.json()["role"] == "ENGINEER"

    # Owner adds Viewer
    add_viewer = await client.post(
        f"/api/v1/projects/{pid}/members",
        json={"user_id": viewer_user["id"], "role": "VIEWER"},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert add_viewer.status_code == 200
    assert add_viewer.json()["role"] == "VIEWER"

    # 1. VIEWER TESTS:
    # Viewer can read project and members (200 OK)
    viewer_headers = {"Authorization": f"Bearer {viewer_token}"}
    assert (await client.get(f"/api/v1/projects/{pid}", headers=viewer_headers)).status_code == 200
    assert (
        await client.get(f"/api/v1/projects/{pid}/members", headers=viewer_headers)
    ).status_code == 200
    assert (
        await client.get(f"/api/v1/projects/{pid}/log-sources", headers=viewer_headers)
    ).status_code == 200

    # Viewer CANNOT create log source -> 403 Forbidden
    v_src = await client.post(
        f"/api/v1/projects/{pid}/log-sources",
        json={"name": "v-src", "source_type": "FILE", "environment": "production"},
        headers={"Authorization": f"Bearer {viewer_token}"},
    )
    assert v_src.status_code == 403
    assert v_src.json()["error"]["code"] == "FORBIDDEN"

    # Viewer CANNOT add/modify members -> 403 Forbidden
    v_add = await client.post(
        f"/api/v1/projects/{pid}/members",
        json={"user_id": eng_user["id"], "role": "OWNER"},
        headers={"Authorization": f"Bearer {viewer_token}"},
    )
    assert v_add.status_code == 403

    # 2. ENGINEER TESTS:
    # Engineer CAN create log source (201 Created)
    eng_src = await client.post(
        f"/api/v1/projects/{pid}/log-sources",
        json={"name": "eng-src", "source_type": "CONTAINER", "environment": "staging"},
        headers={"Authorization": f"Bearer {eng_token}"},
    )
    assert eng_src.status_code == 201
    source_id = eng_src.json()["id"]

    # Engineer CAN ingest telemetry using Bearer token (202 Accepted)
    batch = {"events": [{"timestamp": "2026-10-25T16:00:00Z", "message": "msg", "level": "INFO"}]}
    ing_eng = await client.post(
        f"/api/v1/projects/{pid}/log-sources/{source_id}/ingest",
        json=batch,
        headers={"Authorization": f"Bearer {eng_token}"},
    )
    assert ing_eng.status_code == 202

    # Viewer CANNOT ingest telemetry using Bearer token -> 403 Forbidden
    ing_v = await client.post(
        f"/api/v1/projects/{pid}/log-sources/{source_id}/ingest",
        json=batch,
        headers={"Authorization": f"Bearer {viewer_token}"},
    )
    assert ing_v.status_code == 403

    # Engineer CANNOT add members or escalate privileges -> 403 Forbidden
    eng_add = await client.post(
        f"/api/v1/projects/{pid}/members",
        json={"user_id": viewer_user["id"], "role": "ENGINEER"},
        headers={"Authorization": f"Bearer {eng_token}"},
    )
    assert eng_add.status_code == 403

    # Engineer CANNOT escalate self to OWNER -> 403 Forbidden
    eng_self_esc = await client.post(
        f"/api/v1/projects/{pid}/members",
        json={"user_id": eng_user["id"], "role": "OWNER"},
        headers={"Authorization": f"Bearer {eng_token}"},
    )
    assert eng_self_esc.status_code == 403


async def test_project_membership_uniqueness_and_cascade_deletion() -> None:
    """Validate database-level unique constraint and cascade deletions."""
    sessionmaker = db_session.get_async_sessionmaker()

    # 1. Test uniqueness constraint
    async with sessionmaker() as session:
        user_repo = UserRepository(session)
        project_repo = ProjectRepository(session)
        member_repo = ProjectMembershipRepository(session)

        u = await user_repo.create("uniq@test.com", "hash", "Uniq User")
        p = await project_repo.create(
            ProjectCreate(name="Uniq Project", slug=f"u-{uuid.uuid4().hex[:6]}")
        )
        await session.commit()
        uid = u.id
        pid = p.id

    async with sessionmaker() as session:
        member_repo = ProjectMembershipRepository(session)
        await member_repo.create_membership(pid, uid, "ENGINEER")
        await session.commit()

    # Attempt inserting duplicate (pid, uid)
    async with sessionmaker() as session:
        member_repo = ProjectMembershipRepository(session)
        with pytest.raises(IntegrityError):
            await member_repo.create_membership(pid, uid, "VIEWER")
            await session.commit()

    # 2. Test cascade delete on project deletion
    async with sessionmaker() as session:
        project_repo = ProjectRepository(session)
        member_repo = ProjectMembershipRepository(session)
        p = await project_repo.get_by_id(pid)
        await session.delete(p)
        await session.commit()

        # Membership must be deleted by cascade
        membership = await member_repo.get_membership(pid, uid)
        assert membership is None


async def test_sole_owner_demotion_and_removal_protection(client: AsyncClient) -> None:
    """Validate sole-owner self-demotion, demotion by another OWNER, and permitted demotion."""
    # 1. Create project with owner1
    owner1_user, owner1_token = await _create_test_user_and_token(client, "sole.owner1@logpilot.io")
    owner1_id = owner1_user["id"]
    headers1 = {"Authorization": f"Bearer {owner1_token}"}

    proj_res = await client.post(
        "/api/v1/projects",
        json={"name": "Sole Owner Project", "slug": f"sole-{uuid.uuid4().hex[:6]}"},
        headers=headers1,
    )
    assert proj_res.status_code == 201
    pid = proj_res.json()["id"]

    # 2. Sole-owner self-demotion to VIEWER -> rejected with 409 CONFLICT
    demote_res = await client.post(
        f"/api/v1/projects/{pid}/members",
        json={"user_id": owner1_id, "role": "VIEWER"},
        headers=headers1,
    )
    assert demote_res.status_code == 409
    assert demote_res.json()["error"]["code"] == "CONFLICT"
    assert "sole project owner" in demote_res.json()["error"]["message"].lower()

    # 3. Sole-owner removal -> rejected with 409 CONFLICT
    del_res = await client.delete(
        f"/api/v1/projects/{pid}/members/{owner1_id}",
        headers=headers1,
    )
    assert del_res.status_code == 409
    assert del_res.json()["error"]["code"] == "CONFLICT"
    assert "sole project owner" in del_res.json()["error"]["message"].lower()

    # 4. Add second owner (owner2)
    owner2_user, owner2_token = await _create_test_user_and_token(
        client, "second.owner@logpilot.io"
    )
    owner2_id = owner2_user["id"]
    headers2 = {"Authorization": f"Bearer {owner2_token}"}

    add_owner2 = await client.post(
        f"/api/v1/projects/{pid}/members",
        json={"user_id": owner2_id, "role": "OWNER"},
        headers=headers1,
    )
    assert add_owner2.status_code == 200

    # 5. Permitted demotion: owner1 demoting owner2 to ENGINEER when another OWNER remains -> 200 OK
    demote_o2 = await client.post(
        f"/api/v1/projects/{pid}/members",
        json={"user_id": owner2_id, "role": "ENGINEER"},
        headers=headers1,
    )
    assert demote_o2.status_code == 200
    assert demote_o2.json()["role"] == "ENGINEER"

    # Re-promote owner2 to OWNER
    re_promote = await client.post(
        f"/api/v1/projects/{pid}/members",
        json={"user_id": owner2_id, "role": "OWNER"},
        headers=headers1,
    )
    assert re_promote.status_code == 200

    # 6. Permitted demotion: owner2 demotes owner1 to VIEWER -> 200 OK
    demote_o1 = await client.post(
        f"/api/v1/projects/{pid}/members",
        json={"user_id": owner1_id, "role": "VIEWER"},
        headers=headers2,
    )
    assert demote_o1.status_code == 200
    assert demote_o1.json()["role"] == "VIEWER"

    # Now owner2 is the sole remaining OWNER. Trying to demote owner2 -> rejected with 409 CONFLICT
    demote_sole_o2 = await client.post(
        f"/api/v1/projects/{pid}/members",
        json={"user_id": owner2_id, "role": "ENGINEER"},
        headers=headers2,
    )
    assert demote_sole_o2.status_code == 409
    assert demote_sole_o2.json()["error"]["code"] == "CONFLICT"

    # 7. Permitted removal: owner2 removes owner1 (who is now VIEWER) -> 204 No Content
    del_o1 = await client.delete(
        f"/api/v1/projects/{pid}/members/{owner1_id}",
        headers=headers2,
    )
    assert del_o1.status_code == 204


async def test_concurrent_project_slug_conflict_mapped_to_409(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Validate database-level slug collision maps to HTTP 409 CONFLICT."""
    sessionmaker = db_session.get_async_sessionmaker()
    slug = f"dup-slug-{uuid.uuid4().hex[:6]}"

    async with sessionmaker() as session:
        user_repo = UserRepository(session)
        user = await user_repo.create("slug.creator@test.com", "hash", "Creator")
        await session.commit()
        uid = user.id

    async with sessionmaker() as session:
        service = ProjectService(session)
        # Create first project
        await service.create_project_with_owner(
            ProjectCreate(name="First Project", slug=slug),
            creator_user_id=uid,
        )

        # Force bypass pre-check to simulate race where two requests pass pre-check concurrently
        async def fake_get_by_slug(_slug: str):
            return None

        monkeypatch.setattr(service.project_repo, "get_by_slug", fake_get_by_slug)

        with pytest.raises(ConflictError) as exc_info:
            await service.create_project_with_owner(
                ProjectCreate(name="Second Project", slug=slug),
                creator_user_id=uid,
            )

        assert exc_info.value.code == "CONFLICT"
        assert exc_info.value.status_code == 409


async def test_concurrent_membership_upsert_recovered_cleanly() -> None:
    """Validate concurrent membership insertion recovers cleanly upon database collision."""
    sessionmaker = db_session.get_async_sessionmaker()

    async with sessionmaker() as session:
        user_repo = UserRepository(session)
        u1 = await user_repo.create("concurrent.u1@test.com", "hash", "User 1")
        u2 = await user_repo.create("concurrent.u2@test.com", "hash", "User 2")
        await session.commit()
        uid1 = u1.id
        uid2 = u2.id

    async with sessionmaker() as session:
        service = ProjectService(session)
        project = await service.create_project_with_owner(
            ProjectCreate(name="Concurrent Mem Proj", slug=f"con-mem-{uuid.uuid4().hex[:6]}"),
            creator_user_id=uid1,
        )
        pid = project.id

    # Pre-insert membership into database
    async with sessionmaker() as session:
        member_repo = ProjectMembershipRepository(session)
        await member_repo.create_membership(pid, uid2, "ENGINEER")
        await session.commit()

    # Now call add_or_update_member with mocked get_membership returning None (simulating race)
    async with sessionmaker() as session:
        service = ProjectService(session)
        original_get = service.member_repo.get_membership

        call_count = 0

        async def race_get_membership(p_id, u_id):
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                # First two calls return None to trigger collision on session.add
                return None
            return await original_get(p_id, u_id)

        service.member_repo.get_membership = race_get_membership

        resp = await service.add_or_update_member(
            project_id=pid,
            payload=MemberAddRequest(user_id=uid2, role="VIEWER"),
        )
        assert resp.role == "VIEWER"
        assert resp.user_id == uid2


async def test_project_row_lock_invoked_before_owner_decision() -> None:
    """Validate pessimistic row lock on project is acquired before owner count evaluation."""
    sessionmaker = db_session.get_async_sessionmaker()

    async with sessionmaker() as session:
        user_repo = UserRepository(session)
        user = await user_repo.create("lock.test@logpilot.io", "hash", "Lock Test User")
        await session.commit()
        uid = user.id

    async with sessionmaker() as session:
        service = ProjectService(session)
        project = await service.create_project_with_owner(
            ProjectCreate(name="Lock Project", slug=f"lock-{uuid.uuid4().hex[:6]}"),
            creator_user_id=uid,
        )
        pid = project.id

    async with sessionmaker() as session:
        service = ProjectService(session)
        call_order = []

        orig_lock = service.project_repo.get_by_id_for_update
        orig_count = service.member_repo.count_owners

        async def tracked_lock(p_id):
            call_order.append("lock")
            return await orig_lock(p_id)

        async def tracked_count(p_id):
            call_order.append("count")
            return await orig_count(p_id)

        service.project_repo.get_by_id_for_update = tracked_lock
        service.member_repo.count_owners = tracked_count

        # 1. Test add_or_update_member acquires lock before counting owners
        with pytest.raises(ConflictError):
            await service.add_or_update_member(pid, MemberAddRequest(user_id=uid, role="VIEWER"))

        assert call_order == ["lock", "count"]

        # 2. Test remove_member acquires lock before counting owners
        call_order.clear()
        with pytest.raises(ConflictError):
            await service.remove_member(pid, uid)

        assert call_order == ["lock", "count"]


async def test_unrelated_integrity_error_not_misclassified_as_membership_conflict(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Validate unrelated constraint failures propagate rather than misclassifying."""
    sessionmaker = db_session.get_async_sessionmaker()

    async with sessionmaker() as session:
        user_repo = UserRepository(session)
        user = await user_repo.create("fk.user@logpilot.io", "hash", "FK User")
        user2 = await user_repo.create("fk.user2@logpilot.io", "hash", "FK User 2")
        await session.commit()
        uid = user.id
        u2_id = user2.id

    async with sessionmaker() as session:
        service = ProjectService(session)
        project = await service.create_project_with_owner(
            ProjectCreate(name="FK Project", slug=f"fk-{uuid.uuid4().hex[:6]}"),
            creator_user_id=uid,
        )
        pid = project.id

    async with sessionmaker() as session:
        service = ProjectService(session)

        # Mock upsert_membership to raise a foreign-key IntegrityError
        orig_orig = Exception("FOREIGN KEY constraint failed: project_memberships.user_id")
        fk_integrity_error = IntegrityError("statement", [], orig_orig)

        async def fake_upsert(*args, **kwargs):
            raise fk_integrity_error

        monkeypatch.setattr(service.member_repo, "upsert_membership", fake_upsert)

        # Must re-raise IntegrityError and NOT catch and map to ConflictError
        with pytest.raises(IntegrityError):
            await service.add_or_update_member(
                pid, MemberAddRequest(user_id=u2_id, role="ENGINEER")
            )
