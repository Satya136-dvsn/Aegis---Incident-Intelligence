"""
Aegis Backend — LLM Orchestrator

Uses google-genai to connect with the new Gemini API endpoints.
Provides intelligent root cause summaries for automatically generated incidents.
"""

from __future__ import annotations

import structlog
from google import genai
from google.genai import types
from tenacity import retry, stop_after_attempt, wait_exponential

from app.config import get_settings

logger = structlog.get_logger(__name__)
settings = get_settings()

client = None
if settings.GEMINI_API_KEY:
    client = genai.Client(api_key=settings.GEMINI_API_KEY)


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    reraise=True
)
def generate_rca_sync(incident_title: str, incident_desc: str, context_logs: list[dict], context_metrics: list[dict]) -> tuple[str, str]:
    """
    Synchronous RCA generation using google-genai. Designed to be called by Celery workers.
    Returns a tuple of (rca_summary, probable_cause).
    """
    if not client:
        logger.warning("gemini_client_missing", reason="GEMINI_API_KEY is not set. Skipping RCA.")
        return ("AI RCA unavailable (No API Key).", "Unknown")

    prompt = f"""
    You are an expert DevOps and Site Reliability Engineering assistant.
    An automated anomaly has triggered an incident on our systems.
    
    Incident Title: {incident_title}
    Incident Description: {incident_desc}
    
    Here is the recent context from the affected service leading up to the incident:
    
    --- METRICS ROUNDUP ---
    {context_metrics}
    
    --- LOGS ROUNDUP ---
    {context_logs}
    
    Please provide an analysis consisting of two precise parts.
    Format your response EXACTLY as follows:
    RCA_SUMMARY: <A 3 to 4 sentence executive summary of what went wrong based on the logs and metrics>
    PROBABLE_CAUSE: <A 1 sentence explanation of the most likely root cause>
    """

    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
        )
        
        text = response.text or ""
        rca_summary = "No summary generated."
        probable_cause = "Unknown"
        
        # Simple parsing of the structured response
        lines = text.split('\n')
        for line in lines:
            if line.startswith("RCA_SUMMARY:"):
                rca_summary = line.replace("RCA_SUMMARY:", "").strip()
            elif line.startswith("PROBABLE_CAUSE:"):
                probable_cause = line.replace("PROBABLE_CAUSE:", "").strip()
                
        return rca_summary, probable_cause

    except Exception as e:
        logger.error("gemini_rca_failed", error=str(e))
        raise
