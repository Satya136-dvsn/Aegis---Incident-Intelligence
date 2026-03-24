"""
Aegis Backend — Metrics API Tests

Verify high-throughput POST /api/v1/metrics logic:
- Single metric ingestion
- Batch ingestion
- Strict validation (extra=forbid, etc)
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_ingest_single_metric(client: AsyncClient) -> None:
    """It should accept a single MetricIn payload and return 201."""
    payload = {
        "service_name": "payment-gateway",
        "metric_type": "transaction_latency",
        "value": 150.5,
    }
    response = await client.post("/api/v1/metrics", json=payload)
    
    assert response.status_code == 201
    data = response.json()
    assert data["message"] == "Successfully ingested 1 metric(s)"
    assert len(data["data"]) == 1
    assert isinstance(data["data"][0], int)


@pytest.mark.asyncio
async def test_ingest_batch_metrics(client: AsyncClient) -> None:
    """It should accept a list of MetricIn payloads and return 201."""
    payload = [
        {"service_name": "auth-api", "metric_type": "cpu_usage", "value": 45.1},
        {"service_name": "auth-api", "metric_type": "memory_usage", "value": 1024.0},
    ]
    response = await client.post("/api/v1/metrics", json=payload)
    
    assert response.status_code == 201
    data = response.json()
    assert data["message"] == "Successfully ingested 2 metric(s)"
    assert len(data["data"]) == 2


@pytest.mark.asyncio
async def test_ingest_metrics_validation_error(client: AsyncClient) -> None:
    """It should return 422 for missing required fields or unknown extra fields."""
    
    # Missing 'value' field
    invalid_payload = {
        "service_name": "auth-api",
        "metric_type": "cpu_usage",
    }
    response = await client.post("/api/v1/metrics", json=invalid_payload)
    assert response.status_code == 422
    assert response.json()["error"] == "VALIDATION_ERROR"
    
    # Extra unexpected field
    extra_field_payload = {
        "service_name": "auth-api",
        "metric_type": "cpu_usage",
        "value": 45.1,
        "hacker_field": "hacked",
    }
    extra_response = await client.post("/api/v1/metrics", json=extra_field_payload)
    assert extra_response.status_code == 422
    assert "validation error(s)" in extra_response.json()["message"]
