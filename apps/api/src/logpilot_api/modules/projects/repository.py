"""Project repository for database operations conforming to D05 § 8.2 and D06 § 7.2."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from logpilot_api.modules.projects.models import Project
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
