# Closed-Loop Feedback Agent Runbook

This guide shows how to use the failure-analysis endpoint to classify failed test output and generate actionable QA follow-ups.

## Endpoint

- `POST /feedback/analyze-failures`

## Auth

All requests require:

- Header: `X-API-Key: <API_AUTH_TOKEN>`

## Mode 1: Analysis only (no Jira write)

Use this when you want triage output but do not want to post comments automatically.

### Example request body

```json
{
  "source": "playwright",
  "failureReport": "Error: net::ERR_CONNECTION_REFUSED\nExpected status 200, received 500 for /api/billing/widget-data",
  "context": "CI run #122 failed on auth and billing suites."
}
```

### Example curl

```bash
curl -X POST "http://127.0.0.1:8000/feedback/analyze-failures" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-auth-token" \
  -d '{
    "source": "playwright",
    "failureReport": "Error: Timeout 30000ms exceeded while waiting for locator",
    "context": "Nightly execution run."
  }'
```

## Mode 2: Auto-comment on Jira issue

Use this when you want the analysis posted to the Jira ticket automatically.

Required fields:

- `commentOnJira: true`
- `issueKey: "<JIRA-KEY>"` (recommended)
- or include a ticket key in `branchName`/`context` (for example `feature/QAP-120-hardening`) so QAP can infer the issue key.

### Example request body

```json
{
  "source": "playwright",
  "issueKey": "QAP-20",
  "commentOnJira": true,
  "failureReport": "Error: Timeout 30000ms exceeded while waiting for locator",
  "context": "Nightly run on chrome only."
}
```

### Deterministic demo payload (copy/paste)

```json
{
  "source": "playwright",
  "issueKey": "QAP-XXX",
  "commentOnJira": true,
  "failureReport": "Error: Timeout 30000ms exceeded while waiting for locator\nExpected status 200, received 500 for /api/billing/widget-data",
  "context": "Deterministic closed-loop demo payload."
}
```

### Example response (abbreviated)

```json
{
  "summary": "Most failures appear environment-related with one regression candidate.",
  "dominantClassification": "environment",
  "confidence": 0.82,
  "findings": [
    {
      "testName": "Authentication Tests › should allow login",
      "classification": "environment",
      "confidence": 0.86,
      "evidence": ["net::ERR_CONNECTION_REFUSED"],
      "suggestedAction": "Verify target environment availability and retry."
    }
  ],
  "suggestedJiraTaskSummary": "Closed-loop follow-up: harden environment preflight checks",
  "jiraComment": {
    "issueKey": "QAP-20",
    "status": "comment_added"
  }
}
```

## Validation behavior

- If `commentOnJira` is `true` and `issueKey` is missing, the API returns `400`.
- Output is schema-validated and returns `502` if model output is malformed.

## Classification semantics

- `flake`: likely nondeterministic test behavior (timing/selectors/retries).
- `environment`: infra/service/config instability (network/auth/env availability).
- `regression`: likely product behavior break requiring bug triage and coverage expansion.
