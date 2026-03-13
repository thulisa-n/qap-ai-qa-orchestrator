# Execution Trace Example

This page shows a representative execution trace returned by QAP after
`POST /jira/full-qa-flow-async` completes.

## How to retrieve it

1. Trigger async flow and capture `jobId` from response.
2. Query:
   - `GET /jobs/{jobId}`
   - `GET /jobs/{jobId}/trace`

## Sample trace payload

```json
{
  "jobId": "9f6f4f9d-1f4a-438f-bf9f-f4b8892ef001",
  "issueKey": "QAP-22",
  "status": "succeeded",
  "executionTrace": {
    "steps": [
      "generate_tests",
      "analyze_coverage",
      "generate_playwright",
      "critic_validation",
      "automation_decision",
      "validator_gate",
      "remediation_planning",
      "governance_gate",
      "jira_reporting"
    ],
    "taskCreated": true
  },
  "validatorDecision": {
    "isValid": true,
    "verdict": "pass",
    "findings": [],
    "suggestedFixes": []
  },
  "remediationDecision": {
    "action": "none",
    "status": "not_needed",
    "notes": []
  },
  "governanceDecision": {
    "framework": "ISTQB Foundation 4.0 (baseline principles mapping)",
    "allowedForAutomation": true,
    "requiresHumanApproval": false,
    "coverageRatio": 0.86,
    "automationRisk": "medium",
    "violations": [],
    "summary": "Governance checks passed; automation is allowed."
  },
  "error": null
}
```

## How to interpret

- `executionTrace.steps`: ordered chain of decisions and gates.
- `validatorDecision`: deterministic quality/control verdict.
- `remediationDecision`: what QAP did after validation (`none`, `heal`, or `escalate`).
- `governanceDecision`: source-of-truth policy enforcement outcome.
- `taskCreated`: indicates whether automation task handoff happened.
