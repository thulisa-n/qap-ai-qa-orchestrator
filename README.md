# QAP AI QA Engine
AI-driven QA Agent Controller that turns Jira Acceptance Criteria into structured QA outputs with human-in-the-loop governance.

[![CI](https://github.com/thulisa-n/qap-ai-qa-orchestrator/actions/workflows/ci.yml/badge.svg)](https://github.com/thulisa-n/qap-ai-qa-orchestrator/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.13-blue.svg)](app/requirements.txt)
[![Docker](https://img.shields.io/badge/Docker-ready-2496ED.svg)](Dockerfile)
[![Playwright](https://img.shields.io/badge/Playwright-tests-2EAD33.svg)](playwright-tests)

## Quick Links
- [Quickstart](#quickstart)
- [Docker Quickstart](#docker-quickstart)
- [Core Endpoints](#core-endpoints)
- [Documentation Index](docs/index.md)
- [Go-live Checklist](docs/go-live-checklist.md)
- [Implementation Checklist](docs/implementation-checklist.md)
- [Demo Video](docs/ai-qa-demo.mov)

## What Problem This Solves
QA teams lose time manually translating Jira Acceptance Criteria into test scenarios, deciding automation priority, and creating starter test code. QAP accelerates this flow while keeping final decisions with QA engineers.

## Demo in 60 Seconds
1. Move a Jira issue to `In QA`.
2. Jira Automation calls `POST /jira/full-qa-flow-async`.
3. QAP posts:
   - AI-generated test scenarios
   - Critic validation (scenario/playwright quality score + recommendations)
   - Acceptance Criteria coverage report (`covered`/`missing`)
   - AI QA Agent decision (automation recommendation + risk)
4. QAP writes Playwright skeleton files and can create a linked automation task.
5. QA reviews and approves implementation direction.

## Demo Video
[▶ Watch the 83-second walkthrough](docs/ai-qa-demo.mov)

## Visual Architecture
```text
Jira Ticket (Acceptance Criteria)
              |
              v
   Jira Automation -> /jira/full-qa-flow-async
              |
              v
      QAP Agentic Controller
              |
      +-------+-------+-----------------------------+
      |               |                             |
      v               v                             v
  Scenario Gen    Playwright Gen               Async Job Store
      |               |                         (SQLite + /jobs)
      +-------+-------+
              v
         Critic Agent
              |
              v
     Governance Policy Gate
   (ISTQB + Org source-of-truth)
              |
      +-------+-----------------------------+
      |                                     |
      v                                     v
 Jira comments (scenarios/critic/      Linked automation task
 governance/decision)                  (only when policy allows)

 Closed-loop path:
 CI failure logs -> /feedback/analyze-failures -> classify flake/environment/regression -> Jira feedback comment
```

## Agentic Flow Logic
QAP follows a practical agentic loop with explicit control gates:

1. **Reason:** Parse AC and context, determine needed QA artifacts.
2. **Tool:** Generate scenarios and Playwright templates.
3. **Observe:** Evaluate coverage, run critic scoring, assess automation risk.
4. **Adjust:** Apply governance rules (ISTQB + org policy) before creating automation work.
5. **Act:** Post structured Jira comments and create linked tasks only when gates pass.
6. **Learn:** Analyze failed CI runs via closed-loop feedback and feed recommendations back into Jira.

This keeps AI behavior powerful but bounded: automation is never “blindly accepted,” and human QA remains the final authority.

## Verification & Remediation Architecture
QAP implements a "Trust but Verify" pattern with three safety layers:

1. **Critic Agent** -> Scores generated scenario/playwright quality.
2. **Validator Agent** -> Enforces deterministic business rules and consistency gates.
3. **Remediation Agent** -> Self-heals or escalates when checks fail.

[View Execution Trace Example ->](docs/execution-trace-example.md)

- Full QA flow returns `criticDecision`, `validatorDecision`, and `remediationDecision`.
- Automation task creation is blocked when the validator or governance gate does not pass.

## Tech Stack
- Python + FastAPI
- Pydantic
- Gemini (`google-genai`)
- Jira Cloud API + Jira Automation
- Playwright
- Pytest
- Bitbucket Pipelines + GitHub Actions

## CI Security Checks
- CI runs explicit security regression tests from `app/tests/test_security.py` on both GitHub Actions and Bitbucket Pipelines.
- CI also runs security scans:
  - SAST: `bandit -r app/src`
  - Dependency scan: `pip-audit -r app/requirements.txt`
- Scan policy:
  - `main`: blocking (pipeline fails on findings)
  - feature/PR branches: non-blocking visibility mode
- Security docs and evidence are in `docs/security-hardening-report.md`.
- GitHub Actions uploads backend/playwright trace artifacts for transparent debugging in the Actions UI.

## GitHub Debug Transparency
- Each GitHub Actions run publishes artifacts:
  - `backend-traces-<run_id>` (security/backend test logs)
  - `playwright-traces-<run_id>` (Playwright logs and reports)
- This gives hiring managers and reviewers direct run-level traceability without local reproduction.

## Why Playwright-first
This project is intentionally Playwright-first to maximize depth, stability, and execution quality on one automation platform.

QAP is designed to be framework-extensible in future releases, but current implementation and quality focus are optimized for Playwright workflows end to end.

## Quickstart
```bash
git clone <your-repo-url>
cd ai-qa-engine
python3 -m venv .venv
source .venv/bin/activate
pip install -r app/requirements.txt
cp app/.env.example app/.env
python -m uvicorn app.src.app:app --host 0.0.0.0 --port 8000
```

Open:
- Swagger: `http://127.0.0.1:8000/docs`
- Health: `http://127.0.0.1:8000/health`

## Docker Quickstart
```bash
cp app/.env.example app/.env
docker compose up --build
```

Open:
- Swagger: `http://127.0.0.1:8000/docs`
- Health: `http://127.0.0.1:8000/health`

Notes:
- Async job tracking is persisted in SQLite at `JOB_DB_PATH` (default: `app/.data/jobs.db`).
- In Docker, job data is persisted via the `qap_job_data` volume.

## Core Endpoints
- `POST /jira/full-qa-flow-async` (recommended webhook target)
- `GET /jobs/{jobId}` (async QA flow status: `pending|running|succeeded|failed`)
- `GET /jobs/{jobId}/trace` (execution trace + validator/remediation/governance decisions)
- `GET /jobs/{jobId}/explain-decision` (human-readable reason for allow/block decisions)
- `GET /jobs` (list recent jobs, supports `status`, `issueKey`, and `limit` filters)
- `POST /jobs/cleanup` (retention cleanup by age and optional status filter)
- `POST /jira/full-qa-flow`
- `POST /generate-both`
- `POST /generate-qa-report` (structured QA report template from AC/requirements)
- `POST /feedback/analyze-failures` (closed-loop failure triage: flake vs environment vs regression)
- `POST /pki/validate-profile` (hybrid PKI policy-as-code profile validation demo)
- `GET /pki/discover` (hybrid domain adapter: `demo|real_pki`)
- `GET /health`

## Job Trace Example
`GET /jobs/{jobId}/trace`

- Scenario generation -> success
- Playwright generation -> success
- Critic evaluation -> pass/needs_revision (with score)
- Validator -> pass/blocked
- Remediation -> none/heal/escalate
- Governance gate -> allowed/denied
- Decision explanation -> why automation was allowed or denied

## Documentation
- Docs index: `docs/index.md`
- Implementation checklist: `docs/implementation-checklist.md`
- Architecture: `docs/architecture.md`
- Jira automation rules and payload schemas: `docs/jira-automation-rules.md`
- Runbook and troubleshooting: `docs/runbook-troubleshooting.md`
- Closed-loop feedback runbook: `docs/closed-loop-feedback.md`
- CI failure notification setup: `docs/ci-failure-notification-setup.md`
- Go-live checklist: `docs/go-live-checklist.md`
- PKI hybrid mode: `docs/pki-hybrid-mode.md`
- Security: `docs/security-hardening-report.md`
- Data classification + redaction: `docs/data-classification-and-redaction.md`
- Governance + certification alignment: `docs/governance-certification-alignment.md`
- Observability: `docs/observability.md`
- PoC rollout: `docs/poc-implementation-guide.md`
- Contribution guide: `CONTRIBUTING.md`
- Changelog: `CHANGELOG.md`

## Source-of-Truth Governance (Phase 1)
- Governance policies are versioned in:
  - `app/src/governance/policies/istqb_foundation_v4.json`
  - `app/src/governance/policies/org_policy.json`
- The full QA flow now evaluates these policy files before creating automation tasks.
- Policy checks currently enforce:
  - minimum AC coverage ratio threshold
  - required security-focused scenario presence
  - max allowed automation risk
- A critic pass also scores generated artifacts; policy requires critic acceptance and minimum overall score before automation task creation.
- Result is surfaced in Jira comments as `QAP Governance Gate` and returned in API response as `governanceDecision`.
- This keeps AI recommendations bounded by auditable QA standards, while human QA remains the final decision maker.

## Closed-Loop Feedback Agent Starter (Phase 3)
- Send failed test output (Playwright/JUnit/generic) to `POST /feedback/analyze-failures`.
- QAP classifies failures as `flake`, `environment`, or `regression`.
- Optional Jira auto-comment mode:
  - set `commentOnJira: true`
  - provide `issueKey` (recommended), or include issue key in `branchName/context` so QAP can infer it
- Response includes:
  - per-test findings with evidence and suggested action
  - dominant failure classification and confidence
  - suggested regression tests
  - suggested Jira follow-up task summary
- This closes the loop from execution failures back into backlog-ready QA actions.
- CI auto-trigger support is included:
  - GitHub Actions and Bitbucket pipeline can auto-call `POST /feedback/analyze-failures` when Playwright fails.
  - Configure CI secrets/variables:
    - `QAP_API_BASE_URL`
    - `QAP_API_AUTH_TOKEN`
    - optional `JIRA_ISSUE_KEY` (fallback when branch/context does not include ticket key)

## Playwright test scopes
- Demo-verified runnable suite: `playwright-tests/tests/auth.spec.js` (works against `the-internet.herokuapp.com`)
- Generated app-specific templates: `playwright-tests/tests/generated/*.template.js` (intended for refinement in your product environment)

## FAQ
### Do I need to change Jira rules for coverage analysis?
No. Keep Jira Rule A simple and continue calling `POST /jira/full-qa-flow-async`. Coverage analysis runs inside the backend QA Agent flow, not in Jira rule logic.

## AI helper prompt (PR summaries)
```text
Create a detailed PR summary from this branch: include context/problem, goals, architecture changes, endpoint changes, security updates, test/CI changes, docs updates, migration notes, risks/trade-offs, verification steps, and a clear “why this approach works” section.
```

## Future Roadmap

### Recently completed
- Dedicated `Critic Agent` module in `app/src/agents/critic_agent.py`.
- Validator + remediation gates with explicit decision reporting in Jira comments and API response.
- Self-healing v1 controls:
  - one controlled heal retry,
  - `POST /jobs/{jobId}/retry`,
  - `POST /jobs/{jobId}/proceed-anyway`,
  - retry metadata in execution trace.
- Operations dashboard endpoints:
  - `GET /dashboard`
  - `GET /dashboard/metrics`
- Data safety hardening:
  - LLM input redaction + Jira output sanitization
  - retention cleanup endpoint `POST /jobs/cleanup`
  - data-classification documentation.

### Next milestones
Updated priorities for the next implementation cycle:
- Multi-attempt self-healing loop (up to 3 attempts) with strategy-specific regeneration.
- Healing session model and history API (`/healing/sessions`) with per-attempt analytics.
- Human override audit enrichment (`approvedBy`, `approvedAt`, `reason`) and stricter governance policy checks.
- GitHub Pages metrics badges for healing rate, escalation rate, and average attempts.
- Automated bug triage issue creation from closed-loop failure analysis.
- Optional framework adapters (Cypress/Selenium) without changing core governance/agent contracts.
