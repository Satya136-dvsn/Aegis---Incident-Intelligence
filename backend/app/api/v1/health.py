"""
Aegis Backend — Health & Diagnostics Endpoint

Provides /api/v1/health with detailed component status checks.
Components (DB, Redis, LLM) return placeholder status in Phase 1;
real checks are wired in during subsequent phases.
"""

from __future__ import annotations

import time

import structlog
from fastapi import APIRouter, Request

from app.config import get_settings
from app.schemas import ComponentHealth, DataResponse, HealthResponse, ResponseMeta

logger = structlog.get_logger(__name__)
router = APIRouter()

# ── Module-level start time for uptime calculation ────────────────────
_START_TIME = time.time()


@router.get(
    "/health",
    response_model=DataResponse[HealthResponse],
    summary="System Health Check",
    description="Returns detailed status of all Aegis subsystems.",
    tags=["Diagnostics"],
)
async def health_check(request: Request) -> DataResponse[HealthResponse]:
    """
    Diagnostic endpoint returning:
    - Overall system status
    - App version and uptime
    - Component-level health (DB, Redis, LLM — placeholders for now)
    """
    settings = get_settings()
    request_id = request.headers.get("X-Request-ID", "unknown")

    components: list[ComponentHealth] = []

    # ── Database check (placeholder — wired in Phase 2) ───────────
    components.append(
        ComponentHealth(
            name="database",
            status="not_configured",
            message="PostgreSQL integration pending (Phase 2)",
        )
    )

    # ── Redis check (placeholder — wired in Phase 4) ──────────────
    components.append(
        ComponentHealth(
            name="redis",
            status="not_configured",
            message="Redis integration pending (Phase 4)",
        )
    )

    # ── LLM Provider check ────────────────────────────────────────
    llm_status = "not_configured"
    llm_message = "No API key configured"
    if settings.RCA_PROVIDER == "gemini" and settings.GEMINI_API_KEY:
        llm_status = "ok"
        llm_message = "Gemini API key present"
    elif settings.RCA_PROVIDER == "openai" and settings.OPENAI_API_KEY:
        llm_status = "ok"
        llm_message = "OpenAI API key present"

    components.append(
        ComponentHealth(
            name="llm_provider",
            status=llm_status,
            message=f"{settings.RCA_PROVIDER}: {llm_message}",
        )
    )

    # ── Aggregate status ──────────────────────────────────────────
    critical_components = [c for c in components if c.status == "down"]
    degraded_components = [c for c in components if c.status == "degraded"]

    if critical_components:
        overall = "down"
    elif degraded_components:
        overall = "degraded"
    else:
        overall = "ok"

    health = HealthResponse(
        status=overall,
        version=settings.APP_VERSION,
        uptime_seconds=round(time.time() - _START_TIME, 2),
        environment="development" if settings.DEBUG else "production",
        components=components,
    )

    await logger.ainfo("health_check", status=overall)

    return DataResponse(
        data=health,
        meta=ResponseMeta(request_id=request_id, version=settings.APP_VERSION),
    )
