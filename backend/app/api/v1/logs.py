"""
Aegis Backend — Logs Ingestion API

Endpoints for receiving structured application logs.
"""

from __future__ import annotations

import structlog
from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app import repository
from app.api.schemas import LogIn
from app.config import get_settings
from app.database import get_db
from app.schemas import DataResponse, ResponseMeta

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/logs", tags=["Logs Ingestion"])


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=DataResponse[int],
    summary="Ingest service logs",
)
async def ingest_log(
    request: Request,
    payload: LogIn,
    db: AsyncSession = Depends(get_db),
) -> DataResponse[int]:
    """
    Ingest a single structured log entry.
    
    Primarily intended for critical warnings and errors from downstream services.
    These events are monitored by the Aegis anomaly engine.
    """
    settings = get_settings()
    request_id = request.headers.get("X-Request-ID", getattr(request.state, "request_id", "unknown"))

    record = await repository.create_log(
        db,
        service_name=payload.service_name,
        level=payload.level.value,
        message=payload.message,
        metadata_payload=payload.metadata,
    )
    await db.commit()

    await logger.ainfo(
        "log_ingested",
        service=record.service_name,
        level=record.level.value,
        log_id=record.id,
        request_id=request_id,
    )

    return DataResponse(
        data=record.id,  # type: ignore
        meta=ResponseMeta(request_id=request_id, version=settings.APP_VERSION),
        message="Successfully ingested log record",
    )
