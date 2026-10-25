"""Project and Membership repositories for database operations conforming to D05 and D06."""

import uuid
from collections.abc import Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from logpilot_api.modules.projects.models import Project, ProjectMembership
from logpilot_api.modules.projects.schemas import ProjectCreate


class ProjectRepository:
    """Repository handling project persistence and querying."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, project_id: uuid.UUID) -> Project | None:
        """Fetch project by primary key ID."""
        stmt = select(Project).where(Project.id == project_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_id_for_update(self, project_id: uuid.UUID) -> Project | None:
        """Fetch project by ID acquiring a pessimistic row lock (SELECT ... FOR UPDATE)."""
        stmt = select(Project).where(Project.id == project_id).with_for_update()
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_slug(self, slug: str) -> Project | None:
        """Fetch project by unique slug."""
        stmt = select(Project).where(Project.slug == slug)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def create(self, data: ProjectCreate) -> Project:
        """Persist a new project entity."""
        project = Project(
            name=data.name,
            slug=data.slug,
            description=data.description,
        )
        self.session.add(project)
        await self.session.flush()
        return project

    async def list_user_projects(self, user_id: uuid.UUID) -> Sequence[tuple[Project, str]]:
        """List all projects where the specified user holds an active membership."""
        stmt = (
            select(Project, ProjectMembership.role)
            .join(ProjectMembership, ProjectMembership.project_id == Project.id)
            .where(ProjectMembership.user_id == user_id)
            .order_by(Project.created_at.desc())
        )
        result = await self.session.execute(stmt)
        return result.tuples().all()


class ProjectMembershipRepository:
    """Repository handling project membership and authorization queries."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_membership(
        self, project_id: uuid.UUID, user_id: uuid.UUID
    ) -> ProjectMembership | None:
        """Query membership record for a specific user and project."""
        stmt = select(ProjectMembership).where(
            ProjectMembership.project_id == project_id,
            ProjectMembership.user_id == user_id,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_members(self, project_id: uuid.UUID) -> Sequence[ProjectMembership]:
        """List all member records for a project, eagerly loading user details."""
        stmt = (
            select(ProjectMembership)
            .options(selectinload(ProjectMembership.user))
            .where(ProjectMembership.project_id == project_id)
            .order_by(ProjectMembership.created_at.asc())
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def create_membership(
        self, project_id: uuid.UUID, user_id: uuid.UUID, role: str
    ) -> ProjectMembership:
        """Create a new project membership record."""
        membership = ProjectMembership(
            project_id=project_id,
            user_id=user_id,
            role=role,
        )
        self.session.add(membership)
        await self.session.flush()
        return membership

    async def upsert_membership(
        self, project_id: uuid.UUID, user_id: uuid.UUID, role: str
    ) -> ProjectMembership:
        """Add a member or update their existing role."""
        membership = await self.get_membership(project_id, user_id)
        if membership:
            membership.role = role
        else:
            membership = ProjectMembership(
                project_id=project_id,
                user_id=user_id,
                role=role,
            )
            self.session.add(membership)
        await self.session.flush()
        return membership

    async def count_owners(self, project_id: uuid.UUID) -> int:
        """Count the number of active OWNER memberships in a project."""
        stmt = select(func.count(ProjectMembership.id)).where(
            ProjectMembership.project_id == project_id,
            ProjectMembership.role == "OWNER",
        )
        result = await self.session.execute(stmt)
        return int(result.scalar_one() or 0)

    async def delete_membership(self, project_id: uuid.UUID, user_id: uuid.UUID) -> bool:
        """Delete a membership record by project_id and user_id."""
        membership = await self.get_membership(project_id, user_id)
        if not membership:
            return False
        await self.session.delete(membership)
        await self.session.flush()
        return True
