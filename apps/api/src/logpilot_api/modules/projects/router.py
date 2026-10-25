"""Project API endpoints conforming to D06 § 7.2."""

import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from logpilot_api.api.deps import (
    get_current_user,
    get_session,
    require_project_member,
    require_project_owner,
)
from logpilot_api.core.errors import NotFoundError
from logpilot_api.modules.identity.models import User
from logpilot_api.modules.projects.models import ProjectMembership
from logpilot_api.modules.projects.schemas import (
    MemberAddRequest,
    MemberResponse,
    ProjectCreate,
    ProjectResponse,
    ProjectWithRoleResponse,
)
from logpilot_api.modules.projects.service import ProjectService

router = APIRouter(prefix="/api/v1/projects", tags=["Projects"])


@router.post(
    "",
    response_model=ProjectResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new workspace project",
)
async def create_project(
    payload: ProjectCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> ProjectResponse:
    """Create a new project and atomically assign the creator as OWNER (D06 § 7.2)."""
    service = ProjectService(session)
    project = await service.create_project_with_owner(payload, current_user.id)
    return ProjectResponse.model_validate(project)


@router.get(
    "",
    response_model=list[ProjectWithRoleResponse],
    status_code=status.HTTP_200_OK,
    summary="List projects where the user holds membership",
)
async def list_projects(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[ProjectWithRoleResponse]:
    """List all projects where the authenticated caller holds membership (D06 § 7.2)."""
    service = ProjectService(session)
    projects_with_roles = await service.list_user_projects(current_user.id)
    return [
        ProjectWithRoleResponse(
            id=p.id,
            name=p.name,
            slug=p.slug,
            description=p.description,
            created_at=p.created_at,
            updated_at=p.updated_at,
            role=role,
        )
        for p, role in projects_with_roles
    ]


@router.get(
    "/{project_id}",
    response_model=ProjectResponse,
    summary="Retrieve project details",
)
async def get_project(
    project_id: uuid.UUID,
    _membership: ProjectMembership = Depends(require_project_member),
    session: AsyncSession = Depends(get_session),
) -> ProjectResponse:
    """Retrieve project details by ID with membership check (D06 § 7.2)."""
    service = ProjectService(session)
    project = await service.get_project_by_id(project_id)
    if not project:
        raise NotFoundError("The requested project was not found.")
    return ProjectResponse.model_validate(project)


@router.get(
    "/{project_id}/members",
    response_model=list[MemberResponse],
    summary="List project members and their assigned roles",
)
async def list_project_members(
    project_id: uuid.UUID,
    _membership: ProjectMembership = Depends(require_project_member),
    session: AsyncSession = Depends(get_session),
) -> list[MemberResponse]:
    """List members and their assigned roles in the project (D06 § 7.2)."""
    service = ProjectService(session)
    return await service.list_project_members(project_id)


@router.post(
    "/{project_id}/members",
    response_model=MemberResponse,
    status_code=status.HTTP_200_OK,
    summary="Add a user or update their role in the project",
)
async def add_or_update_member(
    project_id: uuid.UUID,
    payload: MemberAddRequest,
    _membership: ProjectMembership = Depends(require_project_owner),
    session: AsyncSession = Depends(get_session),
) -> MemberResponse:
    """Add a member or update role, strictly requiring OWNER authorization (D06 § 7.2)."""
    service = ProjectService(session)
    return await service.add_or_update_member(project_id, payload)


@router.delete(
    "/{project_id}/members/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove a member from the project",
)
async def remove_member(
    project_id: uuid.UUID,
    user_id: uuid.UUID,
    _membership: ProjectMembership = Depends(require_project_owner),
    session: AsyncSession = Depends(get_session),
) -> None:
    """Remove a project member, strictly requiring OWNER authorization (D06 § 7.2)."""
    service = ProjectService(session)
    await service.remove_member(project_id, user_id)
