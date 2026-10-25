"""Pydantic schemas for Project domain operations conforming to D06 § 7.2."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


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


class ProjectWithRoleResponse(ProjectResponse):
    """Project details response including caller's assigned role."""

    role: str


class MemberAddRequest(BaseModel):
    """Payload for adding a member or updating their role."""

    user_id: uuid.UUID = Field(..., description="Target user identifier")
    role: str = Field(..., description="Assigned role: OWNER, ENGINEER, or VIEWER")

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: str) -> str:
        valid_roles = {"OWNER", "ENGINEER", "VIEWER"}
        upper = v.upper().strip()
        if upper not in valid_roles:
            raise ValueError(f"Role must be one of {valid_roles}")
        return upper


class MemberResponse(BaseModel):
    """Response schema for project member records."""

    model_config = ConfigDict(from_attributes=True)

    user_id: uuid.UUID
    email: str
    full_name: str
    role: str
    joined_at: datetime
