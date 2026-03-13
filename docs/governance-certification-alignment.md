# Governance and Certification Alignment

This guide maps QAP governance controls to certification tracks that strengthen
your credibility for AI QA and compliance-focused automation roles.

## Recommended certification path

## 1) Foundation (must-have)

- ISTQB Certified Tester Foundation Level (CTFL 4.0)
  - Why: gives shared QA vocabulary and risk-based testing baseline.
  - Project alignment: maps directly to your source-of-truth policy approach.

## 2) Automation specialization (high-value)

- ISTQB Test Automation Engineer (CTAL-TAE or equivalent module name via your ISTQB board)
  - Why: focuses on automation architecture, maintainability, and reliability.
  - Project alignment: supports your critic/validator quality gates and flake control.

## 3) AI assurance specialization (role-aligned)

- AI testing/governance credential recognized by your regional board or provider
  - Examples to evaluate: ISTQB AI-focused offerings (where available), ISO/IEC 42001 training, or equivalent AI governance programs.
  - Why: demonstrates model-risk, explainability, and control awareness.
  - Project alignment: supports your remediation + trace transparency + human override model.

## 4) Security/compliance supporting credential (recommended)

- ISO 27001 foundation/implementer or equivalent security governance training
  - Why: strengthens policy, control, and audit narratives.
  - Project alignment: supports pipeline SAST/SCA, auth controls, and evidence retention.

## Strict governance rules to enforce in QAP

These are practical "hard rules" you can encode in org policy and CI gates.

- **Rule G1 - Automation gate integrity**
  - Never create automation task when validator fails.
  - Never create automation task when governance denies.

- **Rule G2 - Critic threshold enforcement**
  - Block automation if critic overall score is below threshold.
  - Block automation when critic acceptability is false.

- **Rule G3 - Human override auditing**
  - `proceed-anyway` requires justification text.
  - Persist approver identity and timestamp.
  - Post Jira audit comment with override reason.

- **Rule G4 - Retry guardrails**
  - Max heal attempts: 3.
  - Persist attempt history (strategy + score delta + outcome).
  - Escalate automatically when max attempts reached.

- **Rule G5 - Trace transparency**
  - Each run must expose `executionTrace`, `validatorDecision`, `remediationDecision`, `governanceDecision`.
  - Keep traces queryable by `jobId` and listable by status.

- **Rule G6 - Security baseline**
  - Block `main` on critical SAST/SCA findings.
  - Run API auth regression tests in CI.
  - Keep secrets out of source control (`.env` ignored and rotated when leaked).

## Suggested interview narrative

"QAP is policy-first: generation is useful, but release decisions are bounded by
critic, validator, and governance gates. Every exception is audited, every retry
is traceable, and human override remains explicit."
