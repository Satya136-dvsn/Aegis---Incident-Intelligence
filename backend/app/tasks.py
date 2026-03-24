"""
Aegis Backend — Background Tasks

Defines Celery tasks for:
- process_metric_batch: Anomaly detection on incoming metrics
- trigger_incident: Raising high-priority incidents asynchronously
"""

from __future__ import annotations

import asyncio
import uuid
import structlog
from datetime import datetime, timezone

from pydantic import ValidationError

from app.worker import celery_app
from app.api.schemas import SeverityEnum
from app.database import async_session
from app.models import MetricRecord, IncidentStatus

logger = structlog.get_logger(__name__)


def run_async(coro):
    """Utility to run async functions synchronously in Celery tasks."""
    loop = asyncio.get_event_loop()
    if loop.is_running():
        import nest_asyncio
        nest_asyncio.apply()
    return asyncio.run(coro)


@celery_app.task(bind=True, name="app.tasks.process_metric_batch", max_retries=3)
def process_metric_batch(self, metric_ids: list[int]) -> dict:
    """
    Process newly ingested metrics to detect anomalies using 2σ rolling deviation.
    Because Celery is synchronous, we use asyncio.run to call our async DB logic,
    or we can use synchronous SQLAlchemy sessions. Here we use an async wrap.
    """
    return run_async(_process_metric_batch_async(metric_ids))


async def _process_metric_batch_async(metric_ids: list[int]) -> dict:
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import AsyncSession
    from app import repository

    if not metric_ids:
        return {"processed": 0, "anomalies": 0}

    async with async_session() as db:
        # 1. Fetch the metrics
        result = await db.execute(
            select(MetricRecord).where(MetricRecord.id.in_(metric_ids))
        )
        metrics = result.scalars().all()
        
        anomalies_detected = []

        for metric in metrics:
            # 2. Get rolling stats (last 50 data points for this service + type)
            # In a production system, this would use Redis for fast sliding windows.
            # Here we do a basic DB query for simplicity in MVP.
            recent_query = await db.execute(
                select(MetricRecord)
                .where(
                    MetricRecord.service_name == metric.service_name,
                    MetricRecord.metric_type == metric.metric_type,
                    MetricRecord.id < metric.id
                )
                .order_by(MetricRecord.timestamp.desc())
                .limit(50)
            )
            recent_metrics = recent_query.scalars().all()

            if len(recent_metrics) >= 10:  # Minimum sample size
                values = [m.value for m in recent_metrics]
                mean = sum(values) / len(values)
                variance = sum((x - mean) ** 2 for x in values) / len(values)
                std_dev = variance ** 0.5
                
                # Update rolling stats on the current metric
                metric.rolling_mean = mean
                metric.rolling_std = std_dev
                
                # 3. Check for anomaly (value > mean + 2 std_dev)
                # Ensure std_dev is non-zero to avoid hypersensitivity on static metrics
                threshold = mean + (2 * max(std_dev, 0.01 * mean, 0.1))
                if metric.value > threshold:
                    metric.is_anomaly = True
                    anomalies_detected.append(metric)
                    await logger.ainfo(
                        "anomaly_detected",
                        service=metric.service_name,
                        type=metric.metric_type,
                        value=metric.value,
                        threshold=threshold
                    )

        await db.commit()

        # 4. Trigger incidents for anomalies
        for anomaly in anomalies_detected:
            # Dispatch another task to handle incident creation to decouple failure domains
            trigger_incident.delay(
                service_name=anomaly.service_name,
                metric_type=anomaly.metric_type,
                value=anomaly.value,
                metric_id=anomaly.id
            )

        return {"processed": len(metrics), "anomalies": len(anomalies_detected)}


@celery_app.task(bind=True, name="app.tasks.trigger_incident", max_retries=3)
def trigger_incident(self, service_name: str, metric_type: str, value: float, metric_id: int) -> int | None:
    """Create an incident automatically when an automated anomaly is detected."""
    return run_async(_trigger_incident_async(service_name, metric_type, value, metric_id))


async def _trigger_incident_async(service_name: str, metric_type: str, value: float, metric_id: int) -> int | None:
    from app import repository
    from sqlalchemy.ext.asyncio import AsyncSession
    
    async with async_session() as db:
        title = f"Anomaly: {service_name} {metric_type} spike"
        description = (
            f"Automated detection triggered by metric ID {metric_id}.\n"
            f"Service: {service_name}\n"
            f"Metric: {metric_type}\n"
            f"Value: {value}\n"
            "This exceeded the dynamic 2σ rolling threshold."
        )

        incident = await repository.create_incident(
            db,
            title=title,
            description=description,
            severity=SeverityEnum.HIGH,
            reporter_uid="system",
            reporter_name="Aegis Anomaly Engine",
            category="Performance",
        )
        await db.commit()
        
        await logger.ainfo(
            "incident_auto_created",
            incident_id=incident.id,
            service=service_name,
            metric=metric_type
        )
        return incident.id
