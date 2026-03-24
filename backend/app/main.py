"""
Aegis Backend — FastAPI Application Factory

Creates and configures the FastAPI application with:
- CORS middleware for frontend integration
- Request-ID middleware for distributed tracing
- Global exception handlers for consistent error responses
- API router mounting under /api/v1
- Structured logging initialization
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import AsyncGenerator

import structlog
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1.health import router as health_router
from app.api.v1.logs import router as logs_router
from app.api.v1.metrics import router as metrics_router
from app.config import get_settings
from app.logging import setup_logging
from app.middleware import RequestIDMiddleware
from app.schemas import ErrorDetail, ErrorResponse, ResponseMeta

logger = structlog.get_logger(__name__)


# ── Lifespan (startup / shutdown) ─────────────────────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan: startup and shutdown hooks."""
    settings = get_settings()
    setup_logging()

    # ── Database initialization ───────────────────────────────────
    from app.database import Base, engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await logger.ainfo("database_initialized")

    await logger.ainfo(
        "aegis_starting",
        version=settings.APP_VERSION,
        debug=settings.DEBUG,
        rca_provider=settings.RCA_PROVIDER,
    )

    yield  # ← application is running

    # ── Cleanup ───────────────────────────────────────────────────
    from app.database import engine as db_engine

    await db_engine.dispose()
    await logger.ainfo("aegis_shutdown")


# ── Factory ───────────────────────────────────────────────────────────


def create_app() -> FastAPI:
    """Build and return the fully configured FastAPI application."""
    settings = get_settings()

    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description=(
            "AI-powered incident management and intelligence platform "
            "for reporting, tracking, and analyzing security & operational incidents."
        ),
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # ── Middleware (order matters: last added = first executed) ────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID", "X-Response-Time-Ms"],
    )
    app.add_middleware(RequestIDMiddleware)

    # ── Exception Handlers ────────────────────────────────────────
    _register_exception_handlers(app)

    # ── Routers ───────────────────────────────────────────────────
    app.include_router(health_router, prefix=settings.API_V1_PREFIX)
    app.include_router(metrics_router, prefix=settings.API_V1_PREFIX)
    app.include_router(logs_router, prefix=settings.API_V1_PREFIX)

    return app


# ── Exception Handlers ────────────────────────────────────────────────


def _register_exception_handlers(app: FastAPI) -> None:
    """Register global exception handlers for consistent error responses."""

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        """Convert Pydantic validation errors into our ErrorResponse envelope."""
        request_id = request.headers.get("X-Request-ID", "unknown")
        details = [
            ErrorDetail(
                field=".".join(str(loc) for loc in err.get("loc", [])),
                message=err.get("msg", "Validation error"),
                code=err.get("type"),
            )
            for err in exc.errors()
        ]
        body = ErrorResponse(
            error="VALIDATION_ERROR",
            message=f"{len(details)} validation error(s) in request",
            details=details,
            meta=ResponseMeta(request_id=request_id),
        )
        return JSONResponse(status_code=422, content=body.model_dump(mode="json"))

    @app.exception_handler(404)
    async def not_found_handler(request: Request, exc: Exception) -> JSONResponse:
        """Return a structured 404 instead of FastAPI's default HTML."""
        request_id = request.headers.get("X-Request-ID", "unknown")
        body = ErrorResponse(
            error="NOT_FOUND",
            message=f"No endpoint matches {request.method} {request.url.path}",
            meta=ResponseMeta(request_id=request_id),
        )
        return JSONResponse(status_code=404, content=body.model_dump(mode="json"))

    @app.exception_handler(500)
    async def internal_error_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        """Catch-all for unhandled server errors."""
        request_id = request.headers.get("X-Request-ID", "unknown")
        body = ErrorResponse(
            error="INTERNAL_SERVER_ERROR",
            message="An unexpected error occurred. Please try again later.",
            meta=ResponseMeta(request_id=request_id),
        )
        return JSONResponse(status_code=500, content=body.model_dump(mode="json"))


# ── Application Instance ─────────────────────────────────────────────

app = create_app()
