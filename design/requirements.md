# Requirements Document

Version: 1.0
Last Updated: March 21, 2026

## Introduction

A real-time AI-powered observability platform that ingests system metrics and logs, detects anomalies, and uses an LLM to automatically explain root causes and suggest remediation steps. The platform is designed to demonstrate SRE and backend engineering skills, covering data ingestion, async processing, anomaly detection, AI-driven analysis, alerting, and a live dashboard.

## Glossary

- **Platform**: The Real-Time System Monitoring & Incident Intelligence Platform as a whole.
- **IngestionService**: The FastAPI component responsible for receiving and storing metrics and log events.
- **MetricsStore**: The PostgreSQL database tables that hold raw and aggregated metric data.
- **ProcessingEngine**: The background worker (Celery task or FastAPI background task) that cleans, normalizes, and aggregates raw metrics.
- **AnomalyDetector**: The component that evaluates processed metrics against thresholds and statistical baselines to identify unusual behavior.
- **RCAEngine**: The AI Root Cause Analysis Engine that calls an LLM (OpenAI or Gemini) to explain anomalies and suggest fixes.
- **AlertManager**: The component that creates incident records and dispatches notifications when anomalies are confirmed.
- **Incident**: A persisted record of a detected anomaly, its severity, RCA output, and resolution status.
- **Dashboard**: The React-based frontend that displays real-time graphs, incident logs, and system health indicators.
- **Metric**: A time-stamped numerical measurement such as CPU usage percentage, memory usage percentage, API response time in milliseconds, or error rate as a percentage.
- **LogEvent**: A structured JSON record capturing application-level events including timestamp, service name, log level, and message.
- **Severity**: A classification of anomaly impact — one of LOW, MEDIUM, HIGH, or CRITICAL.
- **Simulator**: A background process that generates synthetic Metric and LogEvent data to populate the Platform during development and demonstration.

---

## System Scope / System Boundaries

The Platform is a self-contained demonstration environment. The following boundaries apply:

- The Platform simulates a monitoring environment and is NOT integrated with any production infrastructure.
- All Metric and LogEvent data is synthetic, generated exclusively by the Simulator.
- External integrations are limited to: configured LLM APIs (OpenAI or Gemini) and optional outbound webhook alerts.
- The Platform is NOT building: a production APM agent, real service instrumentation, a billing system, user authentication/authorization, or multi-tenant isolation.

---

## Assumptions

- The Simulator provides a consistent and continuous stream of synthetic data throughout the platform's operation.
- LLM API responses (OpenAI / Gemini) are assumed to be structurally reliable within the defined prompt constraints; the platform handles API failures but does not validate LLM reasoning quality.
- The platform runs in a controlled demonstration environment; production-grade concerns such as multi-tenancy, user authentication, and billing are explicitly out of scope.
- PostgreSQL and Redis are assumed to be available and healthy at startup; cold-start resilience beyond the defined retry logic is not required.
- Network latency between platform components is assumed to be negligible (co-located containers).

---

## Data Flow Summary

The end-to-end data flow through the Platform is:

```
Metrics/Logs → IngestionService → MetricsStore → ProcessingEngine → AnomalyDetector → RCAEngine → AlertManager (Incident) → Dashboard
```

1. The Simulator generates synthetic Metrics and LogEvents and POSTs them to the IngestionService.
2. The IngestionService validates and persists records to the MetricsStore.
3. The ProcessingEngine asynchronously reads raw records, normalizes them, and computes rolling statistics.
4. The AnomalyDetector evaluates processed Metrics against thresholds and statistical baselines.
5. On anomaly detection, the RCAEngine retrieves context from the MetricsStore and calls the LLM for root cause analysis.
6. The AlertManager creates an Incident record and dispatches notifications.
7. The Dashboard polls or subscribes via WebSocket to display live Metrics and open Incidents.

---

## Requirements

### Requirement 1 [P0]: Metrics Ingestion

**User Story:** As an SRE, I want the platform to ingest CPU, memory, API response time, and error rate metrics, so that I have a continuous stream of system health data to monitor.

#### Acceptance Criteria

1. THE IngestionService SHALL expose a POST endpoint at `/api/v1/metrics` that accepts a JSON payload containing `service_name`, `metric_type`, `value`, and `timestamp`.
2. WHEN a valid metric payload is received, THE IngestionService SHALL persist the record to the MetricsStore within 500ms.
3. IF a metric payload is missing a required field, THEN THE IngestionService SHALL return HTTP 422 with a descriptive validation error message.
4. IF a metric `value` is outside the valid range for its `metric_type` (e.g., CPU percentage > 100 or < 0), THEN THE IngestionService SHALL return HTTP 422 with a field-level error.
5. THE IngestionService SHALL support ingestion of at least four metric types: `cpu_usage`, `memory_usage`, `api_response_time_ms`, and `error_rate_percent`.
6. THE MetricsStore SHALL retain raw metric records for a configurable retention period, defaulting to 30 days.

---

### Requirement 2 [P0]: Log Event Ingestion

**User Story:** As an SRE, I want the platform to ingest structured log events from services, so that the RCAEngine has log context when explaining failures.

#### Acceptance Criteria

1. THE IngestionService SHALL expose a POST endpoint at `/api/v1/logs` that accepts a JSON payload containing `service_name`, `level`, `message`, and `timestamp`.
2. WHEN a valid log payload is received, THE IngestionService SHALL persist the record to the MetricsStore within 500ms.
3. IF a log payload contains an unrecognized `level` value, THEN THE IngestionService SHALL return HTTP 422 with a descriptive error.
4. THE IngestionService SHALL accept log levels: `DEBUG`, `INFO`, `WARNING`, `ERROR`, and `CRITICAL`.

---

### Requirement 3 [P1]: Metrics Simulator

**User Story:** As a developer, I want a built-in simulator that generates realistic synthetic metrics and logs, so that I can demonstrate the platform without connecting to a live system.

#### Acceptance Criteria

1. THE Simulator SHALL generate synthetic Metric records for at least two named services at a configurable interval, defaulting to every 10 seconds.
2. THE Simulator SHALL periodically inject anomalous metric values (e.g., CPU spike to 90–100%) at a configurable probability, defaulting to 5% per interval.
3. THE Simulator SHALL submit generated Metric and LogEvent records to the IngestionService endpoints.
4. WHEN the Platform starts in simulation mode, THE Simulator SHALL begin generating data automatically without manual intervention.

---

### Requirement 4 [P0]: Data Processing Engine

**User Story:** As an SRE, I want raw metrics to be cleaned, normalized, and aggregated, so that the AnomalyDetector operates on consistent, high-quality data.

#### Acceptance Criteria

1. WHEN a new Metric record is persisted, THE ProcessingEngine SHALL process it asynchronously within 5 seconds.
2. THE ProcessingEngine SHALL compute a rolling 5-minute average and standard deviation for each `(service_name, metric_type)` pair and store the result in the MetricsStore.
3. IF a raw Metric value is a statistical outlier (more than 3 standard deviations from the rolling mean), THE ProcessingEngine SHALL flag the record as a candidate anomaly before forwarding it to the AnomalyDetector.
4. THE ProcessingEngine SHALL normalize `api_response_time_ms` values by capping storage at a configurable maximum, defaulting to 60,000ms, and logging a warning for any value that exceeds the cap.
5. WHILE the ProcessingEngine is running, THE ProcessingEngine SHALL not drop any Metric records; failed processing attempts SHALL be retried up to 3 times before the record is moved to a dead-letter store.

---

### Requirement 5 [P0]: Anomaly Detection

**User Story:** As an SRE, I want the platform to automatically detect unusual metric behavior, so that I am alerted to potential incidents before they escalate.

#### Acceptance Criteria

1. THE AnomalyDetector SHALL evaluate each processed Metric against static thresholds: `cpu_usage` ≥ 85%, `memory_usage` ≥ 90%, `api_response_time_ms` ≥ 2000ms, `error_rate_percent` ≥ 5%.
2. THE AnomalyDetector SHALL evaluate each processed Metric against a statistical baseline: a value more than 2 standard deviations above the rolling mean for that `(service_name, metric_type)` pair SHALL be flagged as anomalous.
3. WHEN a Metric is flagged as anomalous by either method, THE AnomalyDetector SHALL assign a Severity level according to the following rules:
   - LOW: statistical deviation only, no threshold breach.
   - MEDIUM: threshold breached by less than 20% above the threshold value.
   - HIGH: threshold breached by 20–50% above the threshold value.
   - CRITICAL: threshold breached by more than 50% above the threshold value.
4. WHEN an anomaly is detected, THE AnomalyDetector SHALL emit an anomaly event containing `service_name`, `metric_type`, `value`, `severity`, `detected_at`, and the rolling mean and standard deviation at the time of detection.
5. THE AnomalyDetector SHALL deduplicate anomaly events: if an anomaly for the same `(service_name, metric_type)` was emitted within the last 2 minutes, THE AnomalyDetector SHALL suppress the duplicate event.

---

### Requirement 6 [P1]: AI Root Cause Analysis

**User Story:** As an SRE, I want the platform to automatically explain why an anomaly occurred and suggest a fix, so that I can resolve incidents faster without deep manual investigation.

#### Acceptance Criteria

1. WHEN an anomaly event is emitted, THE RCAEngine SHALL retrieve the last 15 minutes of Metric records and the last 50 LogEvent records for the affected service from the MetricsStore.
2. THE RCAEngine SHALL construct a prompt containing the anomaly details, the retrieved metric history, and the retrieved log events, and submit it to the configured LLM provider (OpenAI GPT-4o or Google Gemini).
3. WHEN the LLM returns a response, THE RCAEngine SHALL parse the response into a structured object containing: `probable_cause` (string), `contributing_factors` (list of strings), and `suggested_fixes` (list of strings).
4. THE RCAEngine SHALL persist the structured RCA result alongside the corresponding Incident record in the MetricsStore.
5. IF the LLM API call fails or times out after 30 seconds, THEN THE RCAEngine SHALL store a placeholder RCA result with `probable_cause` set to `"RCA unavailable — LLM call failed"` and retry the call once after a 60-second delay.
6. THE RCAEngine SHALL support runtime selection of LLM provider via an environment variable `RCA_PROVIDER` with accepted values `openai` and `gemini`.
7. THE RCAEngine SHALL redact any secret or credential patterns (e.g., API keys matching common regex patterns) from log content before including it in the LLM prompt.

---

### Requirement 7 [P1]: Alert & Incident Management

**User Story:** As an SRE, I want incidents to be recorded and notifications dispatched when anomalies are detected, so that the team can track and respond to issues.

#### Acceptance Criteria

1. WHEN an anomaly event is emitted, THE AlertManager SHALL create an Incident record in the MetricsStore containing `id`, `service_name`, `metric_type`, `severity`, `detected_at`, `status` (defaulting to `OPEN`), and a reference to the RCA result once available.
2. THE AlertManager SHALL expose a GET endpoint at `/api/v1/incidents` that returns a paginated list of Incident records, filterable by `status` and `severity`.
3. THE AlertManager SHALL expose a PATCH endpoint at `/api/v1/incidents/{id}` that allows updating the `status` field to `ACKNOWLEDGED` or `RESOLVED`.
4. WHEN an Incident with Severity HIGH or CRITICAL is created, THE AlertManager SHALL dispatch a notification to at least one configured channel (webhook URL or email address) within 10 seconds of incident creation.
5. IF no notification channel is configured, THEN THE AlertManager SHALL log a WARNING and continue without raising an exception.
6. THE AlertManager SHALL expose a GET endpoint at `/api/v1/incidents/{id}` that returns the full Incident record including the associated RCA result.

---

### Requirement 8 [P0]: REST API & Backend Service

**User Story:** As a developer, I want a well-structured FastAPI backend, so that all platform components are accessible via a consistent HTTP API.

#### Acceptance Criteria

1. THE Platform SHALL expose all public endpoints under the `/api/v1/` prefix.
2. THE Platform SHALL return all responses in JSON format with consistent envelope structure containing `data`, `error`, and `meta` fields.
3. WHEN a request is received for an undefined route, THE Platform SHALL return HTTP 404 with a JSON error body.
4. WHEN an unhandled exception occurs during request processing, THE Platform SHALL return HTTP 500 with a JSON error body and log the full stack trace.
5. THE Platform SHALL expose a GET `/api/v1/health` endpoint that returns the status of the database connection and the processing queue.
6. THE Platform SHALL enforce a request timeout of 30 seconds on all endpoints and return HTTP 504 if the timeout is exceeded.

---

### Requirement 9 [P0]: Async Processing & Background Jobs

**User Story:** As a developer, I want metric processing and RCA calls to run asynchronously, so that ingestion endpoints remain fast and the system stays responsive under load.

#### Acceptance Criteria

1. THE ProcessingEngine SHALL run as a Celery worker or FastAPI background task, decoupled from the HTTP request lifecycle.
2. WHEN the task queue depth exceeds 1000 pending tasks, THE Platform SHALL log a WARNING indicating queue backpressure.
3. THE Platform SHALL support at least 2 concurrent ProcessingEngine workers configurable via an environment variable `WORKER_CONCURRENCY`.
4. WHILE a background job is executing, THE Platform SHALL not block the ingestion endpoints from accepting new requests.

---

### Requirement 10 [P2]: Dashboard (Frontend)

**User Story:** As an SRE, I want a real-time web dashboard, so that I can visually monitor system health, view live metric graphs, and inspect open incidents.

#### Acceptance Criteria

1. THE Dashboard SHALL display a real-time line chart for each metric type, updating at most every 5 seconds by polling the backend or via WebSocket.
2. THE Dashboard SHALL display a list of open Incidents with their Severity, affected service, detected time, and a link to the full RCA report.
3. WHEN an Incident status is updated to `RESOLVED`, THE Dashboard SHALL reflect the change within 10 seconds without requiring a full page reload.
4. THE Dashboard SHALL display a system health summary panel showing the current status (HEALTHY, DEGRADED, or CRITICAL) for each monitored service, derived from the most recent anomaly state.
5. WHERE a WebSocket connection is available, THE Dashboard SHALL use WebSocket for live metric updates instead of polling.

---

### Requirement 11 [P0]: Data Persistence & Schema

**User Story:** As a developer, I want a well-defined PostgreSQL schema, so that all platform data is stored reliably and queryable efficiently.

#### Acceptance Criteria

1. THE MetricsStore SHALL contain a `metrics` table with columns: `id`, `service_name`, `metric_type`, `value`, `timestamp`, `is_anomaly`, `created_at`.
2. THE MetricsStore SHALL contain a `log_events` table with columns: `id`, `service_name`, `level`, `message`, `timestamp`, `created_at`.
3. THE MetricsStore SHALL contain an `incidents` table with columns: `id`, `service_name`, `metric_type`, `severity`, `detected_at`, `status`, `rca_probable_cause`, `rca_contributing_factors`, `rca_suggested_fixes`, `created_at`, `updated_at`.
4. THE MetricsStore SHALL define indexes on `(service_name, metric_type, timestamp)` for the `metrics` table and on `(service_name, timestamp)` for the `log_events` table to support efficient time-range queries.
5. THE Platform SHALL use Alembic for database schema migrations, and all schema changes SHALL be applied via versioned migration scripts.

---

### Requirement 12 [P1]: Configuration & Secrets Management

**User Story:** As a developer, I want all sensitive configuration to be managed via environment variables, so that the platform can be deployed securely across environments.

#### Acceptance Criteria

1. THE Platform SHALL read all secrets (database URL, LLM API keys, notification webhook URLs) exclusively from environment variables and SHALL NOT hardcode any secret values in source code.
2. THE Platform SHALL fail to start with a descriptive error message if any required environment variable (`DATABASE_URL`, `RCA_PROVIDER`, `OPENAI_API_KEY` or `GEMINI_API_KEY`) is missing.
3. THE Platform SHALL support a `.env` file for local development, loaded via `python-dotenv` or equivalent.

---

### Requirement 13 [P1]: Deployment

**User Story:** As a developer, I want the platform containerized and deployable to a cloud environment, so that I can demonstrate it running in a production-like setup.

#### Acceptance Criteria

1. THE Platform SHALL provide a `Dockerfile` for the FastAPI backend that produces a runnable container image.
2. THE Platform SHALL provide a `docker-compose.yml` that starts the backend, PostgreSQL, Redis (if Celery is used), and the Simulator together with a single `docker-compose up` command.
3. THE Platform SHALL provide deployment configuration (e.g., `render.yaml` or AWS ECS task definition) for deploying to Render or AWS.
4. WHEN the container starts, THE Platform SHALL automatically run pending Alembic migrations before accepting traffic.

---

### Requirement 14 [P0]: Non-Functional Requirements

**User Story:** As a developer, I want the platform to meet defined performance and availability targets, so that it can handle realistic demonstration workloads reliably.

#### Acceptance Criteria

1. THE Platform SHALL handle a sustained ingestion rate of at least 10,000 Metric events per minute across all IngestionService instances.
2. THE IngestionService SHALL respond to valid ingestion requests (POST `/api/v1/metrics` and POST `/api/v1/logs`) within 200ms at the 95th percentile under normal load.
3. WHILE running in simulation mode, THE Platform SHALL maintain 99% uptime measured over any 1-hour window.
4. WHEN an anomaly event is emitted, THE RCAEngine SHALL complete all processing steps (excluding the LLM API call duration) within 5 seconds.
5. THE Platform SHALL support horizontal scaling of ProcessingEngine workers by increasing the `WORKER_CONCURRENCY` environment variable without requiring code changes or redeployment of other components.

---

### Requirement 15 [P0]: Failure Handling

**User Story:** As a developer, I want the platform to degrade gracefully under infrastructure failures, so that partial outages do not cause total data loss or silent failures.

#### Acceptance Criteria

1. IF the MetricsStore database connection fails, THEN THE Platform SHALL retry the connection up to 5 times with exponential backoff and log each failed attempt with the error details.
2. IF the Redis broker or Celery worker is unavailable, THEN THE ProcessingEngine SHALL fall back to synchronous in-process task execution and log a WARNING indicating degraded async processing mode.
3. IF the LLM API returns errors on 3 consecutive attempts for the same anomaly event, THEN THE RCAEngine SHALL create the Incident record without an RCA result and set `probable_cause` to `"RCA unavailable — LLM repeatedly failed"`, ensuring the Incident is still visible on the Dashboard.

---

### Requirement 16 [P1]: Security

**User Story:** As a developer, I want the platform to enforce basic security controls, so that it is safe to demonstrate and does not expose sensitive data.

#### Acceptance Criteria

1. THE IngestionService SHALL validate all incoming request payloads against defined JSON schemas and reject any request that contains unexpected fields or invalid data types with HTTP 422.
2. THE RCAEngine SHALL sanitize all LogEvent content by removing or masking patterns matching secrets (API keys, passwords, tokens) before including the content in any LLM prompt.
3. THE Platform SHOULD implement rate limiting on the POST `/api/v1/metrics` and POST `/api/v1/logs` endpoints, returning HTTP 429 when the configured request rate is exceeded.
4. THE Platform SHALL not write sensitive data (LLM API keys, database credentials, webhook URLs) to any log output.
