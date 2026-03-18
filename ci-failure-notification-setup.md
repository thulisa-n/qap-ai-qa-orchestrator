# CI Failure Notification Setup

This guide configures automatic failure-to-Jira feedback comments when Playwright tests fail in CI.

## What this enables

On Playwright test failure, CI automatically calls:

- `POST /feedback/analyze-failures`

with:

- `commentOnJira: true`
- failure log text
- branch/run context

QAP then posts a `QAP Closed-Loop Feedback Analysis` comment to Jira.

## Required app behavior

Already implemented in QAP:

- explicit issue key mode (`issueKey`)
- inferred issue key mode from `branchName`/`context`/`failureReport`
- fallback error if no issue key can be resolved

## GitHub Actions setup

File already wired:

- `.github/workflows/ci.yml`

Add repository secrets:

1. `QAP_API_BASE_URL`  
   Example: `https://<your-ngrok-or-host>.ngrok-free.dev`
2. `QAP_API_AUTH_TOKEN`  
   Must match your app `API_AUTH_TOKEN`
3. `JIRA_ISSUE_KEY` *(optional fallback)*  
   Example: `QAP-123`

How to add secrets:

- GitHub repo -> `Settings` -> `Secrets and variables` -> `Actions` -> `New repository secret`

## Bitbucket Pipelines setup

File already wired:

- `bitbucket-pipelines.yml`

Add repository variables:

1. `QAP_API_BASE_URL`
2. `QAP_API_AUTH_TOKEN`
3. `JIRA_ISSUE_KEY` *(optional fallback)*

How to add variables:

- Bitbucket repo -> `Repository settings` -> `Pipelines` -> `Repository variables`

## Branch naming recommendation

Use Jira keys in branch names so issue resolution is automatic:

- `feature/QAP-77-feedback-automation`
- `bugfix/QAP-120-login-timeout`

## Verification checklist

1. Ensure QAP API is reachable from CI (`QAP_API_BASE_URL` public).
2. Trigger a branch/PR run with a controlled Playwright failure.
3. Confirm CI log shows QAP notification step executed.
4. Confirm Jira ticket receives `QAP Closed-Loop Feedback Analysis` comment.
5. Confirm API response includes `resolvedIssueKey` and `jiraComment.status=comment_added`.

## Common failure causes

- `401 Unauthorized` from QAP
  - `QAP_API_AUTH_TOKEN` does not match app token
- `400 Could not resolve issueKey`
  - no `issueKey` provided and no Jira key in branch/context/failure text
- webhook timeout/network errors
  - `QAP_API_BASE_URL` not publicly reachable (restart ngrok or use stable host)
