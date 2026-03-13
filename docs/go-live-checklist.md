# QAP Go-Live Checklist

Use this checklist before demos, stakeholder reviews, or production-like validation runs.

## 1) Start services

From repo root:

```bash
docker compose up --build
```

Confirm:

- Swagger: `http://127.0.0.1:8000/docs`
- Health: `http://127.0.0.1:8000/health`

## 2) Start public tunnel (for Jira cloud -> local API)

```bash
ngrok http 8000
```

Use URL:

- `https://<your-ngrok-url>.ngrok-free.dev/jira/full-qa-flow-async`

## 3) Validate Jira automation config

- Trigger: Issue transitioned -> `In QA`
- Condition: Description contains `Acceptance Criteria`
- Action: Send web request to `/jira/full-qa-flow-async`
- Headers:
  - `Content-Type: application/json`
  - `X-API-Key: <API_AUTH_TOKEN>`

## 4) Run one end-to-end ticket

1. Move ticket to `In QA`
2. Confirm accepted response includes `jobId`
3. Poll `GET /jobs/{jobId}` until `succeeded|failed`
4. Verify Jira comments include:
   - AI scenarios
   - critic validation
   - governance gate
   - automation decision

## 5) Run closed-loop feedback once

Call:

- `POST /feedback/analyze-failures`

Use:

- `commentOnJira: true`
- `issueKey` (or branch/context containing ticket key)

Verify `QAP Closed-Loop Feedback Analysis` comment appears on ticket.

## 6) Verify persistence evidence

Open DB:

- `app/.data/jobs.db`

Check table:

- `jobs`

Confirm:

- status transitions persisted
- timestamps present
- result/error persisted

## 7) CI wiring check (GitHub + Bitbucket)

Ensure variables/secrets are set:

- `QAP_API_BASE_URL`
- `QAP_API_AUTH_TOKEN`
- optional `JIRA_ISSUE_KEY`

Branch naming recommendation:

- include Jira key, e.g. `feature/QAP-120-closed-loop`

## 8) Demo recording flow (5-minute script)

1. Show architecture section in README
2. Show ticket moved to `In QA`
3. Show `jobId` + `/jobs/{jobId}` tracking
4. Show Jira comments (scenarios/critic/governance/decision)
5. Trigger feedback endpoint with failure payload
6. Show closed-loop comment on Jira
7. Show `jobs.db` evidence
8. Close with “human-in-the-loop governance” explanation
