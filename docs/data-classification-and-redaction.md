# Data Classification and Redaction

This document defines how QAP minimizes data exposure when interacting with LLMs,
Jira comments, and runtime traces.

## Classification model

- **Public**: project docs, generic test guidance, non-sensitive architecture data.
- **Internal**: issue keys, branch names, generalized failure reasons.
- **Restricted**: credentials, tokens, emails, account identifiers, internal-only URLs.

## LLM input policy

- Only minimum required AC/context is sent to LLM calls.
- Before prompt assembly, QAP redacts known sensitive patterns:
  - email addresses
  - Gemini-style API keys
  - Atlassian token patterns
  - inline secret assignments (`password=...`, `token=...`, `api_key=...`)

Implementation: `app/src/services/redaction_service.py`, used by `llm_service`.

## Jira output policy

- Before posting comments/issues back to Jira, QAP sanitizes text outputs using the same redaction controls.
- Safety truncation is applied for very long content to reduce accidental over-sharing.

Implementation: `jira_add_comment` and `jira_create_issue` in `app/src/services/jira_service.py`.

## Storage and retention policy

- Jobs persist request metadata and result traces for auditability.
- Optional retention cleanup endpoint is available:
  - `POST /jobs/cleanup?olderThanDays=<N>&status=<optional>`
- Recommended baseline:
  - keep succeeded jobs for 30-90 days
  - keep failed jobs for 90 days for investigations

## Operational guardrails

- `.env` files are ignored and must never be committed.
- Rotate leaked/posted tokens immediately.
- Prefer least-privilege Jira API tokens scoped to required actions only.
- Avoid attaching sensitive CI artifacts for production-like runs.
