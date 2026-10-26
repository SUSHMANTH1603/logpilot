"""Pydantic schemas for incidents conforming to D06 § 7.5."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from logpilot_api.modules.incidents.models import IncidentSeverity, IncidentState


class IncidentStateUpdate(BaseModel):
    """Payload to transition incident state."""

    state: IncidentState
    reason: str | None = Field(default=None, max_length=500)


class IncidentEventResponse(BaseModel):
    """Schema representing an incident log event association."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    incident_id: uuid.UUID
    project_id: uuid.UUID
    log_event_id: uuid.UUID
    event_role: str
    linked_at: datetime


class IncidentResponse(BaseModel):
    """Schema representing an incident."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    incident_number: str
    title: str
    state: IncidentState
    severity: IncidentSeverity
    window_start: datetime
    window_end: datetime
    detected_at: datetime
    resolved_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    events_count: int = 0


class PaginatedIncidentList(BaseModel):
    """Paginated collection of incidents."""

    items: list[IncidentResponse]
    total: int
    page: int
    page_size: int


class PaginatedIncidentEventList(BaseModel):
    """Paginated collection of linked incident events."""

    items: list[IncidentEventResponse]
    total: int
    page: int
    page_size: int
