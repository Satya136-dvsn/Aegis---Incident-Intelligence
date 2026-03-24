"""
Aegis Backend — Data Access Repository

Provides typed, async CRUD operations for all models.
Centralizes DB access patterns, error handling, and query construction.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Sequence

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Comment, Incident, IncidentStatus, LogRecord, MetricRecord, Severity

logger = structlog.get_logger(__name__)


# ── Metrics ───────────────────────────────────────────────────────────


async def create_metric(db: AsyncSession, **kwargs) -> MetricRecord:
    """Persist a single metric data point."""
    if "timestamp" not in kwargs or kwargs["timestamp"] is None:
        kwargs["timestamp"] = datetime.now(timezone.utc)
    record = MetricRecord(**kwargs)
    db.add(record)
    await db.flush()
    await db.refresh(record)
    return record


async def create_metrics_batch(
    db: AsyncSession, metrics: list[dict]
) -> list[MetricRecord]:
    """Persist a batch of metric data points."""
    now = datetime.now(timezone.utc)
    records = []
    for m in metrics:
        if "timestamp" not in m or m["timestamp"] is None:
            m["timestamp"] = now
        records.append(MetricRecord(**m))
    db.add_all(records)
    await db.flush()
    for r in records:
        await db.refresh(r)
    return records


async def get_recent_metrics(
    db: AsyncSession,
    service_name: str | None = None,
    metric_type: str | None = None,
    limit: int = 100,
) -> Sequence[MetricRecord]:
    """Retrieve recent metrics, optionally filtered by service or type."""
    stmt = select(MetricRecord).order_by(MetricRecord.timestamp.desc()).limit(limit)
    if service_name:
        stmt = stmt.where(MetricRecord.service_name == service_name)
    if metric_type:
        stmt = stmt.where(MetricRecord.metric_type == metric_type)
    result = await db.execute(stmt)
    return result.scalars().all()


# ── Logs ──────────────────────────────────────────────────────────────


async def create_log(db: AsyncSession, **kwargs) -> LogRecord:
    """Persist a single log event."""
    if "timestamp" not in kwargs or kwargs["timestamp"] is None:
        kwargs["timestamp"] = datetime.now(timezone.utc)
    record = LogRecord(**kwargs)
    db.add(record)
    await db.flush()
    await db.refresh(record)
    return record


async def get_recent_logs(
    db: AsyncSession,
    service_name: str | None = None,
    level: str | None = None,
    limit: int = 100,
) -> Sequence[LogRecord]:
    """Retrieve recent logs, optionally filtered."""
    stmt = select(LogRecord).order_by(LogRecord.timestamp.desc()).limit(limit)
    if service_name:
        stmt = stmt.where(LogRecord.service_name == service_name)
    if level:
        stmt = stmt.where(LogRecord.level == level)
    result = await db.execute(stmt)
    return result.scalars().all()


# ── Incidents ─────────────────────────────────────────────────────────


async def create_incident(db: AsyncSession, **kwargs) -> Incident:
    """Create a new incident."""
    record = Incident(**kwargs)
    db.add(record)
    await db.flush()
    await db.refresh(record)
    return record


async def get_incident(db: AsyncSession, incident_id: int) -> Incident | None:
    """Retrieve a single incident by ID, with comments loaded."""
    stmt = (
        select(Incident)
        .where(Incident.id == incident_id)
        .options(selectinload(Incident.comments))
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def list_incidents(
    db: AsyncSession,
    severity: Severity | None = None,
    status: IncidentStatus | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[Sequence[Incident], int]:
    """List incidents with optional filters. Returns (incidents, total_count)."""
    stmt = select(Incident).order_by(Incident.created_at.desc())
    count_stmt = select(func.count()).select_from(Incident)

    if severity:
        stmt = stmt.where(Incident.severity == severity)
        count_stmt = count_stmt.where(Incident.severity == severity)
    if status:
        stmt = stmt.where(Incident.status == status)
        count_stmt = count_stmt.where(Incident.status == status)

    stmt = stmt.limit(limit).offset(offset)

    result = await db.execute(stmt)
    count_result = await db.execute(count_stmt)

    return result.scalars().all(), count_result.scalar_one()


async def update_incident(
    db: AsyncSession, incident_id: int, **kwargs
) -> Incident | None:
    """Update an incident's fields. Returns None if not found."""
    incident = await get_incident(db, incident_id)
    if not incident:
        return None
    for key, value in kwargs.items():
        if value is not None:
            setattr(incident, key, value)
    incident.updated_at = datetime.now(timezone.utc)
    await db.flush()
    await db.refresh(incident)
    return incident


# ── Comments ──────────────────────────────────────────────────────────


async def create_comment(
    db: AsyncSession, incident_id: int, **kwargs
) -> Comment:
    """Add a comment to an incident."""
    record = Comment(incident_id=incident_id, **kwargs)
    db.add(record)
    await db.flush()
    await db.refresh(record)
    return record


async def list_comments(
    db: AsyncSession, incident_id: int
) -> Sequence[Comment]:
    """List all comments for an incident, newest first."""
    stmt = (
        select(Comment)
        .where(Comment.incident_id == incident_id)
        .order_by(Comment.created_at.desc())
    )
    result = await db.execute(stmt)
    return result.scalars().all()
