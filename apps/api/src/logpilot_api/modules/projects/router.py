"""Project API endpoints conforming to D06 § 7.2."""

import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from logpilot_api.api.deps import get_session, verify_bearer_token
from logpilot_api.core.errors import ConflictError, NotFoundError
from logpilot_api.modules.projects.repository import ProjectRepository
from logpilot_api.modules.projects.schemas import ProjectCreate, ProjectResponse

router = APIRouter(prefix="/api/v1/projects", tags=["Projects"])


@router.post(
    "",
    response_model=ProjectResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new workspace project",
)
async def create_project(
    payload: ProjectCreate,
    _token: str = Depends(verify_bearer_token),
    session: AsyncSession = Depends(get_session),
) -> ProjectResponse:
    """Create a new isolated workspace project (D06 § 7.2)."""
    repo = ProjectRepository(session)
    existing = await repo.get_by_slug(payload.slug)
    if existing:
        raise ConflictError(f"Project with slug '{payload.slug}' already exists.")

    project = await repo.create(payload)
    return ProjectResponse.model_validate(project)


@router.get(
    "/{project_id}",
    response_model=ProjectResponse,
    summary="Retrieve project details",
)
async def get_project(
    project_id: uuid.UUID,
    _token: str = Depends(verify_bearer_token),
    session: AsyncSession = Depends(get_session),
) -> ProjectResponse:
    """Retrieve project details by ID (D06 § 7.2)."""
    repo = ProjectRepository(session)
    project = await repo.get_by_id(project_id)
    if not project:
        raise NotFoundError(f"Project '{project_id}' not found.")
    return ProjectResponse.model_validate(project)
