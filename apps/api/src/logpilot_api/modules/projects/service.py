"""Project service orchestrating atomic project creation and membership governance."""

import uuid

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from logpilot_api.core.errors import ConflictError, NotFoundError
from logpilot_api.modules.identity.repository import UserRepository
from logpilot_api.modules.projects.models import Project
from logpilot_api.modules.projects.repository import ProjectMembershipRepository, ProjectRepository
from logpilot_api.modules.projects.schemas import MemberAddRequest, MemberResponse, ProjectCreate


def _is_membership_unique_violation(exc: IntegrityError) -> bool:
    """Detect if an IntegrityError stems from uq_project_memberships_project_id_user_id."""
    orig = getattr(exc, "orig", None)
    if orig is not None:
        constraint = getattr(orig, "constraint_name", None)
        if constraint == "uq_project_memberships_project_id_user_id":
            return True
        pgcode = getattr(orig, "pgcode", None)
        if pgcode is not None and pgcode != "23505":
            return False

    err_str = (str(orig) if orig else str(exc)).lower()
    has_constraint_name = "uq_project_memberships_project_id_user_id" in err_str
    has_sqlite_unique = (
        "unique constraint failed" in err_str
        and "project_memberships.project_id" in err_str
        and "project_memberships.user_id" in err_str
    )
    return has_constraint_name or has_sqlite_unique


class ProjectService:
    """Service handling project lifecycle and team membership."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.project_repo = ProjectRepository(session)
        self.member_repo = ProjectMembershipRepository(session)
        self.user_repo = UserRepository(session)

    async def create_project_with_owner(
        self, payload: ProjectCreate, creator_user_id: uuid.UUID
    ) -> Project:
        """Atomically create a project and assign the creator as OWNER in a single transaction."""
        existing = await self.project_repo.get_by_slug(payload.slug)
        if existing:
            raise ConflictError(f"Project with slug '{payload.slug}' already exists.")

        try:
            project = await self.project_repo.create(payload)
            await self.member_repo.create_membership(
                project_id=project.id,
                user_id=creator_user_id,
                role="OWNER",
            )
            await self.session.commit()
            return project
        except IntegrityError as exc:
            await self.session.rollback()
            err_msg = (
                str(exc.orig).lower() if hasattr(exc, "orig") and exc.orig else str(exc).lower()
            )
            if "uq_projects_slug" in err_msg or "projects.slug" in err_msg or "slug" in err_msg:
                raise ConflictError(
                    message=f"Project with slug '{payload.slug}' already exists.",
                    code="CONFLICT",
                ) from exc
            raise
        except Exception:
            await self.session.rollback()
            raise

    async def list_user_projects(self, user_id: uuid.UUID) -> list[tuple[Project, str]]:
        """List all projects where the specified user holds membership."""
        results = await self.project_repo.list_user_projects(user_id)
        return list(results)

    async def get_project_by_id(self, project_id: uuid.UUID) -> Project | None:
        """Fetch project details by ID."""
        return await self.project_repo.get_by_id(project_id)

    async def list_project_members(self, project_id: uuid.UUID) -> list[MemberResponse]:
        """List all members for a project with user email and display name."""
        memberships = await self.member_repo.list_members(project_id)
        return [
            MemberResponse(
                user_id=m.user_id,
                email=m.user.email,
                full_name=m.user.full_name,
                role=m.role,
                joined_at=m.created_at,
            )
            for m in memberships
        ]

    async def add_or_update_member(
        self, project_id: uuid.UUID, payload: MemberAddRequest
    ) -> MemberResponse:
        """Add a user to the project or update an existing member's role."""
        # 1. Serialize ownership-affecting mutations per project using row lock on Project
        project = await self.project_repo.get_by_id_for_update(project_id)
        if not project:
            raise NotFoundError(f"Project '{project_id}' not found.")

        target_user = await self.user_repo.get_by_id(payload.user_id)
        if not target_user:
            raise NotFoundError(f"User '{payload.user_id}' not found.")

        target_user_id = target_user.id
        target_user_email = target_user.email
        target_user_name = target_user.full_name

        # 2. Check if updating an existing OWNER to a non-OWNER role under lock
        existing_membership = await self.member_repo.get_membership(project_id, payload.user_id)
        if existing_membership and existing_membership.role == "OWNER" and payload.role != "OWNER":
            owner_count = await self.member_repo.count_owners(project_id)
            if owner_count <= 1:
                raise ConflictError(
                    message="Cannot demote the sole project OWNER.",
                    code="CONFLICT",
                )

        try:
            membership = await self.member_repo.upsert_membership(
                project_id=project_id,
                user_id=payload.user_id,
                role=payload.role,
            )
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            if _is_membership_unique_violation(exc):
                # Re-acquire project lock in post-rollback transaction to preserve serialization
                await self.project_repo.get_by_id_for_update(project_id)
                membership = await self.member_repo.get_membership(project_id, payload.user_id)
                if membership:
                    if membership.role != payload.role:
                        if membership.role == "OWNER" and payload.role != "OWNER":
                            owner_count = await self.member_repo.count_owners(project_id)
                            if owner_count <= 1:
                                raise ConflictError(
                                    message="Cannot demote the sole project OWNER.",
                                    code="CONFLICT",
                                ) from exc
                        membership.role = payload.role
                        await self.session.commit()
                else:
                    raise ConflictError(
                        message="Membership conflict occurred.",
                        code="CONFLICT",
                    ) from exc
            else:
                raise

        return MemberResponse(
            user_id=target_user_id,
            email=target_user_email,
            full_name=target_user_name,
            role=membership.role,
            joined_at=membership.created_at,
        )

    async def remove_member(self, project_id: uuid.UUID, user_id: uuid.UUID) -> None:
        """Remove a user from the project, preventing removal of the sole OWNER."""
        # Serialize ownership-affecting mutations per project using row lock on Project
        project = await self.project_repo.get_by_id_for_update(project_id)
        if not project:
            raise NotFoundError(f"Project '{project_id}' not found.")

        membership = await self.member_repo.get_membership(project_id, user_id)
        if not membership:
            raise NotFoundError(f"Member with user ID '{user_id}' not found in project.")

        if membership.role == "OWNER":
            owner_count = await self.member_repo.count_owners(project_id)
            if owner_count <= 1:
                raise ConflictError(
                    message="Cannot remove the sole project OWNER.",
                    code="CONFLICT",
                )

        await self.member_repo.delete_membership(project_id, user_id)
        await self.session.commit()
