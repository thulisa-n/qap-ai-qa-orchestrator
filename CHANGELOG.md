# Changelog

All notable changes to this project are documented in this file.

## 2026-03 - Agentic Compliance Platform Milestone

- Added governance source-of-truth policy layer (`istqb` + org policy) with automation gating.
- Added critic, validator, and remediation decision stages in full QA flow.
- Added durable async job tracking (SQLite) with status and trace endpoints:
  - `GET /jobs/{jobId}`
  - `GET /jobs/{jobId}/trace`
  - `GET /jobs`
- Added closed-loop feedback analysis with optional Jira auto-comment.
- Added branch/context issue-key inference for feedback auto-comment mode.
- Added hybrid PKI mode:
  - `GET /pki/discover` (`demo|real_pki` stub)
  - `POST /pki/validate-profile`
- Added Docker runtime (`Dockerfile`, `docker-compose.yml`) and persistent job volume.
- Hardened CI security posture:
  - explicit `test_security.py` execution
  - `bandit` + `pip-audit` scans
  - blocking on `main`, non-blocking on feature/PR branches
- Added CI trace artifact uploads for transparent debugging in GitHub Actions.
- Expanded operational docs:
  - Jira rules (A/B/C) with deterministic payloads
  - closed-loop runbook
  - CI notification setup
  - go-live checklist
  - PKI hybrid mode guide
  - docs index
