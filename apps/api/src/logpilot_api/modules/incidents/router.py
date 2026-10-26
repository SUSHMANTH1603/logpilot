"""Incident API router conforming to D06 § 7.5."""

import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from logpilot_api.api.deps import (
    get_session,
    require_project_engineer,
    require_project_member,
)
from logpilot_api.modules.incidents.models import IncidentSeverity, IncidentState
from logpilot_api.modules.incidents.schemas import (
    IncidentEventResponse,
    IncidentResponse,
    IncidentStateUpdate,
    PaginatedIncidentEventList,
    PaginatedIncidentList,
)
from logpilot_api.modules.incidents.service import IncidentService
from logpilot_api.modules.projects.models import ProjectMembership

router = APIRouter(prefix="/api/v1/projects/{project_id}/incidents", tags=["Incidents"])


@router.get(
    "",
    response_model=PaginatedIncidentList,
    status_code=status.HTTP_200_OK,
    summary="List project incidents with filtering and pagination",
)
async def list_incidents(
    project_id: uuid.UUID,
    state: IncidentState | None = Query(default=None),
    severity: IncidentSeverity | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
    _membership: ProjectMembership = Depends(require_project_member),
    session: AsyncSession = Depends(get_session),
) -> PaginatedIncidentList:
    """List incidents within a project conforming to D06 § 7.5."""
    service = IncidentService(session)
    offset = (page - 1) * page_size
    incidents, total = await service.list_incidents(
        project_id=project_id,
        state=state.value if state else None,
        severity=severity.value if severity else None,
        limit=page_size,
        offset=offset,
    )
    items = [IncidentResponse.model_validate(inc) for inc in incidents]
    return PaginatedIncidentList(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/{incident_id}",
    response_model=IncidentResponse,
    status_code=status.HTTP_200_OK,
    summary="Get incident details",
)
async def get_incident(
    project_id: uuid.UUID,
    incident_id: uuid.UUID,
    _membership: ProjectMembership = Depends(require_project_member),
    session: AsyncSession = Depends(get_session),
) -> IncidentResponse:
    """Retrieve details for a single incident strictly scoped to project."""
    service = IncidentService(session)
    incident = await service.get_incident(project_id, incident_id)
    return IncidentResponse.model_validate(incident)


@router.get(
    "/{incident_id}/events",
    response_model=PaginatedIncidentEventList,
    status_code=status.HTTP_200_OK,
    summary="Get log events linked to an incident",
)
async def get_incident_events(
    project_id: uuid.UUID,
    incident_id: uuid.UUID,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
    _membership: ProjectMembership = Depends(require_project_member),
    session: AsyncSession = Depends(get_session),
) -> PaginatedIncidentEventList:
    """Retrieve correlated log events linked to an incident."""
    service = IncidentService(session)
    offset = (page - 1) * page_size
    events, total = await service.list_incident_events(
        project_id=project_id,
        incident_id=incident_id,
        limit=page_size,
        offset=offset,
    )
    items = [IncidentEventResponse.model_validate(ev) for ev in events]
    return PaginatedIncidentEventList(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.patch(
    "/{incident_id}/state",
    response_model=IncidentResponse,
    status_code=status.HTTP_200_OK,
    summary="Update incident lifecycle state",
)
async def update_incident_state(
    project_id: uuid.UUID,
    incident_id: uuid.UUID,
    payload: IncidentStateUpdate,
    _membership: ProjectMembership = Depends(require_project_engineer),
    session: AsyncSession = Depends(get_session),
) -> IncidentResponse:
    """Transition incident state enforcing D05 § 5 lifecycle rules."""
    service = IncidentService(session)
    updated_incident = await service.transition_state(
        project_id=project_id,
        incident_id=incident_id,
        target_state=payload.state,
    )
    await session.commit()
    return IncidentResponse.model_validate(updated_incident)
