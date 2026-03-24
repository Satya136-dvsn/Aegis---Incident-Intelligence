"""
Aegis Backend — Application Configuration

Central configuration module using pydantic-settings.
All values are sourced from environment variables with sensible defaults.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application-wide settings loaded from environment variables."""

    # ── Core ──────────────────────────────────────────────────────────
    APP_NAME: str = "Aegis Incident Intelligence"
    APP_VERSION: str = "2.0.0"
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"

    # ── API ───────────────────────────────────────────────────────────
    API_V1_PREFIX: str = "/api/v1"
    CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://localhost:5173"]
    RATE_LIMIT_PER_MINUTE: int = 1000

    # ── Database (Phase 2) ────────────────────────────────────────────
    DATABASE_URL: str = "sqlite+aiosqlite:///./aegis_dev.db"

    # ── Redis / Celery (Phase 4) ──────────────────────────────────────
    REDIS_URL: str = "redis://localhost:6379/0"
    WORKER_CONCURRENCY: int = 2

    # ── AI / LLM (Phase 5) ───────────────────────────────────────────
    RCA_PROVIDER: str = "gemini"  # "gemini" | "openai"
    GEMINI_API_KEY: str = ""
    OPENAI_API_KEY: str = ""

    # ── Simulator ────────────────────────────────────────────────────
    SIMULATOR_INTERVAL_SECONDS: float = 10.0
    ANOMALY_INJECT_PROBABILITY: float = 0.05

    # ── Retention ────────────────────────────────────────────────────
    METRIC_RETENTION_DAYS: int = 30

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


@lru_cache
def get_settings() -> Settings:
    """Return a cached singleton of the application settings."""
    return Settings()
