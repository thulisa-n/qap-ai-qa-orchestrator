# AI QA Engine Architecture

## Goals
- Keep API behavior predictable as traffic grows.
- Reduce regression risk by isolating responsibilities.
- Make features easier to add without touching unrelated code.
- Fail safely when external dependencies (Gemini/Jira) are slow or invalid.

## Current module layout

```text
app/src/
  app.py
  settings.py
  schemas.py
  routers/
    generation.py
    jira.py
  services/
    llm_service.py
    jira_service.py
    file_service.py
```

## How requests flow
1. A request enters a route in `routers/`.
2. Request and response payloads are validated by `schemas.py`.
3. Route handlers delegate external work to `services/`.
4. Service results are converted back to typed response models.
5. FastAPI returns stable JSON contracts to clients.

## Responsibilities by layer

### `app.py` (composition root)
- Creates the FastAPI app.
- Registers routers.
- Keeps startup lightweight and deterministic.

### `settings.py` (configuration boundary)
- Loads values from `app/.env` once.
- Exposes a typed `Settings` object through `get_settings()`.
- Prevents repeated env parsing in every request.

### `schemas.py` (contract boundary)
- Central place for request/response schemas.
- Supports both camelCase and snake_case aliases where needed.
- Eliminates duplicated model definitions and silent overrides.

### `routers/*.py` (transport boundary)
- Own HTTP concerns only: endpoint wiring and HTTP exceptions.
- No direct low-level third-party HTTP calls.
- Keeps route code short and easier to test.

### `services/*.py` (integration boundary)
- `llm_service.py`: prompt builders and Gemini call wrapper.
- `jira_service.py`: Jira auth, ADF formatting, issue/comment API calls with retry.
- `file_service.py`: Playwright file write behavior.
- Encapsulates external API details so route code stays stable.

## Why this structure scales better

### 1) Safer change isolation
Updating Jira logic now happens in `jira_service.py` only. Route logic and schemas remain untouched, lowering the chance of accidental regressions.

### 2) Better runtime reliability
Jira calls use a retry-capable HTTP session for transient failures (429/5xx). This improves resilience under network or provider instability.

### 3) Stable API contracts
Typed models in one file stop drift between endpoints and docs. Duplicate route/model definitions are removed, so behavior is deterministic.

### 4) Easier horizontal scaling
Stateless app modules and centralized configuration make it straightforward to run multiple Uvicorn workers/containers.

### 5) Faster onboarding and maintenance
Developers can quickly locate behavior:
- endpoint logic in `routers/`
- external integrations in `services/`
- payload shapes in `schemas.py`

## Operational benefits
- Health endpoint remains available for probes.
- Missing/invalid external configuration fails at call time with explicit errors.
- CI now verifies backend import/compile health before UI tests, catching breakages earlier.

## Recommended next scale steps
- Add async execution (`async def` + `httpx.AsyncClient`) for higher concurrency.
- Introduce structured logging with request IDs.
- Add a background job queue for long-running generation workflows.
- Add backend test suite (`pytest`) for route and service contracts.
- Containerize app with explicit runtime limits and worker count.

## Trade-offs
- More files/modules increase initial navigation overhead.
- Strict schema validation may reject previously tolerated malformed payloads.
- Retry logic adds small latency on hard failures, but improves success rate on transient issues.

These trade-offs are intentional for production safety and long-term maintainability.
