# Implementation Checklist

Use this as the working execution plan for daily progress.

## Current status snapshot

- [x] Async QA flow with durable job store (`/jira/full-qa-flow-async`, SQLite).
- [x] Critic + validator + remediation decisions returned and traced.
- [x] Manual recovery endpoints (`/jobs/{jobId}/retry`, `/jobs/{jobId}/proceed-anyway`).
- [x] Dashboard endpoints (`/dashboard`, `/dashboard/metrics`).
- [x] CI security checks (`test_security`, `bandit`, `pip-audit`) and artifacts.

## Week 1 - Core healing hardening

- [x] Implement enriched remediation classification in `remediation_agent`:
  - `fixable_quality`, `fixable_completeness`, `fixable_consistency`, `unfixable_policy`, `unfixable_complexity`.
- [x] Add heal strategy selection in remediation output:
  - `enhance_prompt_quality`, `decompose_and_rebuild`, `add_consistency_constraints`.
- [x] Add attempt-state object into execution trace:
  - attempt number, strategy, before/after critic scores, outcome.
- [x] Add explicit override/audit fields to trace:
  - `manualOverride`, `approvedBy`, `approvedAt`, `reason`.
- [x] Add one Jira escalation template for unfixable failures.

## Week 2 - Regeneration strategies

- [x] Implement `RegeneratorAgent` module:
  - build fix plan from critic/validator findings,
  - apply strategy-specific prompt augmentation.
- [x] Implement strategy 1: `enhance_prompt_quality`.
- [x] Implement strategy 2: `decompose_and_rebuild` (for completeness failures).
- [x] Implement strategy 3: `add_consistency_constraints`.
- [x] Enforce max attempts (`<= 3`) and deterministic escalate behavior.

## Week 3 - Visibility and platform polish

- [x] Add healing session persistence model:
  - `session_id`, `job_id`, `attempt`, `strategy`, `status`, `score_before`, `score_after`, timestamps.
- [x] Add API endpoint for healing sessions:
  - `GET /healing/sessions`
  - optional filters: `issueKey`, `status`, `strategy`, `limit`.
- [x] Add GitHub Pages metrics output (`docs/metrics/*.json`) from CI runs.
- [x] Add README badges for healing KPIs (success rate, escalation rate, average attempts).
- [x] Add one dashboard section for healing trends (last 20 sessions).

## Optional "wow factor"

- [ ] Streamlit or Vercel dashboard for interactive live demo.
- [ ] Websocket stream for in-progress execution telemetry.
- [ ] Knowledge base table for successful healing patterns.

## Definition of done for self-healing v2

- [ ] At least one failed case auto-heals and passes without manual retry.
- [x] Retry loop stops at max attempts and escalates deterministically.
- [x] Every attempt is traceable via API and linked Jira comments.
- [x] Manual override is auditable and policy-bounded.
- [x] CI publishes healing metrics artifacts each run.
