# QAP AI QA Engine
AI-driven QA Agent Controller that turns Jira Acceptance Criteria into structured QA outputs with human-in-the-loop governance.

## What Problem This Solves
QA teams lose time manually translating Jira Acceptance Criteria into test scenarios, deciding automation priority, and creating starter test code. QAP accelerates this flow while keeping final decisions with QA engineers.

## Demo in 60 Seconds
1. Move a Jira issue to `In QA`.
2. Jira Automation calls `POST /jira/full-qa-flow-async`.
3. QAP posts:
   - AI-generated test scenarios
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
      QAP AI QA Agent Controller
              |
    +---------+---------+-----------+
    |         |         |           |
    v         v         v           v
Scenario   Coverage   Automation   Playwright
Tool       Tool       Decision     Tool
                     (incl. risk)
              \         |         /
               \        |        /
                v       v       v
           Jira Comments + Linked Task + Test Files
```

## Tech Stack
- Python + FastAPI
- Pydantic
- Gemini (`google-genai`)
- Jira Cloud API + Jira Automation
- Playwright
- Pytest
- Bitbucket Pipelines + GitHub Actions

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

## Core Endpoints
- `POST /jira/full-qa-flow-async` (recommended webhook target)
- `POST /jira/full-qa-flow`
- `POST /generate-both`
- `POST /generate-qa-report` (structured QA report template from AC/requirements)
- `GET /health`

## Documentation
- Architecture: `docs/architecture.md`
- Jira automation rules and payload schemas: `docs/jira-automation-rules.md`
- Runbook and troubleshooting: `docs/runbook-troubleshooting.md`
- Security: `docs/security-hardening-report.md`
- Observability: `docs/observability.md`
- PoC rollout: `docs/poc-implementation-guide.md`
- Contribution guide: `CONTRIBUTING.md`

## FAQ
### Do I need to change Jira rules for coverage analysis?
No. Keep Jira Rule A simple and continue calling `POST /jira/full-qa-flow-async`. Coverage analysis runs inside the backend QA Agent flow, not in Jira rule logic.

## AI helper prompt (PR summaries)
```text
Create a detailed PR summary from this branch: include context/problem, goals, architecture changes, endpoint changes, security updates, test/CI changes, docs updates, migration notes, risks/trade-offs, verification steps, and a clear “why this approach works” section.
```

## Future Roadmap
- Agentic orchestration loop (`reason -> tool -> observe -> adjust`) on top of the current controller
- Human feedback loop from Jira comments to refine scenarios and decisions
- Closed-loop quality from test execution results and CI signals
- Automated bug triage with AI-generated Jira bug summaries from failures
- Playwright quality critic pass for flaky selector and brittle assertion detection
- Optional framework adapters (Cypress/Selenium) without changing core agent logic
