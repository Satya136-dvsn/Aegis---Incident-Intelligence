"""
Aegis Backend — Async Database Engine

Provides the async SQLAlchemy engine, session factory, and base model class.
Supports both PostgreSQL (production) and SQLite (development/testing).
"""

from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.config import get_settings

settings = get_settings()

# ── Engine ────────────────────────────────────────────────────────────

# If using SQLite, we need to allow multiple threads to access it
# and disable connection pooling so tables created in one connection
# are visible to others (especially for in-memory or fast local testing).
connect_args = {}
if settings.DATABASE_URL.startswith("sqlite"):
    connect_args["check_same_thread"] = False

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    connect_args=connect_args,
    # Disable connection pooling for SQLite to prevent "table not found" errors in tests
    poolclass=None if settings.DATABASE_URL.startswith("sqlite") else None,
)

# ── Session factory ───────────────────────────────────────────────────

async_session = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


# ── Base model ────────────────────────────────────────────────────────


class Base(DeclarativeBase):
    """Declarative base for all SQLAlchemy models."""

    pass


# ── Dependency ────────────────────────────────────────────────────────


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency yielding an async database session."""
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
