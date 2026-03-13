# Observability Plan

## Why observability matters
QAP orchestrates Jira webhooks, AI generation, and file output. When something fails, teams need to answer quickly:
- what failed
- where it failed
- which issue/ticket was affected
- whether the request should be retried

## Current state
- Baseline HTTP errors and retries exist for Jira calls.
- CI catches regressions for backend contracts and Playwright tests.
- Async flow endpoint avoids webhook timeout pressure.
- Async flow now returns a `jobId`, with status visibility via `GET /jobs/{jobId}`.
- GitHub Actions uploads backend and Playwright execution trace artifacts for run-level debugging.

## Gaps to close for production readiness
- No structured logs with correlation IDs.
- No centralized metrics for latency, failure rate, and throughput.
- No alerting for background task failures.
- No job status endpoint for async workflow visibility.

## Recommended implementation

### 1) Structured logging
- Use JSON logs for API and background workflows.
- Include fields:
  - `request_id`
  - `jira_issue_key`
  - `endpoint`
  - `duration_ms`
  - `result` (`ok`/`error`)
  - `error_type`

### 2) Correlation IDs
- Accept incoming `X-Request-ID` when present.
- Generate one when missing.
- Propagate the ID across route handler, service calls, and background execution logs.

### 3) Metrics
Track at minimum:
- request count by endpoint/status
- p95 latency per endpoint
- background workflow success/failure counts
- AI call latency/error rate
- Jira API latency/error rate

### 4) Alerting
Set alerts for:
- sustained increase in 5xx responses
- repeated background workflow failures
- repeated Jira API failures (4xx/5xx spikes)
- prolonged queue/worker lag (if queue is introduced)

### 5) Async workflow visibility
- Current: durable SQLite-backed job tracking with:
  - `POST /jira/full-qa-flow-async` -> returns `jobId`
  - `GET /jobs/{jobId}` -> `pending|running|succeeded|failed` + timestamps
  - `GET /jobs/{jobId}/trace` -> execution steps and gate decisions (validator/remediation/governance)
  - `GET /jobs` -> recent job listing with optional `status`, `issueKey`, `limit`
- Next: move execution to a dedicated queue/worker model (while keeping durable status store).

## Suggested phased rollout
1. Add JSON logging + correlation IDs.
2. Add Prometheus-style metrics endpoint.
3. Add alerts in your chosen monitoring platform.
4. Move background execution to durable queue/worker.

This plan upgrades QAP from demo-friendly to production-traceable behavior.
