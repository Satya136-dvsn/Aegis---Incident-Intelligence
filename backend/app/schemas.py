"""
Aegis Backend — Standardized API Response Schemas

Every API response is wrapped in one of these envelopes to ensure
consistent, predictable JSON structures across the entire platform.

Success → DataResponse[T]
Error   → ErrorResponse
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


# ── Meta ──────────────────────────────────────────────────────────────


class ResponseMeta(BaseModel):
    """Metadata attached to every successful response."""

    request_id: str = Field(..., description="Unique ID for distributed tracing")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Server UTC timestamp",
    )
    version: str = Field(default="2.0.0", description="API version")


# ── Success ───────────────────────────────────────────────────────────


class DataResponse(BaseModel, Generic[T]):
    """Standard success envelope wrapping any payload type *T*."""

    data: T
    meta: ResponseMeta
    message: str | None = None


# ── Error ─────────────────────────────────────────────────────────────


class ErrorDetail(BaseModel):
    """Individual error detail for structured error reporting."""

    field: str | None = None
    message: str
    code: str | None = None


class ErrorResponse(BaseModel):
    """Standard error envelope returned for all 4xx / 5xx responses."""

    error: str = Field(..., description="Machine-readable error code")
    message: str = Field(..., description="Human-readable description")
    details: list[ErrorDetail] = Field(default_factory=list)
    meta: ResponseMeta


# ── Health ────────────────────────────────────────────────────────────


class ComponentHealth(BaseModel):
    """Health status for a single system component."""

    name: str
    status: str = Field(description="'ok' | 'degraded' | 'down'")
    latency_ms: float | None = None
    message: str | None = None


class HealthResponse(BaseModel):
    """Diagnostic payload returned by the /health endpoint."""

    status: str = Field(description="'ok' | 'degraded' | 'down'")
    version: str
    uptime_seconds: float
    environment: str
    components: list[ComponentHealth] = Field(default_factory=list)


# ── Pagination (for future list endpoints) ────────────────────────────


class PaginationMeta(BaseModel):
    """Pagination metadata for list endpoints."""

    page: int = 1
    per_page: int = 50
    total_items: int = 0
    total_pages: int = 0
