# QAP AI QA Engine

AI-driven QA Automation Platform (QAP) that converts Jira tickets into:
- Manual test scenarios
- High-value automation candidates
- Playwright test names
- Security-minded QA notes

## Start-to-Finish Quickstart (recommended)
Use this section if you want a single guided path from setup to successful demo.

### 1) Clone and install
```bash
git clone <your-repo-url>
cd ai-qa-engine
python3 -m venv .venv
source .venv/bin/activate
pip install -r app/requirements.txt
```

### 2) Configure environment
```bash
cp app/.env.example app/.env
```
Set in `app/.env`:
- `GEMINI_API_KEY`
- `JIRA_BASE_URL`
- `JIRA_EMAIL`
- `JIRA_API_TOKEN`
- `JIRA_PROJECT_KEY`
- `API_AUTH_TOKEN` (used by Jira header `X-API-Key`)

### 3) Run the API
```bash
python -m uvicorn app.src.app:app --host 0.0.0.0 --port 8000
```
Keep this terminal open.

### 4) Expose local API to Jira Cloud (ngrok)
In a second terminal:
```bash
ngrok http 8000
```
Copy the HTTPS forwarding URL.

### 5) Verify API + tunnel
```bash
curl -i http://127.0.0.1:8000/health
curl -i https://<your-ngrok-url>/health
```
Both should return `200`.

### 6) Create Jira Rule A (In QA trigger)
Configure Jira Automation "Send web request" action:
- Method: `POST`
- URL: `https://<your-ngrok-url>/jira/full-qa-flow-async`
- Headers:
  - `Content-Type` = `application/json`
  - `X-API-Key` = `<API_AUTH_TOKEN value>`
- Body:
```json
{
  "issueKey": "{{issue.key}}",
  "acceptanceCriteria": {{issue.description.asJsonString}},
  "context": "Triggered by Jira Automation when issue transitions to In QA",
  "commentOnJira": true,
  "writePlaywrightFiles": true,
  "createAutomationTask": true,
  "automationIssueType": "Task",
  "automationSummaryPrefix": "Automation: Implement generated Playwright tests"
}
```

### 7) Run the Jira flow
1. Create a Jira ticket with acceptance criteria in the description.
2. Move ticket to `In QA`.
3. Confirm:
   - Trigger comment appears
   - Web request shows success in audit log
   - AI Generated Test Scenarios comment appears
   - AI Automation Decision comment appears
   - Automation task is created when candidate is approved by decision logic

### 8) Execute generated/refined Playwright test
```bash
cd playwright-tests
npx playwright install
BASE_URL=https://the-internet.herokuapp.com TEST_USER=tomsmith TEST_PASS=SuperSecretPassword! npx playwright test tests/auth.spec.js
```

### 9) Troubleshoot quickly
- `401 Unauthorized`: Jira `X-API-Key` value does not match `API_AUTH_TOKEN`.
- `422 json_invalid`: use `{{issue.description.asJsonString}}` in body.
- ngrok `ERR_NGROK_3200`: tunnel offline/stale URL.
- Playwright browser error: run `npx playwright install`.
- Jira timeout: use `/jira/full-qa-flow-async` (not sync endpoint).

## Run locally
1. Create and activate a virtual environment:
   - `python3 -m venv .venv`
   - `source .venv/bin/activate`
2. Copy env file:
   - `cp app/.env.example app/.env`
3. Install dependencies:
   - `pip install -r app/requirements.txt`
4. Start server:
   - `python -m uvicorn app.src.app:app --reload`

## API docs and health
- Swagger UI: `http://127.0.0.1:8000/docs`
- Health check: `GET /health`

## API authentication (recommended)
- Set `API_AUTH_TOKEN` in `app/.env` to enable auth.
- When enabled, send `X-API-Key: <API_AUTH_TOKEN>` on all non-health endpoints.
- If `API_AUTH_TOKEN` is empty, auth is disabled for local development.

## Main endpoints
- `POST /generate-tests`
- `POST /generate-playwright`
- `POST /generate-both`
- `POST /jira/comment-tests`
- `POST /playwright/write-files`
- `POST /jira/create-automation-task`
- `POST /jira/full-qa-flow`
- `POST /jira/full-qa-flow-async` (recommended for Jira automation webhooks to avoid 30s timeout)

## Jira automation rules (recommended)
You can run in two modes:

- **Autonomous mode (AI decides):** only Rule A is required.
- **Governance demo mode (show process):** use Rule A + Rule B (+ Rule C optional).

To match the "AI assists, humans decide" workflow, use at least **2 rules** (3rd optional):

1) **Rule A - In QA Orchestration (required)**
- Trigger: issue transitioned to `In QA`
- Condition: Acceptance Criteria exists
- Actions:
  - add "QA Automation Triggered (QAP)" comment
  - call `POST /jira/full-qa-flow` with `X-API-Key`
  - set labels like `qap-generated`, `qap-needs-review`
- Behavior:
  - backend AI decides if automation should be created (`automationDecision`)
  - if yes, it creates linked automation task with Playwright skeleton
  - if no, it keeps output as manual-first guidance

2) **Rule B - Human approval gate for automation task (recommended)**
- Trigger: custom field/checkbox `Automation Approved = Yes` (or label `automation-approved`)
- Purpose: only create/advance automation work after QA review
- Action:
  - either call `POST /jira/create-automation-task`
  - or transition/update the generated automation task

3) **Rule C - Completion feedback loop (optional but high value)**
- Trigger: linked automation task moved to `Done`
- Actions:
  - comment on parent ticket with result links (branch/PR/test report)
  - remove `qap-needs-review`, add `qap-automation-complete`

This keeps human QA as the final gatekeeper while still accelerating scenario and skeleton generation.

## Jira rule implementation playbook (copy/paste)

### Rule A - In QA orchestration (required)
Use this rule in all modes.

- Trigger: `Issue transitioned` -> `To status: In QA`
- Condition: Acceptance Criteria field (or Description) is not empty
- Action 1 (Add comment) - use this exact text:

```text
QA Automation Triggered (QAP)
This issue has entered **In QA** and meets quality criteria.
Acceptance Criteria detected
Preparing:
- Test scenarios
- Automation candidate selection
- Playwright test skeletons (next phase)
—QA Automation Platform
```

- Action 2 (Send web request):
  - Method: `POST`
  - URL: `https://<your-qap-host>/jira/full-qa-flow-async`
  - Headers:
    - `Content-Type: application/json`
    - `X-API-Key: <API_AUTH_TOKEN>`
  - Body:

```json
{
  "issueKey": "{{issue.key}}",
  "acceptanceCriteria": {{issue.description.asJsonString}},
  "context": "Triggered by Jira Automation when issue transitions to In QA",
  "commentOnJira": true,
  "writePlaywrightFiles": true,
  "createAutomationTask": true,
  "automationIssueType": "Task",
  "automationSummaryPrefix": "Automation: Implement generated Playwright tests"
}
```

Note: if AC is in a custom field, replace `issue.description` with that custom field smart value and keep `.asJsonString`.
If your Jira project does not support `Sub-task`, the backend automatically falls back to `Task` and links it back to the parent issue.

### Full Rule A request schema
Use this schema as the canonical shape for the Rule A webhook body.

```json
{
  "type": "object",
  "required": [
    "issueKey",
    "acceptanceCriteria"
  ],
  "properties": {
    "issueKey": {
      "type": "string",
      "description": "Parent Jira issue key (example: QAP-12)"
    },
    "acceptanceCriteria": {
      "type": "string",
      "description": "Acceptance criteria text extracted from Jira smart value"
    },
    "context": {
      "type": "string",
      "description": "Optional context for generation prompts"
    },
    "baseUrl": {
      "type": "string",
      "description": "Optional app base URL for generated Playwright tests"
    },
    "commentOnJira": {
      "type": "boolean",
      "default": true,
      "description": "Post generated scenarios and AI decision comments on parent issue"
    },
    "writePlaywrightFiles": {
      "type": "boolean",
      "default": true,
      "description": "Write generated Playwright files to local playwright-tests folder"
    },
    "createAutomationTask": {
      "type": "boolean",
      "default": true,
      "description": "Allow backend to create automation task if AI decides candidate = yes"
    },
    "automationIssueType": {
      "type": "string",
      "enum": ["Task", "Sub-task", "Subtask"],
      "default": "Task",
      "description": "Requested Jira issue type for automation work item"
    },
    "automationSummaryPrefix": {
      "type": "string",
      "default": "Automation: Implement generated Playwright tests",
      "description": "Prefix used in created automation task summary"
    }
  }
}
```

### Rule B - Human approval gate (recommended for governance demo)
Use this if you want to visibly show human sign-off before automation starts.

- Trigger: `Field value changed` -> `Automation Approved` = `Yes` (or label `automation-approved`)
- Conditions:
  - issue has `qap-generated`
  - issue has `qap-needs-review`
- Action:
  - Send web request to `POST /jira/create-automation-task` (only if task not yet created), or transition linked task to `To Do`
  - Remove label `qap-needs-review`
  - Add label `qap-approved`
  - Optional comment:

```text
Automation approved by QA reviewer.
Proceeding with linked automation implementation task.
```

### Rule C - Completion feedback loop (optional, recommended)
Use this to demonstrate closed-loop governance.

- Trigger: linked automation task transitioned to `Done`
- Conditions: issue type is `Task` (or your automation issue type), summary contains `Automation:`
- Actions on parent story:
  - Add comment:

```text
Automation task completed: {{issue.key}}
Please review test evidence, PR links, and execution report.
```

  - Remove `qap-approved`
  - Add `qap-automation-complete`
  - Optional transition parent issue to your next QA status

## Ticket AC examples for demo/testing

Use these three tickets to prove each path in your orchestrator.

### Ticket 1 - Scenario blueprint (manual-first, your In QA trigger)
**Summary:** Login with lockout and generic error handling  
**Acceptance Criteria:**
- User can log in with valid username/password.
- Invalid password shows generic error message and does not reveal whether username exists.
- After 5 failed attempts in 10 minutes, account is locked for 15 minutes.
- Locked account sees a clear lockout message and cannot authenticate.
- Successful login after lock period restores normal access.
- Audit event is recorded for failed attempts and lockout.

Expected PoC outcome:
- strong manual scenario generation
- automation decision may be `partial_automation` depending on environment stability

### Ticket 2 - Strong automation candidate (should create automation task)
**Summary:** Role-based access to Admin Billing page  
**Acceptance Criteria:**
- Admin users can access `/admin/billing` and view invoice controls.
- Standard users receive `403` for `/admin/billing`.
- Unauthorized users are redirected to login.
- Session timeout after 15 minutes of inactivity requires re-authentication.
- Access control behavior is consistent across Chrome and Firefox.
- All outcomes are deterministic and test data is stable.

Expected PoC outcome:
- `automationDecision.shouldCreateAutomationTask = true`
- linked automation task with Playwright skeleton is created

### Ticket 3 - Critical but not a good immediate automation candidate
**Summary:** Marketing landing page copy and layout experiment  
**Acceptance Criteria:**
- Hero headline and CTA copy vary by A/B cohort.
- Multiple content blocks are controlled by CMS and may change daily.
- Visual hierarchy should "feel clearer" based on UX review.
- Stakeholders can update banner text without deployment.
- Final design/content is expected to iterate quickly for 2 weeks.

Expected PoC outcome:
- `automationDecision.shouldCreateAutomationTask = false`
- recommendation remains manual-first (`manual_only`)
- avoids low-value brittle automation

## CI
Pull requests run:
- backend smoke checks (Python import/compile validation)
- backend API/security regression tests (`pytest`)
- Playwright UI tests

## Running generated Playwright tests (human-in-the-loop)
Generated tests are a starting point. A QA/SDET should always review and refine selectors/assertions.

### Example flow using a generated task file
1. Install browser binaries (one-time per environment):

```bash
cd playwright-tests
npx playwright install
```

2. Run a generated/refined spec against the demo app:

```bash
BASE_URL=https://the-internet.herokuapp.com TEST_USER=tomsmith TEST_PASS=SuperSecretPassword! npx playwright test tests/auth.spec.js
```

### Expected result for this PoC demo
- 2 tests pass (valid login + invalid password)
- 1 test skipped (locked-account scenario is not supported by `the-internet.herokuapp.com`)

### Common errors and how to fix them
- **`ERR_NGROK_3200` (endpoint offline)**: ngrok tunnel is not running or URL changed. Restart `ngrok http 8000` and update Jira rule URL.
- **`401 Unauthorized`**: `X-API-Key` in Jira does not match `API_AUTH_TOKEN` in `app/.env` loaded by running API process. Update header value and restart API if token changed.
- **`422 json_invalid` from webhook**: Jira smart value inserted raw control characters/newlines. Use `{{issue.description.asJsonString}}` in request body.
- **Jira webhook timeout (30s)**: use `POST /jira/full-qa-flow-async` instead of sync endpoint.
- **`browserType.launch: Executable doesn't exist`**: Playwright browsers not installed. Run `npx playwright install`.
- **Selector timeout on generated tests**: AI used non-existent selectors (e.g., `data-testid`). Refine tests to real selectors (e.g., `#username`, `#password`, `#flash`) for target app.

## Architecture
See `docs/architecture.md` for the service boundaries, scalability choices, and extension patterns.

## Security report
See `docs/security-hardening-report.md` for implemented controls, residual risks, and validation guidance.

## PoC rollout guide
See `docs/poc-implementation-guide.md` for Bitbucket sharing steps and Jira automation rule setup for `In QA` triggers.
