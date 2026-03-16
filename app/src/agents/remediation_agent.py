from app.src.schemas import ArtifactCriticDecision, RemediationDecision, ValidatorDecision


COMPLETENESS_TOKENS = {
    "missing",
    "incomplete",
    "todo",
    "not generated",
    "no playwright",
    "not implemented",
    "not covered",
}
CONSISTENCY_TOKENS = {
    "inconsistent",
    "inconsisten",
    "contradiction",
    "mismatch",
    "conflict",
    "manual_only",
}
POLICY_TOKENS = {"policy", "governance", "compliance", "forbidden", "prohibited"}
COMPLEXITY_TOKENS = {
    "complex",
    "ambiguous",
    "unclear",
    "undefined",
    "external dependency",
}


def _contains_any(text: str, tokens: set[str]) -> bool:
    return any(token in text for token in tokens)


def _classify_failure(
    *, validator_decision: ValidatorDecision, critic_decision: ArtifactCriticDecision
) -> tuple[str, str]:
    combined = " ".join(
        [
            *validator_decision.findings,
            *validator_decision.suggestedFixes,
            *critic_decision.findings,
            *critic_decision.recommendations,
        ]
    ).lower()

    if _contains_any(combined, POLICY_TOKENS):
        return "unfixable_policy", "none"

    if validator_decision.verdict == "fail" and _contains_any(combined, COMPLEXITY_TOKENS):
        return "unfixable_complexity", "none"

    if _contains_any(combined, COMPLETENESS_TOKENS):
        return "fixable_completeness", "decompose_and_rebuild"

    if _contains_any(combined, CONSISTENCY_TOKENS):
        return "fixable_consistency", "add_consistency_constraints"

    if validator_decision.verdict == "needs_fix" or critic_decision.overallScore < 0.7:
        return "fixable_quality", "enhance_prompt_quality"

    return "unfixable_complexity", "none"


def plan_remediation(
    validator_decision: ValidatorDecision,
    critic_decision: ArtifactCriticDecision,
    *,
    attempt_number: int = 1,
    max_attempts: int = 2,
) -> RemediationDecision:
    if validator_decision.isValid:
        return RemediationDecision(action="none", status="not_needed", notes=[])

    failure_category, heal_strategy = _classify_failure(
        validator_decision=validator_decision,
        critic_decision=critic_decision,
    )
    is_fixable = failure_category.startswith("fixable_") and heal_strategy != "none"

    if is_fixable and attempt_number < max_attempts:
        return RemediationDecision(
            action="heal",
            status="succeeded",
            failureCategory=failure_category,
            healStrategy=heal_strategy,
            notes=[
                f"Failure classified as {failure_category}.",
                f"Selected heal strategy: {heal_strategy}.",
                "Automation task creation was safely suppressed until validator findings are resolved.",
            ],
        )

    escalation_reason = (
        "Maximum healing attempts reached."
        if is_fixable and attempt_number >= max_attempts
        else f"Failure classified as {failure_category}; human review required."
    )
    return RemediationDecision(
        action="escalate",
        status="escalated",
        failureCategory=failure_category,
        healStrategy="none",
        notes=[
            escalation_reason,
            "Validator reported high-severity issues. Human review required before proceeding.",
        ],
    )
