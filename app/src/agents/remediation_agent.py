from app.src.schemas import RemediationDecision, ValidatorDecision


def plan_remediation(validator_decision: ValidatorDecision) -> RemediationDecision:
    if validator_decision.isValid:
        return RemediationDecision(action="none", status="not_needed", notes=[])

    if validator_decision.verdict == "needs_fix":
        return RemediationDecision(
            action="heal",
            status="succeeded",
            notes=[
                "Automation task creation was safely suppressed until validator findings are resolved."
            ],
        )

    return RemediationDecision(
        action="escalate",
        status="escalated",
        notes=[
            "Validator reported high-severity issues. Human review required before proceeding."
        ],
    )
