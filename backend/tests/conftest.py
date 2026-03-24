"""
Aegis Backend — Test Configuration

Shared pytest fixtures for all test modules.
"""

from __future__ import annotations

import os
from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# Force testing database to be file-backed rather than purely in-memory.
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./test.db"

import app.models  # Ensure models are registered with Base.metadata before tests run
from app.database import Base
from app.main import app
from app.worker import celery_app

# Set Celery to eager mode so tasks execute synchronously without Redis during tests
celery_app.conf.update(
    task_always_eager=True,
    task_eager_propagates=True,
    broker_url="memory://",
    result_backend="cache+memory://"
)

# Create a single test engine
test_engine = create_async_engine(
    "sqlite+aiosqlite:///./test.db",
    connect_args={"check_same_thread": False},
    poolclass=None,
)

TestingSessionLocal = async_sessionmaker(
    test_engine, class_=AsyncSession, expire_on_commit=False
)


@pytest.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Provide a direct database session for test queries."""
    async with TestingSessionLocal() as session:
        yield session


@pytest.fixture
async def client() -> AsyncClient:
    """Async HTTP test client wired to the FastAPI application."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac


@pytest.fixture(autouse=True)
async def setup_db() -> AsyncGenerator[None, None]:
    """Create and drop the test database schema for every test."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    yield
    
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture(autouse=True)
def override_db_session(monkeypatch: pytest.MonkeyPatch) -> None:
    """Override the app's async_session to use our test DB."""
    import app.database
    monkeypatch.setattr(app.database, "async_session", TestingSessionLocal)

