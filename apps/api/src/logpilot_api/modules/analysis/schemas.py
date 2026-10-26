"""Pydantic schemas for anomaly signals conforming to D05 § 8.10."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class AnomalySignalResponse(BaseModel):
    """Schema representing an anomaly detection signal."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    log_source_id: uuid.UUID
    anomaly_type: str
    confidence_score: float = Field(ge=0.0, le=1.0)
    window_start: datetime
    window_end: datetime
    feature_vector: dict[str, Any] | None = None
    detected_at: datetime
