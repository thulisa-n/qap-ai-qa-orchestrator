# Jira Automation Rules

This document contains the complete Jira automation setup for QAP.

## Recommended modes
- **Autonomous mode:** Rule A only.
- **Governance mode:** Rule A + Rule B (+ Rule C optional).

## Rule A: In QA orchestration (required)

### Trigger
- Issue transitioned
- To status: `In QA`

### Condition
- Acceptance Criteria exists (description or custom field)

### Action 1: Add comment
```text
QA Automation Triggered (QAP)
This issue has entered **In QA** and meets quality criteria.
Acceptance Criteria detected
Preparing:
- Test scenarios
- Coverage analysis
- Automation candidate selection
- Playwright test skeletons (next phase)
—QA Automation Platform
```

### Action 2: Send web request
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

Note: If AC is in a custom field, replace `issue.description` with your custom smart value and keep `.asJsonString`.

## Rule A request schema (canonical)
```json
{
  "type": "object",
  "required": ["issueKey", "acceptanceCriteria"],
  "properties": {
    "issueKey": { "type": "string" },
    "acceptanceCriteria": { "type": "string" },
    "context": { "type": "string" },
    "baseUrl": { "type": "string" },
    "commentOnJira": { "type": "boolean", "default": true },
    "writePlaywrightFiles": { "type": "boolean", "default": true },
    "createAutomationTask": { "type": "boolean", "default": true },
    "automationIssueType": {
      "type": "string",
      "enum": ["Task", "Sub-task", "Subtask"],
      "default": "Task"
    },
    "automationSummaryPrefix": {
      "type": "string",
      "default": "Automation: Implement generated Playwright tests"
    }
  }
}
```

## Rule B: Human approval gate (recommended)
Use this rule to automatically create a remediation follow-up when governance blocks automation.

### Step-by-step setup

1) **Trigger**
- Type: `Issue commented`

2) **Condition A: Comment content**
- Type: `Advanced compare condition` (or "Comment contains" if your Jira plan supports it)
- Value should contain: `QAP Governance Gate`

3) **Condition B: Blocked decision text**
- Add another condition on the same comment:
- Contains: `Allowed for automation: No`

4) **Action: Create issue**
- Issue type: `Task`
- Summary:
  - `{{issue.key}} | QAP Follow-up: Resolve governance/validator findings`
- Description (recommended):
```text
QAP governance/validator gate blocked automation task creation.

Parent issue: {{issue.key}}

What happened
- Governance comment indicated: Allowed for automation: No
- Review validator/remediation findings and apply fixes.

Expected actions
1. Review QAP comments on parent issue
2. Resolve policy violations and validator findings
3. Re-run In QA workflow after updates
```

5) **Action (optional): Link issues**
- Link created follow-up task back to parent issue (`Relates`)

6) **Action (optional): Add parent comment**
```text
QAP Rule B created a remediation follow-up task because automation was blocked by governance/validator checks.
```

## Rule C: Completion feedback loop (optional)
Use this rule to automatically call QAP closed-loop analysis when CI failure evidence is posted to a Jira issue.

### Step-by-step setup

1) **Trigger**
- Type: `Issue commented`

2) **Condition**
- Comment contains a CI failure marker, for example:
  - `GitHub Actions failure`
  - or `Bitbucket pipeline failure`

3) **Action: Send web request**
- Method: `POST`
- URL: `https://<your-qap-host>/feedback/analyze-failures`
- Headers:
  - `Content-Type: application/json`
  - `X-API-Key: <API_AUTH_TOKEN>`
- Body:
```json
{
  "source": "playwright",
  "issueKey": "{{issue.key}}",
  "commentOnJira": true,
  "failureReport": {{comment.body.asJsonString}},
  "context": "Triggered by Jira Rule C from CI failure comment"
}
```

4) **Optional: Guard against loops**
- Add condition to ignore comments that already contain:
  - `QAP Closed-Loop Feedback Analysis`

### Alternative for CI-first design (recommended)
If you already configured CI auto-callback (`.github/workflows/ci.yml` or `bitbucket-pipelines.yml`), Rule C is optional.
CI can call `/feedback/analyze-failures` directly and include branch/run URL context.

## Deterministic payload blocks (copy/paste)

### Rule A deterministic test payload
Use this in Jira "Send web request" body for deterministic demo runs:
```json
{
  "issueKey": "{{issue.key}}",
  "acceptanceCriteria": "h3. Acceptance Criteria\n- Valid credentials allow login.\n- Invalid password shows clear error.\n- Session timeout requires re-authentication.\n- Role-based access is enforced for protected routes.\n- Error responses do not leak stack traces.",
  "context": "Deterministic demo payload from Jira Rule A",
  "commentOnJira": true,
  "writePlaywrightFiles": true,
  "createAutomationTask": true,
  "automationIssueType": "Task",
  "automationSummaryPrefix": "Automation: Implement generated Playwright tests"
}
```

### Rule C deterministic feedback payload
```json
{
  "source": "playwright",
  "issueKey": "{{issue.key}}",
  "commentOnJira": true,
  "failureReport": "Error: Timeout 30000ms exceeded while waiting for locator\nExpected status 200, received 500 for /api/billing/widget-data",
  "context": "Deterministic closed-loop test payload from Jira Rule C"
}
```

## Coverage analysis note
Coverage analysis is handled by backend orchestration. No extra Jira rule is required.
