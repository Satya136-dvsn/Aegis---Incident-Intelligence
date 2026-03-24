"""
Aegis Backend — Celery Worker App

Initializes the Celery application for background task processing.
Tasks include async anomaly detection, statistical aggregation,
and external AI summarization.
"""

from __future__ import annotations

import structlog
from celery import Celery

from app.config import get_settings

logger = structlog.get_logger(__name__)
settings = get_settings()

celery_app = Celery(
    "aegis_worker",
    broker=str(settings.REDIS_URL),
    backend=str(settings.REDIS_URL),
    include=["app.tasks"],
)

# Optional configuration
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    # In development, eager mode can be used if redis isn't available, but we'll default to normal queues
)

if __name__ == "__main__":
    celery_app.start()
