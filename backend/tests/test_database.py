"""
Aegis Backend — Database & Repository Tests

Verifies:
1. Database tables are created on startup
2. Metric CRUD operations
3. Log CRUD operations
4. Incident CRUD with filtering
5. Comment CRUD with cascade
6. Pydantic schema validation (extra=forbid)
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient


# ── Database initializes on startup ───────────────────────────────────


@pytest.mark.asyncio
async def test_database_tables_created(client: AsyncClient) -> None:
    """App startup should create all tables without error."""
    # If health returns 200, the lifespan (which creates tables) ran successfully
    response = await client.get("/api/v1/health")
    assert response.status_code == 200


# ── Schema Validation (extra=forbid) ──────────────────────────────────


@pytest.mark.asyncio
async def test_metric_schema_forbids_extra_fields() -> None:
    """MetricIn must reject payloads with unknown fields."""
    from app.api.schemas import MetricIn
    from pydantic import ValidationError

    with pytest.raises(ValidationError) as exc_info:
        MetricIn(
            service_name="auth-service",
            metric_type="cpu_usage",
            value=55.0,
            hacker_field="malicious",
        )
    assert "extra" in str(exc_info.value).lower() or "Extra inputs" in str(exc_info.value)


@pytest.mark.asyncio
async def test_incident_schema_enforces_title_length() -> None:
    """IncidentCreate must reject titles exceeding 100 characters."""
    from app.api.schemas import IncidentCreate
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        IncidentCreate(
            title="x" * 101,  # exceeds 100 char limit
            description="Test",
            severity="high",
            reporter_uid="user-1",
            reporter_name="Test User",
        )


@pytest.mark.asyncio
async def test_comment_schema_enforces_text_length() -> None:
    """CommentCreate must reject text exceeding 1000 characters."""
    from app.api.schemas import CommentCreate
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        CommentCreate(
            text="x" * 1001,
            author_uid="user-1",
            author_name="Test User",
        )


# ── Repository CRUD ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_and_retrieve_metric(setup_db) -> None:
    """Create a metric and verify it can be retrieved."""
    from app.database import async_session
    from app import repository

    async with async_session() as db:
        metric = await repository.create_metric(
            db,
            service_name="auth-service",
            metric_type="cpu_usage",
            value=55.5,
        )
        await db.commit()

        assert metric.id is not None
        assert metric.service_name == "auth-service"
        assert metric.value == 55.5

        # Retrieve
        metrics = await repository.get_recent_metrics(
            db, service_name="auth-service", limit=5
        )
        assert len(metrics) >= 1
        assert metrics[0].service_name == "auth-service"


@pytest.mark.asyncio
async def test_create_and_retrieve_log(setup_db) -> None:
    """Create a log event and verify retrieval."""
    from app.database import async_session
    from app import repository

    async with async_session() as db:
        log = await repository.create_log(
            db,
            service_name="payment-gateway",
            level="ERROR",
            message="Connection timeout to payment processor",
        )
        await db.commit()

        assert log.id is not None
        assert log.level.value == "ERROR"

        logs = await repository.get_recent_logs(db, service_name="payment-gateway")
        assert len(logs) >= 1


@pytest.mark.asyncio
async def test_incident_lifecycle(setup_db) -> None:
    """Create, update, and list incidents."""
    from app.database import async_session
    from app import repository

    async with async_session() as db:
        # Create
        incident = await repository.create_incident(
            db,
            title="High CPU on auth-service",
            description="CPU usage exceeded 95% for 5 minutes",
            severity="critical",
            reporter_uid="user-42",
            reporter_name="Jane Doe",
        )
        await db.commit()

        assert incident.id is not None
        assert incident.status.value == "open"

        # Update status
        updated = await repository.update_incident(
            db, incident.id, status="in-progress"
        )
        await db.commit()

        assert updated is not None
        assert updated.status.value == "in-progress"

        # List with filter
        incidents, total = await repository.list_incidents(db, severity="critical")
        assert total >= 1
        assert any(i.title == "High CPU on auth-service" for i in incidents)


@pytest.mark.asyncio
async def test_comment_crud(setup_db) -> None:
    """Create and list comments on an incident."""
    from app.database import async_session
    from app import repository

    async with async_session() as db:
        # First create an incident
        incident = await repository.create_incident(
            db,
            title="Test incident for comments",
            description="Testing comment system",
            severity="low",
            reporter_uid="user-1",
            reporter_name="Test User",
        )
        await db.commit()

        # Add comments
        c1 = await repository.create_comment(
            db,
            incident_id=incident.id,
            text="Investigating now",
            author_uid="user-2",
            author_name="Responder A",
        )
        c2 = await repository.create_comment(
            db,
            incident_id=incident.id,
            text="Found the root cause",
            author_uid="user-2",
            author_name="Responder A",
        )
        await db.commit()

        # List
        comments = await repository.list_comments(db, incident.id)
        assert len(comments) >= 2


@pytest.mark.asyncio
async def test_batch_metric_creation(setup_db) -> None:
    """Batch create metrics and verify count."""
    from app.database import async_session
    from app import repository

    async with async_session() as db:
        metrics_data = [
            {"service_name": "order-processor", "metric_type": "memory_usage", "value": 65.0},
            {"service_name": "order-processor", "metric_type": "memory_usage", "value": 70.0},
            {"service_name": "order-processor", "metric_type": "memory_usage", "value": 75.0},
        ]
        records = await repository.create_metrics_batch(db, metrics_data)
        await db.commit()

        assert len(records) == 3
        assert all(r.id is not None for r in records)
