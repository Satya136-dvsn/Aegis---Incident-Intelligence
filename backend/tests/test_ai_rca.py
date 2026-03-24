"""
Aegis Backend — AI RCA Engine Tests

Verifies that the `perform_rca_analysis` Celery task correctly gathers
metric and log context and updates the Incident with LLM-generated summaries,
mocking the actual google-genai API calls.
"""

from __future__ import annotations

import pytest
from unittest.mock import patch, MagicMock
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models import Incident, MetricRecord, LogRecord, Severity
from app.api.schemas import SeverityEnum
from app.tasks import _perform_rca_analysis_async

@pytest.mark.asyncio
async def test_perform_rca_analysis_success(setup_db, db_session: AsyncSession) -> None:
    """Verify context gathering and DB updating for AI RCA generation."""
    # 1. Seed database with context
    service = "payment-gateway"
    
    # Add an incident
    incident = Incident(
        title=f"Anomaly: {service} cpu spike",
        description="CPU breached 2-sigma threshold.",
        severity=SeverityEnum.HIGH,
        reporter_uid="system",
        reporter_name="Engine",
        category="Performance"
    )
    db_session.add(incident)
    await db_session.commit()
    await db_session.refresh(incident)
    
    # Add some context records
    db_session.add(MetricRecord(service_name=service, metric_type="cpu", value=99.9))
    db_session.add(LogRecord(service_name=service, level="ERROR", message="CPU throttling activated"))
    await db_session.commit()

    # 2. Mock the Gemini generate_rca_sync function to return deterministic AI text
    with patch("app.llm.generate_rca_sync") as mock_generate:
        mock_generate.return_value = (
            "The payment-gateway ran out of CPU resources due to high load, triggering throttling.",
            "High traffic leading to CPU exhaustion."
        )
        
        # 3. Execute the RCA task
        success = await _perform_rca_analysis_async(incident.id, service)
        
        assert success is True
        
        # Verify the mock was called with context
        mock_generate.assert_called_once()
        args, kwargs = mock_generate.call_args
        # Title and description
        assert incident.title in args[0]
        # Logs
        assert str(args[2][0]["msg"]) == "CPU throttling activated"
        # Metrics
        assert float(args[3][0]["val"]) == 99.9

    # 4. Verify Database update
    # Expunge to bypass session cache
    db_session.expunge_all()
    result = await db_session.execute(select(Incident).where(Incident.id == incident.id))
    updated_incident = result.scalar_one()

    assert updated_incident.rca_summary == "The payment-gateway ran out of CPU resources due to high load, triggering throttling."
    assert updated_incident.probable_cause == "High traffic leading to CPU exhaustion."
