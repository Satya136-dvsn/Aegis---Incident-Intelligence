"""
Aegis Backend — Anomaly Engine Tests

Verifies the Celery background tasks that process metrics
and trigger incidents upon detecting 2σ deviations.
"""

from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Incident, MetricRecord
from app.tasks import _process_metric_batch_async, _trigger_incident_async

@pytest.mark.asyncio
async def test_trigger_incident_creates_db_record(setup_db, db_session: AsyncSession) -> None:
    """Verify that the trigger_incident task creates a HIGH severity incident."""
    incident_id = await _trigger_incident_async(
        service_name="payment-api",
        metric_type="latency",
        value=500.0,
        metric_id=999
    )
    
    assert incident_id is not None
    
    # Query the database
    result = await db_session.execute(select(Incident).where(Incident.id == incident_id))
    incident = result.scalar_one_or_none()
    
    assert incident is not None
    assert incident.severity.value == "high"
    assert "payment-api latency spike" in incident.title
    assert incident.reporter_name == "Aegis Anomaly Engine"


@pytest.mark.asyncio
async def test_process_metric_batch_detects_anomaly(setup_db, db_session: AsyncSession) -> None:
    """
    Verify 2-sigma deviation logic:
    1. Insert baseline metrics.
    2. Insert a spike metric.
    3. Run processing task and check if anomaly is flagged.
    """
    # 1. Insert 10 baseline metrics (values ~10)
    baseline_records = []
    for i in range(10):
        m = MetricRecord(service_name="auth-api", metric_type="cpu", value=10.0 + (i * 0.1))
        db_session.add(m)
        baseline_records.append(m)
    await db_session.commit()

    # 2. Insert spike metric (value 99)
    spike = MetricRecord(service_name="auth-api", metric_type="cpu", value=99.0)
    db_session.add(spike)
    await db_session.commit()
    await db_session.refresh(spike)

    # 3. Process the spike
    result = await _process_metric_batch_async([spike.id])
    assert result["processed"] == 1
    assert result["anomalies"] == 1

    # Verify DB updated
    await db_session.refresh(spike)
    assert spike.is_anomaly is True
    assert spike.rolling_mean is not None
    assert spike.rolling_std is not None

    # Because Celery is eager in tests, trigger_incident should have run synchronously.
    # Let's check if an incident was created.
    # We clear the session cache before querying to ensure fresh state
    db_session.expunge_all()
    inc_result = await db_session.execute(
        select(Incident).where(Incident.title.contains("auth-api cpu spike"))
    )
    incident = inc_result.scalars().first()
    assert incident is not None
    assert incident.severity.value == "high"
