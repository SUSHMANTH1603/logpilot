"""Pydantic schemas for Project domain operations conforming to D06 § 7.2."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ProjectCreate(BaseModel):
    """Payload schema for creating a project."""

    name: str = Field(..., min_length=1, max_length=255, description="Project human-readable name")
    slug: str = Field(
        ..., min_length=1, max_length=100, pattern=r"^[a-z0-9-]+$", description="URL-safe slug"
    )
    description: str | None = Field(default=None, description="Optional workspace description")


class ProjectResponse(BaseModel):
    """Response schema for project details."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    slug: str
    description: str | None
    created_at: datetime
    updated_at: datetime
