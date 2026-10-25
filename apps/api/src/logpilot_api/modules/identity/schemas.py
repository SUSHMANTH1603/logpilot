"""Pydantic schemas for user registration, authentication, and token exchange."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class UserRegisterRequest(BaseModel):
    """Payload for user self-registration."""

    email: str = Field(..., description="User login email address")
    password: str = Field(
        ..., min_length=8, max_length=128, description="User password (8-128 chars)"
    )
    full_name: str = Field(..., min_length=1, max_length=255, description="User display name")

    @field_validator("email")
    @classmethod
    def normalize_email(cls, v: str) -> str:
        trimmed = v.strip().lower()
        if not trimmed or "@" not in trimmed:
            raise ValueError("Invalid email format.")
        return trimmed

    @field_validator("full_name")
    @classmethod
    def strip_full_name(cls, v: str) -> str:
        trimmed = v.strip()
        if not trimmed:
            raise ValueError("full_name cannot be empty.")
        return trimmed


class UserLoginRequest(BaseModel):
    """Payload for user authentication / login."""

    email: str = Field(..., description="User login email address")
    password: str = Field(..., min_length=1, description="User password")

    @field_validator("email")
    @classmethod
    def normalize_email(cls, v: str) -> str:
        trimmed = v.strip().lower()
        if not trimmed:
            raise ValueError("email cannot be empty.")
        return trimmed


class UserResponse(BaseModel):
    """Public user profile response (never returns password or hash)."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    full_name: str
    is_active: bool
    created_at: datetime
    updated_at: datetime


class TokenResponse(BaseModel):
    """Response envelope for successful authentication."""

    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserResponse
