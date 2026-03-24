"""
Aegis Backend — Metrics Ingestion API

Endpoints for receiving high-throughput telemetry data from microservices.
"""

from __future__ import annotations

import structlog
from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app import repository
from app.api.schemas import MetricIn
from app.config import get_settings
from app.database import get_db
from app.schemas import DataResponse, ResponseMeta

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/metrics", tags=["Metrics Ingestion"])


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=DataResponse[list[int]],
    summary="Ingest custom metrics",
)
async def ingest_metrics(
    request: Request,
    payload: MetricIn | list[MetricIn],
    db: AsyncSession = Depends(get_db),
) -> DataResponse[list[int]]:
    """
    Ingest one or multiple metric data points.
    
    This endpoint is designed for downstream applications to push time-series data
    (CPU usage, error rates, queue lengths) into Aegis for real-time monitoring
    and anomaly detection.
    """
    settings = get_settings()
    request_id = request.headers.get("X-Request-ID", getattr(request.state, "request_id", "unknown"))

    metrics_data = (
        [payload.model_dump()] if isinstance(payload, MetricIn) 
        else [m.model_dump() for m in payload]
    )

    records = await repository.create_metrics_batch(db, metrics_data)
    await db.commit()

    # Trigger background anomaly detection task
    # We pass the IDs so the worker can fetch the fresh records
    from app.tasks import process_metric_batch
    from app.api.v1.stream import manager
    record_ids = [r.id for r in records] # type: ignore
    process_metric_batch.delay(record_ids)

    # Broadcast to WebSocket
    # We use await asyncio.shield or just await directly
    for r in records:
        await manager.broadcast("new_metric", {
            "id": r.id,
            "service_name": r.service_name,
            "metric_type": r.metric_type,
            "value": r.value,
            "timestamp": r.timestamp.isoformat()
        })

    await logger.ainfo(
        "metrics_ingested",
        count=len(records),
        request_id=request_id,
        services=list({r.service_name for r in records}),
    )

    return DataResponse(
        data=record_ids,
        meta=ResponseMeta(request_id=request_id, version=settings.APP_VERSION),
        message=f"Successfully ingested {len(records)} metric(s)",
    )
