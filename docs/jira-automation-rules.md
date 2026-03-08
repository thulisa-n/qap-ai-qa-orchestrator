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
- Trigger: `Automation Approved = Yes` (or label `automation-approved`)
- Conditions:
  - issue has `qap-generated`
  - issue has `qap-needs-review`
- Actions:
  - call `POST /jira/create-automation-task` if needed, or transition linked task
  - remove `qap-needs-review`, add `qap-approved`

Optional comment:
```text
Automation approved by QA reviewer.
Proceeding with linked automation implementation task.
```

## Rule C: Completion feedback loop (optional)
- Trigger: linked automation task transitioned to `Done`
- Actions on parent issue:
  - comment with evidence/PR links
  - remove `qap-approved`
  - add `qap-automation-complete`

## Coverage analysis note
Coverage analysis is handled by backend orchestration. No extra Jira rule is required.
