from typing import Any


def build_decision_explanation(
    *,
    critic_decision: dict[str, Any] | None,
    validator_decision: dict[str, Any] | None,
    governance_decision: dict[str, Any] | None,
    automation_decision: dict[str, Any] | None,
) -> dict[str, Any]:
    reasons: list[str] = []
    blocked = False

    if critic_decision:
        overall_score = critic_decision.get("overallScore")
        verdict = critic_decision.get("verdict")
        if verdict == "needs_revision":
            blocked = True
            reasons.append("Critic flagged artifacts as needing revision.")
        if overall_score is not None:
            reasons.append(f"Critic overall score: {overall_score}.")

    if validator_decision:
        is_valid = bool(validator_decision.get("isValid"))
        if not is_valid:
            blocked = True
            reasons.append("Validator blocked automation due to deterministic rule failures.")
            findings = validator_decision.get("findings") or []
            if findings:
                reasons.append(f"Validator findings: {findings[0]}")

    if governance_decision:
        allowed = governance_decision.get("allowedForAutomation")
        if allowed is False:
            blocked = True
            reasons.append("Governance policy denied automation creation.")
            violations = governance_decision.get("violations") or []
            if violations:
                reasons.append(f"Policy violation: {violations[0]}")

    if automation_decision:
        should_create = automation_decision.get("shouldCreateAutomationTask")
        if should_create is False:
            reasons.append("Automation decision recommended manual-only or partial execution.")

    summary = (
        "Automation creation denied because quality or policy gates did not pass."
        if blocked
        else "Automation path allowed because critic, validator, and governance gates passed."
    )
    return {"summary": summary, "reasons": reasons, "blocked": blocked}
