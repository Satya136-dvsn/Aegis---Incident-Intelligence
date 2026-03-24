"""
Aegis Backend — Health Endpoint Tests

Verifies:
1. Health endpoint returns 200 with correct schema
2. Response contains X-Request-ID header
3. Response contains X-Response-Time-Ms header
4. Data envelope is properly structured
5. All expected component checks are present
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_returns_200(client: AsyncClient) -> None:
    """GET /api/v1/health should return 200 OK."""
    response = await client.get("/api/v1/health")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_health_response_envelope(client: AsyncClient) -> None:
    """Response must follow DataResponse[HealthResponse] schema."""
    response = await client.get("/api/v1/health")
    body = response.json()

    # Top-level keys
    assert "data" in body
    assert "meta" in body

    # Data payload
    data = body["data"]
    assert "status" in data
    assert "version" in data
    assert "uptime_seconds" in data
    assert "environment" in data
    assert "components" in data
    assert isinstance(data["components"], list)

    # Meta
    meta = body["meta"]
    assert "request_id" in meta
    assert "timestamp" in meta
    assert "version" in meta


@pytest.mark.asyncio
async def test_health_components_present(client: AsyncClient) -> None:
    """Health check must report on database, redis, and llm_provider."""
    response = await client.get("/api/v1/health")
    components = response.json()["data"]["components"]
    names = [c["name"] for c in components]

    assert "database" in names
    assert "redis" in names
    assert "llm_provider" in names


@pytest.mark.asyncio
async def test_request_id_header(client: AsyncClient) -> None:
    """Every response must contain an X-Request-ID header."""
    response = await client.get("/api/v1/health")
    assert "X-Request-ID" in response.headers
    assert len(response.headers["X-Request-ID"]) > 0


@pytest.mark.asyncio
async def test_custom_request_id_passthrough(client: AsyncClient) -> None:
    """If client sends X-Request-ID, server must echo it back."""
    custom_id = "test-trace-12345"
    response = await client.get(
        "/api/v1/health", headers={"X-Request-ID": custom_id}
    )
    assert response.headers["X-Request-ID"] == custom_id


@pytest.mark.asyncio
async def test_response_time_header(client: AsyncClient) -> None:
    """Every response must contain an X-Response-Time-Ms header."""
    response = await client.get("/api/v1/health")
    assert "X-Response-Time-Ms" in response.headers
    elapsed = float(response.headers["X-Response-Time-Ms"])
    assert elapsed >= 0


@pytest.mark.asyncio
async def test_404_returns_error_envelope(client: AsyncClient) -> None:
    """Unknown routes must return structured ErrorResponse, not HTML."""
    response = await client.get("/api/v1/nonexistent")
    assert response.status_code == 404

    body = response.json()
    assert body["error"] == "NOT_FOUND"
    assert "message" in body
    assert "meta" in body
    assert "request_id" in body["meta"]


@pytest.mark.asyncio
async def test_uptime_is_positive(client: AsyncClient) -> None:
    """Uptime must always be a positive number."""
    response = await client.get("/api/v1/health")
    uptime = response.json()["data"]["uptime_seconds"]
    assert uptime > 0
