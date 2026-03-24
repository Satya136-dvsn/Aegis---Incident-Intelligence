"""
Aegis Backend — SQLAlchemy Models

Defines the relational schema for all core entities:
- MetricRecord: Time-series metric data points
- LogRecord: Structured log events
- Incident: Tracked incidents with severity and status lifecycle
- Comment: Threaded discussion per incident
"""

from __future__ import annotations

import enum
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


# ── Enums ─────────────────────────────────────────────────────────────


class Severity(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class IncidentStatus(str, enum.Enum):
    OPEN = "open"
    IN_PROGRESS = "in-progress"
    RESOLVED = "resolved"
    CLOSED = "closed"


class LogLevel(str, enum.Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


# ── Metric Record ────────────────────────────────────────────────────


class MetricRecord(Base):
    """
    Time-series metric data point ingested from monitored services.

    Maps to Req 1 (Metrics Ingestion) and Req 4 (Data Processing).
    """

    __tablename__ = "metrics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    service_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    metric_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    value: Mapped[float] = mapped_column(Float, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )
    is_anomaly: Mapped[bool] = mapped_column(Boolean, default=False)

    # Rolling stats (populated by the Processing Engine — Phase 4)
    rolling_mean: Mapped[float | None] = mapped_column(Float, nullable=True)
    rolling_std: Mapped[float | None] = mapped_column(Float, nullable=True)

    __table_args__ = (
        Index("ix_metrics_service_type_ts", "service_name", "metric_type", "timestamp"),
    )


# ── Log Record ────────────────────────────────────────────────────────


class LogRecord(Base):
    """
    Structured log event ingested from monitored services.

    Maps to Req 2 (Log Event Ingestion).
    """

    __tablename__ = "logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    service_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    level: Mapped[LogLevel] = mapped_column(Enum(LogLevel), nullable=False, index=True)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    
    from sqlalchemy import JSON
    metadata_payload: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)
    
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )

    __table_args__ = (
        Index("ix_logs_service_level_ts", "service_name", "level", "timestamp"),
    )


# ── Incident ──────────────────────────────────────────────────────────


class Incident(Base):
    """
    A tracked security or operational incident with full lifecycle.

    Maps to Req 7 (Alert & Incident Management).
    """

    __tablename__ = "incidents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[Severity] = mapped_column(Enum(Severity), nullable=False, index=True)
    status: Mapped[IncidentStatus] = mapped_column(
        Enum(IncidentStatus), nullable=False, default=IncidentStatus.OPEN, index=True
    )
    category: Mapped[str] = mapped_column(String(50), nullable=False, default="Other")
    reporter_uid: Mapped[str] = mapped_column(String(128), nullable=False)
    reporter_name: Mapped[str] = mapped_column(String(100), nullable=False)

    # AI-generated fields (populated by RCA Engine — Phase 5)
    rca_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    probable_cause: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    # Relationships
    comments: Mapped[list[Comment]] = relationship(
        "Comment", back_populates="incident", cascade="all, delete-orphan"
    )


# ── Comment ───────────────────────────────────────────────────────────


class Comment(Base):
    """
    Threaded discussion entry on an incident.

    Maps to the comment system from the design document.
    """

    __tablename__ = "comments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    incident_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    text: Mapped[str] = mapped_column(Text, nullable=False)
    author_uid: Mapped[str] = mapped_column(String(128), nullable=False)
    author_name: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    # Relationships
    incident: Mapped[Incident] = relationship("Incident", back_populates="comments")
