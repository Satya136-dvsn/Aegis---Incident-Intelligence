"""
Aegis Backend — Logs API Tests

Verify structured logging POST /api/v1/logs logic:
- Valid log ingestion
- Schema validation
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_ingest_log(client: AsyncClient) -> None:
    """It should accept a valid LogIn payload and return 201."""
    payload = {
        "service_name": "user-service",
        "level": "WARNING",
        "message": "User login attempt failed (rate limit)",
        "metadata": {"ip": "192.168.1.100", "user_id": 1234},
    }
    response = await client.post("/api/v1/logs", json=payload)
    
    assert response.status_code == 201
    data = response.json()
    assert data["message"] == "Successfully ingested log record"
    assert isinstance(data["data"], int)


@pytest.mark.asyncio
async def test_ingest_log_invalid_level(client: AsyncClient) -> None:
    """It should reject invalid enum values for severity level."""
    payload = {
        "service_name": "user-service",
        "level": "SUPER_ERROR",  # Not in config LogLevel enum
        "message": "Something exploded.",
    }
    response = await client.post("/api/v1/logs", json=payload)
    
    assert response.status_code == 422
    data = response.json()
    assert data["error"] == "VALIDATION_ERROR"
    assert any("level" in str(d["field"]) for d in data["details"])
