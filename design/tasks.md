# Implementation Plan: Real-Time Incident Intelligence Platform

## Overview

Incremental build-out of the platform following the data flow:
Simulator → IngestionService → MetricsStore → ProcessingEngine → AnomalyDetector → RCAEngine → AlertManager → Dashboard

Foundation (project scaffold, DB schema, config) is established first, then each pipeline stage is wired in sequence, ending with the frontend and deployment artifacts.

## Tasks

- [ ] 1. Project scaffold and configuration
  - Create the top-level directory structure: `backend/`, `simulator/`, `frontend/`
  - Create `backend/requirements.txt` with all Python dependencies: `fastapi`, `uvicorn[standard]`, `sqlalchemy[asyncio]`, `asyncpg`, `alembic`, `pydantic-settings`, `celery[redis]`, `redis`, `slowapi`, `structlog`, `python-dotenv`, `openai`, `google-generativeai`, `pandas`, `httpx`, `hypothesis`
  - Create `backend/app/config.py` implementing `Settings(BaseSettings)` with all env vars from the design, including the `@model_validator` that fails fast if `RCA_PROVIDER` is set but the corresponding API key is missing
  - Create `.env.example` listing all environment variables with placeholder values and comments
  - _Requirements: 12.1, 12.2, 12.3_

- [ ] 2. Database models and migrations
  - [ ] 2.1 Create SQLAlchemy async ORM models
    - Write `backend/app/database.py` with async engine, session factory (`async_sessionmaker`), and `Base` declarative base; configure `pool_size=20, max_overflow=10`
    - Write `backend/app/models/metric.py`, `log_event.py`, `incident.py`, `rolling_stats.py` matching the exact schema from the design (columns, types, defaults)
    - Add a `backend/app/models/dead_letter.py` model for the `dead_letter_tasks` table
    - _Requirements: 11.1, 11.2, 11.3_

  - [ ] 2.2 Create Alembic migration for initial schema
    - Initialize Alembic in `backend/alembic/` and configure `env.py` to use the async engine and import all ORM models
    - Write `backend/alembic/versions/0001_initial_schema.py` creating all five tables with their columns, constraints, and indexes (`idx_metrics_service_type_ts`, `idx_metrics_timestamp`, `idx_log_events_service_ts`, `idx_incidents_status`, `idx_incidents_severity`, `idx_incidents_service_ts`, `idx_rolling_stats_lookup`)
    - _Requirements: 11.4, 11.5_

- [ ] 3. Pydantic schemas and response envelope
  - Write `backend/app/schemas/metric.py` with `MetricPayload` (strict mode, `extra='forbid'`, `@field_validator` for per-type value ranges) and `MetricResponse`
  - Write `backend/app/schemas/log_event.py` with `LogPayload` (strict mode, `level` as `Literal['DEBUG','INFO','WARNING','ERROR','CRITICAL']`) and `LogEventResponse`
  - Write `backend/app/schemas/incident.py` with `IncidentResponse` and `IncidentStatusUpdate`
  - Write `backend/app/schemas/common.py` with the generic `APIResponse[T]` envelope containing `data`, `error`, and `meta` fields
  - _Requirements: 1.3, 1.4, 1.5, 2.3, 2.4, 8.2, 16.1_

  - [ ] 3.1 Write property test for payload validation (P3)
    - `# Feature: realtime-incident-intelligence-platform, Property 3: Payload validation rejects invalid inputs`
    - Use `st.fixed_dictionaries` to generate payloads with missing fields, extra fields, wrong types, and out-of-range values; assert HTTP 422 for all
    - _Requirements: 1.3, 1.4, 2.3, 16.1_

- [ ] 4. FastAPI application factory and middleware
  - Write `backend/app/main.py` with the FastAPI app factory, lifespan context manager (run Alembic migrations on startup, close DB pool on shutdown), and router registration under `/api/v1`
  - Write `backend/app/middleware/error_handler.py` registering a global exception handler that returns HTTP 500 with a JSON envelope and logs the full stack trace (without sensitive data); add a 404 handler for undefined routes
  - Write `backend/app/middleware/rate_limiter.py` using `slowapi` with a Redis-backed limiter; fall back to in-memory limiter if Redis is unavailable; apply `RATE_LIMIT_PER_MINUTE` to POST `/api/v1/metrics` and POST `/api/v1/logs`
  - _Requirements: 8.1, 8.2, 8.3, 8.4, 13.4, 16.3_

  - [ ] 4.1 Write property test for JSON response envelope (P22)
    - `# Feature: realtime-incident-intelligence-platform, Property 22: Consistent JSON response envelope`
    - Generate valid and invalid requests to multiple endpoints; assert every response body contains `data`, `error`, and `meta` keys
    - _Requirements: 8.2_

  - [ ] 4.2 Write property test for rate limiting (P29)
    - `# Feature: realtime-incident-intelligence-platform, Property 29: Rate limiting returns 429`
    - Generate request bursts exceeding `RATE_LIMIT_PER_MINUTE`; assert requests beyond the limit receive HTTP 429
    - _Requirements: 16.3_

- [ ] 5. Health endpoint
  - Write `backend/app/routers/health.py` implementing `GET /api/v1/health` that checks DB connectivity (execute a trivial query) and Redis queue depth; return JSON with status of each component
  - _Requirements: 8.5_

- [ ] 6. Ingestion endpoints
  - [ ] 6.1 Implement POST /api/v1/metrics and POST /api/v1/logs
    - Write `backend/app/routers/ingestion.py` with both POST endpoints; validate payloads via Pydantic schemas; persist records to PostgreSQL using an async session; enqueue a Celery task (or fall back to `asyncio.create_task`) for each persisted metric; return HTTP 201 with the created record wrapped in `APIResponse`
    - Enforce the 500ms persistence SLA by using async DB writes with `asyncpg`
    - _Requirements: 1.1, 1.2, 1.5, 2.1, 2.2, 9.1, 9.4_

  - [ ] 6.2 Write property test for metric ingestion round-trip (P1)
    - `# Feature: realtime-incident-intelligence-platform, Property 1: Metric ingestion round-trip`
    - Use `st.builds(MetricPayload, ...)` to generate valid payloads; POST each; query DB; assert stored record matches all fields
    - _Requirements: 1.2_

  - [ ] 6.3 Write property test for log ingestion round-trip (P2)
    - `# Feature: realtime-incident-intelligence-platform, Property 2: Log ingestion round-trip`
    - Use `st.builds(LogPayload, ...)` to generate valid payloads; POST each; query DB; assert stored record matches all fields
    - _Requirements: 2.2_

  - [ ] 6.4 Write property test for ingestion non-blocking (P24)
    - `# Feature: realtime-incident-intelligence-platform, Property 24: Ingestion does not block on background processing`
    - Time the ingestion HTTP response; assert it returns before the corresponding Celery task completes by mocking the task with a deliberate delay
    - _Requirements: 9.1, 9.4_

- [ ] 7. Checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 8. Celery worker setup
  - Write `backend/app/workers/celery_app.py` configuring the Celery app with Redis broker (`REDIS_URL`), result backend, and `WORKER_CONCURRENCY` mapped to the `--concurrency` flag
  - Write `backend/app/workers/tasks.py` defining the `process_metric` Celery task with `max_retries=3`, `default_retry_delay=5`; on exhaustion write to `dead_letter_tasks`; add a Celery beat task for daily metric retention cleanup and a 30-second queue depth health check
  - Implement the Redis-unavailable fallback: if enqueueing fails, call the processing function directly via `asyncio.create_task()` and log `WARNING "Degraded async processing mode — Redis unavailable"`
  - _Requirements: 4.5, 9.1, 9.2, 9.3, 15.2_

  - [ ] 8.1 Write property test for dead-letter on exhausted retries (P7)
    - `# Feature: realtime-incident-intelligence-platform, Property 7: Dead-letter on exhausted retries`
    - Mock the processing function to always raise; run the task; assert a `dead_letter_tasks` row is created after exactly 3 retries and no record is silently dropped
    - _Requirements: 4.5_

  - [ ] 8.2 Write property test for Redis unavailability fallback (P27)
    - `# Feature: realtime-incident-intelligence-platform, Property 27: Redis unavailability fallback`
    - Mock Redis as unavailable; ingest a metric; assert the metric is still processed synchronously in-process
    - _Requirements: 15.2_

- [ ] 9. Processing engine
  - Write `backend/app/services/processing_engine.py` implementing:
    - Fetch the last 5-minute window of raw metrics for the given `(service_name, metric_type)` from DB
    - Compute rolling mean and standard deviation using Pandas `rolling()` on the fetched DataFrame
    - Persist the result to `rolling_stats` table
    - Cap `api_response_time_ms` at `API_RESPONSE_TIME_CAP_MS` (default 60,000ms); log WARNING for any value exceeding the cap
    - Flag the metric as a statistical outlier (`is_anomaly=True`) if value > mean + 3σ
    - Forward the processed metric to `AnomalyDetector`
  - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5_

  - [ ] 9.1 Write property test for rolling statistics correctness (P4)
    - `# Feature: realtime-incident-intelligence-platform, Property 4: Rolling statistics correctness`
    - Use `st.lists(st.floats(min_value=0, max_value=1000, allow_nan=False), min_size=1)` to generate metric value sets; assert computed mean and stddev equal `statistics.mean` and `statistics.stdev` for the same sample
    - _Requirements: 4.2_

  - [ ] 9.2 Write property test for outlier flagging (P5)
    - `# Feature: realtime-incident-intelligence-platform, Property 5: Outlier flagging`
    - Generate metric values that are exactly mean + 3σ + ε; assert `is_anomaly=True` is set on those records
    - _Requirements: 4.3_

  - [ ] 9.3 Write property test for response time normalization cap (P6)
    - `# Feature: realtime-incident-intelligence-platform, Property 6: Response time normalization cap`
    - Use `st.floats(min_value=60001, max_value=1e9)` for `api_response_time_ms` values; assert stored value equals the cap
    - _Requirements: 4.4_

- [ ] 10. Anomaly detector
  - Write `backend/app/services/anomaly_detector.py` implementing:
    - Static threshold evaluation for all four metric types (cpu_usage ≥ 85%, memory_usage ≥ 90%, api_response_time_ms ≥ 2000ms, error_rate_percent ≥ 5%)
    - Statistical baseline evaluation: flag if value > rolling_mean + 2σ
    - Severity classification using `breach_ratio = (value - threshold) / threshold`: LOW (statistical only), MEDIUM (< 0.20), HIGH (0.20–0.50), CRITICAL (≥ 0.50)
    - Deduplication: query `incidents` table for any open incident for the same `(service_name, metric_type)` within the last 2 minutes; suppress if found
    - Emit anomaly event dict with all required fields: `service_name`, `metric_type`, `value`, `severity`, `detected_at`, `rolling_mean`, `rolling_stddev`
  - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5_

  - [ ] 10.1 Write property test for threshold-based anomaly detection (P8)
    - `# Feature: realtime-incident-intelligence-platform, Property 8: Threshold-based anomaly detection`
    - Generate values at and above each static threshold; assert all are flagged as anomalous
    - _Requirements: 5.1_

  - [ ] 10.2 Write property test for statistical anomaly detection (P9)
    - `# Feature: realtime-incident-intelligence-platform, Property 9: Statistical anomaly detection`
    - Generate values > mean + 2σ below threshold; assert flagged as anomalous regardless of threshold
    - _Requirements: 5.2_

  - [ ] 10.3 Write property test for severity classification (P10)
    - `# Feature: realtime-incident-intelligence-platform, Property 10: Severity classification correctness`
    - Use `st.floats` for value and threshold; assert severity matches the breach_ratio formula exactly
    - _Requirements: 5.3_

  - [ ] 10.4 Write property test for anomaly event completeness (P11)
    - `# Feature: realtime-incident-intelligence-platform, Property 11: Anomaly event completeness`
    - Generate random anomaly inputs; assert emitted event contains all seven required fields
    - _Requirements: 5.4_

  - [ ] 10.5 Write property test for anomaly deduplication (P12)
    - `# Feature: realtime-incident-intelligence-platform, Property 12: Anomaly deduplication within 2-minute window`
    - Generate pairs of anomaly events for the same `(service_name, metric_type)` within a 2-minute window; assert only the first is emitted
    - _Requirements: 5.5_

- [ ] 11. Checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 12. LLM provider abstraction
  - Write `backend/app/services/llm/base.py` defining the `LLMProvider` Protocol with `async def complete(self, prompt: str) -> str`
  - Write `backend/app/services/llm/openai_provider.py` implementing `OpenAIProvider` using the `openai` async client with a 30-second timeout
  - Write `backend/app/services/llm/gemini_provider.py` implementing `GeminiProvider` using `google-generativeai` with a 30-second timeout
  - Write a factory function `get_llm_provider(settings: Settings) -> LLMProvider` that reads `RCA_PROVIDER` and returns the correct implementation
  - _Requirements: 6.6_

- [ ] 13. RCA engine
  - Write `backend/app/services/rca_engine.py` implementing:
    - `fetch_context(service_name, detected_at)`: query last 15 minutes of metrics and last 50 log events for the service
    - `redact_secrets(text)`: apply all `SECRET_PATTERNS` regexes, replacing matches with `[REDACTED]`
    - `build_prompt(anomaly_event, metrics, logs)`: construct the system+user prompt from the design
    - `parse_response(llm_response)`: parse JSON into `probable_cause`, `contributing_factors`, `suggested_fixes`; raise on malformed response
    - `run_rca(anomaly_event)`: orchestrate fetch → redact → build prompt → call LLM → parse → persist; on first failure store placeholder and schedule retry after 60s; on third consecutive failure store final placeholder
  - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7_

  - [ ] 13.1 Write property test for RCA context retrieval bounds (P13)
    - `# Feature: realtime-incident-intelligence-platform, Property 13: RCA context retrieval bounds`
    - Generate metric/log sets spanning various time ranges; assert retrieved context contains only records from the last 15 minutes and at most 50 log events, all scoped to the affected service
    - _Requirements: 6.1_

  - [ ] 13.2 Write property test for RCA prompt content (P14)
    - `# Feature: realtime-incident-intelligence-platform, Property 14: RCA prompt contains required context`
    - Generate anomaly contexts; assert the constructed prompt string contains service_name, metric_type, value, severity, metric history, and log events
    - _Requirements: 6.2_

  - [ ] 13.3 Write property test for RCA response parsing (P15)
    - `# Feature: realtime-incident-intelligence-platform, Property 15: RCA response parsing`
    - Use `st.text()` shaped as valid JSON with `probable_cause`, `contributing_factors`, `suggested_fixes`; assert parsing produces non-null structured output with correct types
    - _Requirements: 6.3_

  - [ ] 13.4 Write property test for secret redaction (P16)
    - `# Feature: realtime-incident-intelligence-platform, Property 16: Secret redaction from LLM prompts`
    - Generate log messages with injected API keys, passwords, Bearer tokens, and long alphanumeric strings; assert none of the original secret values appear in the constructed prompt
    - _Requirements: 6.7, 16.2_

  - [ ] 13.5 Write property test for LLM repeated failure placeholder (P28)
    - `# Feature: realtime-incident-intelligence-platform, Property 28: LLM repeated failure creates incident with placeholder`
    - Mock LLM provider to raise on every call; trigger RCA three times for the same anomaly; assert incident record exists with `probable_cause = "RCA unavailable — LLM repeatedly failed"`
    - _Requirements: 15.3_

  - [ ] 13.6 Write property test for RCA non-LLM processing time (P25)
    - `# Feature: realtime-incident-intelligence-platform, Property 25: RCA non-LLM processing completes within 5 seconds`
    - Mock the LLM call to return instantly; time all other RCA steps (fetch, redact, build prompt, parse, persist); assert total < 5 seconds
    - _Requirements: 14.4_

- [ ] 14. Alert manager and incident endpoints
  - Write `backend/app/services/alert_manager.py` implementing:
    - `create_incident(anomaly_event)`: insert an `Incident` row with `status=OPEN`; trigger `run_rca` as a Celery task
    - `dispatch_notification(incident)`: for HIGH/CRITICAL incidents, POST the incident JSON to `WEBHOOK_URL` with a 5-second timeout as a fire-and-forget Celery task; log WARNING if no channel is configured
  - Write `backend/app/routers/incidents.py` implementing:
    - `GET /api/v1/incidents` with pagination (`page`, `page_size`) and optional `status` and `severity` query filters
    - `GET /api/v1/incidents/{id}` returning the full incident including RCA fields
    - `PATCH /api/v1/incidents/{id}` accepting `{"status": "ACKNOWLEDGED"|"RESOLVED"}` and updating the record
  - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6_

  - [ ] 14.1 Write property test for incident creation completeness (P17)
    - `# Feature: realtime-incident-intelligence-platform, Property 17: Incident creation completeness`
    - Generate anomaly events; call `create_incident`; fetch via `GET /api/v1/incidents/{id}`; assert all required fields are present and `status=OPEN`
    - _Requirements: 7.1, 7.6_

  - [ ] 14.2 Write property test for incident list filtering (P18)
    - `# Feature: realtime-incident-intelligence-platform, Property 18: Incident list filtering`
    - Generate incident sets with varied statuses and severities; apply filter combinations; assert no out-of-filter incidents appear in results
    - _Requirements: 7.2_

  - [ ] 14.3 Write property test for incident status update round-trip (P19)
    - `# Feature: realtime-incident-intelligence-platform, Property 19: Incident status update round-trip`
    - Generate incident IDs; PATCH to ACKNOWLEDGED or RESOLVED; GET; assert returned status matches the patched value
    - _Requirements: 7.3_

  - [ ] 14.4 Write property test for HIGH/CRITICAL notification dispatch (P20)
    - `# Feature: realtime-incident-intelligence-platform, Property 20: HIGH/CRITICAL notification dispatch`
    - Generate HIGH and CRITICAL incidents with a mock webhook configured; assert the mock webhook receives a POST call for each
    - _Requirements: 7.4_

- [ ] 15. Checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 16. WebSocket endpoint and metrics query endpoint
  - Write `backend/app/routers/websocket.py` implementing `GET /api/v1/ws/metrics`; on connect, push recent metrics every 5 seconds from a background task; broadcast new metrics as they are ingested
  - Add `GET /api/v1/metrics/recent` to `backend/app/routers/ingestion.py` returning the most recent metric records per service and metric type for dashboard polling
  - _Requirements: 10.1, 10.5_

- [ ] 17. Database connection retry and failure handling
  - In `backend/app/database.py`, wrap the startup connection check with retry logic: up to 5 attempts with exponential backoff (1s, 2s, 4s, 8s, 16s); log each failed attempt with error details; raise a startup error after exhaustion
  - In `backend/app/middleware/error_handler.py`, add a handler for `asyncio.TimeoutError` and SQLAlchemy query timeouts that returns HTTP 504
  - _Requirements: 8.6, 15.1_

  - [ ] 17.1 Write property test for DB connection retry (P26)
    - `# Feature: realtime-incident-intelligence-platform, Property 26: DB connection retry with exponential backoff`
    - Mock the DB engine to fail N times (1–5); assert the platform retries exactly N times with increasing delays before succeeding or raising
    - _Requirements: 15.1_

  - [ ] 17.2 Write property test for request timeout 504 (P23)
    - `# Feature: realtime-incident-intelligence-platform, Property 23: Request timeout returns 504`
    - Mock a slow endpoint handler that sleeps > 30 seconds; assert the platform returns HTTP 504
    - _Requirements: 8.6_

- [ ] 18. Security and logging hardening
  - In `backend/app/config.py`, ensure the `Settings` class never logs or exposes `openai_api_key`, `gemini_api_key`, `database_url`, or `webhook_url` in any `__repr__` or `__str__` output
  - Configure `structlog` in `backend/app/main.py` with JSON output; set `LOG_LEVEL` from env; ensure no sensitive fields are included in log records
  - _Requirements: 12.1, 16.4_

  - [ ] 18.1 Write property test for no sensitive data in logs (P30)
    - `# Feature: realtime-incident-intelligence-platform, Property 30: No sensitive data in log output`
    - Capture log output during operations that involve API keys, DB credentials, and webhook URLs; assert none of those secret values appear in any log line
    - _Requirements: 16.4_

- [ ] 19. All endpoints under /api/v1/ prefix — unit test
  - Write a unit test in `backend/tests/unit/test_routes.py` that enumerates all registered FastAPI routes and asserts every path starts with `/api/v1/`
  - _Requirements: 8.1_

  - [ ] 19.1 Write property test for endpoint prefix (P21)
    - `# Feature: realtime-incident-intelligence-platform, Property 21: All endpoints under /api/v1/ prefix`
    - Enumerate all routes from the FastAPI app; assert each URL path begins with `/api/v1/`
    - _Requirements: 8.1_

- [ ] 20. Simulator
  - Write `simulator/simulator.py` that:
    - Generates synthetic `MetricPayload` records for at least two named services (`service-alpha`, `service-beta`) at `SIMULATOR_INTERVAL_SECONDS` (default 10s)
    - Injects anomalous values (e.g., cpu_usage 90–100%) at `ANOMALY_INJECT_PROBABILITY` (default 5%) per interval
    - Generates `LogPayload` records with realistic messages and levels
    - POSTs all records to the IngestionService endpoints; logs any HTTP errors
    - Starts automatically when the container starts (no manual trigger needed)
  - Write `simulator/Dockerfile`
  - _Requirements: 3.1, 3.2, 3.3, 3.4_

- [ ] 21. Checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 22. React dashboard
  - [ ] 22.1 Scaffold the React app
    - Initialize a Vite + React + TypeScript project in `frontend/`; install `recharts`, `axios` (or `fetch`), and a WebSocket hook library
    - Write `frontend/src/hooks/useMetrics.ts` implementing a hook that connects to `GET /api/v1/ws/metrics` WebSocket and falls back to polling `GET /api/v1/metrics/recent` every 5 seconds
    - _Requirements: 10.1, 10.5_

  - [ ] 22.2 Implement MetricChart component
    - Write `frontend/src/components/MetricChart.tsx` rendering a real-time line chart per metric type using `recharts`; update at most every 5 seconds from the `useMetrics` hook
    - _Requirements: 10.1_

  - [ ] 22.3 Implement IncidentList component
    - Write `frontend/src/components/IncidentList.tsx` fetching `GET /api/v1/incidents` and displaying open incidents with severity badge, affected service, detected time, and a link to the full RCA report; poll every 5 seconds to reflect status changes within 10 seconds
    - _Requirements: 10.2, 10.3_

  - [ ] 22.4 Implement HealthSummary component
    - Write `frontend/src/components/HealthSummary.tsx` deriving per-service health status (HEALTHY / DEGRADED / CRITICAL) from the most recent anomaly state returned by the backend; display a summary panel
    - _Requirements: 10.4_

  - [ ] 22.5 Wire components in App.tsx
    - Write `frontend/src/App.tsx` composing `MetricChart`, `IncidentList`, and `HealthSummary` into the dashboard layout
    - Write `frontend/Dockerfile` serving the built static files
    - _Requirements: 10.1, 10.2, 10.3, 10.4_

- [ ] 23. Docker Compose and deployment configuration
  - Write `docker-compose.yml` defining services: `backend` (FastAPI + Celery beat), `worker` (Celery worker with `WORKER_CONCURRENCY`), `simulator`, `frontend`, `postgres`, `redis`; set `depends_on` so backend waits for postgres and redis; mount `.env` file
  - Write `backend/Dockerfile` using a multi-stage build: install dependencies, copy source, run `alembic upgrade head` as the entrypoint before starting Uvicorn
  - Write `render.yaml` defining web service, worker service, postgres, and redis with environment variable references
  - _Requirements: 13.1, 13.2, 13.3, 13.4_

- [ ] 24. Integration wiring and end-to-end validation
  - [ ] 24.1 Wire the full pipeline in tasks.py
    - In `backend/app/workers/tasks.py`, ensure `process_metric` calls `ProcessingEngine.process` → `AnomalyDetector.evaluate` → if anomaly: `AlertManager.create_incident` → `RCAEngine.run_rca` (as a separate Celery task)
    - Verify the queue depth WARNING is logged when depth > 1000 (add a check in the health beat task)
    - _Requirements: 4.1, 5.1, 7.1, 9.2_

  - [ ] 24.2 Write integration tests for the full ingestion-to-incident pipeline
    - Use `pytest` with a test PostgreSQL database and mocked Redis; POST a metric that will trigger an anomaly; assert an incident row is created with correct severity and RCA placeholder
    - _Requirements: 1.2, 4.1, 5.1, 7.1_

- [ ] 25. Final checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- All tasks are required — no optional tasks
- Each task references specific requirements for traceability
- Property tests use Hypothesis with `@settings(max_examples=100)` and are tagged with the format `# Feature: realtime-incident-intelligence-platform, Property N: ...`
- Checkpoints ensure incremental validation at each major pipeline stage
- The design document contains the full correctness property definitions (P1–P30) referenced throughout these tasks
