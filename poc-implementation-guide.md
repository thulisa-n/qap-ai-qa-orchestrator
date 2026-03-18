# PoC Implementation Guide (Bitbucket + Jira Automation)

## Purpose
This PoC shows how AI can improve QA quality and reduce manual effort by automatically generating:
- test scenarios
- automation candidate recommendations
- Playwright starter tests

## 1) Sharing in Bitbucket (similar to GitHub)
Yes, Bitbucket supports the same collaboration pattern as GitHub: repos, branch permissions, pull requests, reviewers, and pipelines.

### Recommended sharing setup
1. Create a Bitbucket repository for the PoC.
2. Push this project and enable branch protections (at minimum on `main`).
3. Add teammates with least-privilege roles:
   - admins: maintainers
   - write: core dev/qa
   - read: stakeholders and auditors
4. Require pull requests and CI status checks before merge.
5. Share repo URL with collaborators and provide this document as onboarding.

## 2) Local implementation steps
1. Clone the repository.
2. Create virtual environment:
   - `python3 -m venv .venv`
   - `source .venv/bin/activate`
3. Configure env:
   - `cp app/.env.example app/.env`
   - set `GEMINI_API_KEY`
   - set Jira values (`JIRA_BASE_URL`, `JIRA_EMAIL`, `JIRA_API_TOKEN`, `JIRA_PROJECT_KEY`)
   - set `API_AUTH_TOKEN` for protected API access
4. Install dependencies:
   - `pip install -r app/requirements.txt`
5. Start API:
   - `python -m uvicorn app.src.app:app --reload`
6. Verify:
   - `GET /health`
   - `GET /docs`

## 3) Jira automation rules for a human-in-the-loop flow

Use Jira Automation to trigger AI early, then keep human QA as the decision maker.

### Rule A: In QA orchestration (required)
Use this rule when issue moves to `In QA`.

#### Rule configuration
1. **Trigger**: *Issue transitioned*
   - To status: `In QA`
2. **Condition**: Acceptance Criteria exists
   - If using Jira field: `Acceptance criteria` is not empty
   - Or if in description: check description contains expected section/pattern
3. **Action (comment)**: add the progress message below
4. **Action (web request)**: call QA engine endpoint
5. **Action**: add labels `qap-generated`, `qap-needs-review`
6. **Expected backend decision behavior**:
   - API returns `automationDecision` with:
     - `shouldCreateAutomationTask`
     - `confidence`
     - `reason`
     - `recommendedCoverage`
   - When `shouldCreateAutomationTask=true`, automation task is created with skeleton and implementation guidance.
   - When false, it remains manual-first and skips task creation.

#### Suggested Jira comment text
Use this exact content in a Jira "Add comment" action:

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

#### Suggested web request action
- Method: `POST`
- URL: `https://<your-qap-host>/jira/full-qa-flow-async`
- Headers:
  - `Content-Type: application/json`
  - `X-API-Key: <API_AUTH_TOKEN>`
- Body template:

```json
{
  "issueKey": "{{issue.key}}",
  "acceptanceCriteria": {{issue.description.asJsonString}},
  "context": "Triggered by Jira Automation on transition to In QA",
  "commentOnJira": true,
  "writePlaywrightFiles": true,
  "createAutomationTask": true,
  "automationIssueType": "Task",
  "automationSummaryPrefix": "Automation: Implement generated Playwright tests"
}
```

Note: If your Acceptance Criteria is in a custom field, replace `issue.description` with the custom field smart value and keep `.asJsonString`.

### Rule B: Human approval gate (recommended)
Use this rule to avoid auto-creating work before a QA human validates scenario quality.

#### Rule configuration
1. **Trigger**:
   - Field value changed: `Automation Approved` -> `Yes`
   - or label added: `automation-approved`
2. **Condition**:
   - issue has label `qap-generated`
3. **Action**:
   - call `POST /jira/create-automation-task` (if task not created yet), or
   - transition linked automation task to `To Do`
4. **Action**:
   - remove label `qap-needs-review`
   - add label `qap-approved`

### Rule C: Automation completion sync (optional, recommended)
Use this for visibility and stakeholder confidence.

#### Rule configuration
1. **Trigger**:
   - linked automation task transitioned to `Done`
2. **Action**:
   - add comment to parent issue with:
     - task key
     - test report link
     - PR link
3. **Action**:
   - add label `qap-automation-complete`

## 4) Security posture for PoC demos
For stakeholder demos and customer conversations, highlight:
- API key protection via `X-API-Key`
- strict input validation and size limits
- prompt-injection checks
- path traversal prevention for generated files
- reduced error detail exposure
- CI security tests in Bitbucket Pipeline

Also share `docs/security-hardening-report.md` as evidence.

## 5) Demo flow for stakeholders
1. Move a Jira ticket to `In QA`.
2. Show automation comment posted by Rule A.
3. QA reviewer checks scenario blueprint + automation candidates.
4. Trigger Rule B by approving automation.
5. Show generated/linked automation task and Playwright skeleton.
6. Show time saved versus manual scenario writing.

## 6) Success metrics for PoC
- Lead time reduction from ticket to first QA artifact.
- % of tickets with generated test scenarios.
- % of generated cases accepted by QA without major edits.
- Playwright skeleton reuse rate.
- Defect discovery earlier in lifecycle (pre-UAT).
