"""Pydantic schemas for Ingestion domain models conforming to D06 § 7.4 and D07."""

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class LogSourceCreate(BaseModel):
    """Payload schema for registering a new log source."""

    name: str = Field(..., min_length=1, max_length=255, description="Source identifier")
    source_type: Literal["CONTAINER", "FILE", "AGENT", "HTTP"] = Field(
        ..., description="Telemetry source type"
    )
    environment: Literal["development", "staging", "production"] = Field(
        default="production", description="Operational environment"
    )


class LogSourceResponse(BaseModel):
    """Response schema for a log source entity."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    name: str
    source_type: str
    environment: str
    is_active: bool
    created_at: datetime
    ingestion_key: str | None = Field(
        default=None,
        description="Source ingestion API key, returned only on creation (D06 § 7.4)",
    )


class LogSourceListResponse(BaseModel):
    """List response for log sources."""

    items: list[LogSourceResponse]
    total: int


class LogEventIngestItem(BaseModel):
    """Single log event entry within an ingestion batch payload."""

    timestamp: datetime = Field(..., description="Observed event timestamp (ISO 8601 UTC)")
    message: str = Field(..., min_length=1, description="Raw or formatted log message body")
    level: str = Field(default="INFO", description="Source severity level")
    attributes: dict[str, Any] = Field(default_factory=dict, description="Structured attributes")


class LogIngestRequest(BaseModel):
    """Batch payload schema for log ingestion."""

    events: list[LogEventIngestItem] = Field(
        ..., min_length=1, description="List of log event items"
    )


class LogIngestResponse(BaseModel):
    """Response schema for accepted ingestion batch."""

    ingestion_run_id: uuid.UUID
    status: str
    received_count: int
    enqueued_at: datetime


class IngestionRunResponse(BaseModel):
    """Response schema for an ingestion run."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    log_source_id: uuid.UUID
    status: str
    events_processed: int
    errors_count: int
    started_at: datetime
    completed_at: datetime | None = None
