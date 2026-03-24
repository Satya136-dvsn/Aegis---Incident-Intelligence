"""
Aegis Backend — Pydantic Schemas for Ingestion & Incident API

Request/response schemas for the ingestion endpoints (Phase 3)
and incident management endpoints. Separate from the base
response envelopes in schemas.py.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field, field_validator


# ── Enums (mirroring SQLAlchemy models) ───────────────────────────────


class SeverityEnum(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class StatusEnum(str, Enum):
    OPEN = "open"
    IN_PROGRESS = "in-progress"
    RESOLVED = "resolved"
    CLOSED = "closed"


class LogLevelEnum(str, Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


# ── Metric Schemas ────────────────────────────────────────────────────


class MetricIn(BaseModel):
    """Payload for POST /api/v1/metrics (Req 1)."""

    service_name: str = Field(..., min_length=1, max_length=100)
    metric_type: str = Field(..., min_length=1, max_length=50)
    value: float
    timestamp: datetime | None = None
    is_anomaly: bool = False

    model_config = {"extra": "forbid"}


class MetricOut(BaseModel):
    """Response body for a persisted metric."""

    id: int
    service_name: str
    metric_type: str
    value: float
    timestamp: datetime
    is_anomaly: bool
    rolling_mean: float | None = None
    rolling_std: float | None = None

    model_config = {"from_attributes": True}


# ── Log Schemas ───────────────────────────────────────────────────────


class LogIn(BaseModel):
    """Payload for POST /api/v1/logs (Req 2)."""

    service_name: str = Field(..., min_length=1, max_length=100)
    level: LogLevelEnum
    message: str = Field(..., min_length=1, max_length=5000)
    timestamp: datetime | None = None
    metadata: dict | None = Field(None, description="Optional structured context")

    model_config = {"extra": "forbid"}


class LogOut(BaseModel):
    """Response body for a persisted log record."""

    id: int
    service_name: str
    level: LogLevelEnum
    message: str
    timestamp: datetime

    model_config = {"from_attributes": True}


# ── Incident Schemas ──────────────────────────────────────────────────


class IncidentCreate(BaseModel):
    """Payload for creating a new incident (Req 7)."""

    title: str = Field(..., min_length=1, max_length=100)
    description: str = Field(..., min_length=1, max_length=2000)
    severity: SeverityEnum
    category: str = Field(default="Other", max_length=50)
    reporter_uid: str = Field(..., min_length=1, max_length=128)
    reporter_name: str = Field(..., min_length=1, max_length=100)

    model_config = {"extra": "forbid"}


class IncidentUpdate(BaseModel):
    """Payload for updating an existing incident."""

    title: str | None = Field(None, min_length=1, max_length=100)
    description: str | None = Field(None, min_length=1, max_length=2000)
    severity: SeverityEnum | None = None
    status: StatusEnum | None = None
    category: str | None = Field(None, max_length=50)
    rca_summary: str | None = None
    probable_cause: str | None = None

    model_config = {"extra": "forbid"}


class IncidentOut(BaseModel):
    """Response body for an incident."""

    id: int
    title: str
    description: str
    severity: SeverityEnum
    status: StatusEnum
    category: str
    reporter_uid: str
    reporter_name: str
    rca_summary: str | None = None
    probable_cause: str | None = None
    created_at: datetime
    updated_at: datetime
    comment_count: int = 0

    model_config = {"from_attributes": True}


# ── Comment Schemas ───────────────────────────────────────────────────


class CommentCreate(BaseModel):
    """Payload for adding a comment to an incident."""

    text: str = Field(..., min_length=1, max_length=1000)
    author_uid: str = Field(..., min_length=1, max_length=128)
    author_name: str = Field(..., min_length=1, max_length=100)

    model_config = {"extra": "forbid"}


class CommentOut(BaseModel):
    """Response body for a comment."""

    id: int
    incident_id: int
    text: str
    author_uid: str
    author_name: str
    created_at: datetime

    model_config = {"from_attributes": True}
