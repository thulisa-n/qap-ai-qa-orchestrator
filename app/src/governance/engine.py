import json
from pathlib import Path
from typing import Any

from app.src.schemas import (
    ArtifactCriticDecision,
    AutomationDecision,
    GenerateTestsResponse,
)


RISK_ORDER = {"low": 0, "medium": 1, "high": 2}
SECURITY_HINTS = {
    "auth",
    "authentication",
    "authorization",
    "access",
    "forbidden",
    "session",
    "token",
    "secret",
    "injection",
    "xss",
    "csrf",
    "security",
}


def _load_policy_file(filename: str) -> dict[str, Any]:
    policy_path = Path(__file__).resolve().parent / "policies" / filename
    return json.loads(policy_path.read_text(encoding="utf-8"))


def _max_risk(istqb_risk: str, org_risk: str) -> str:
    # Use stricter (lower tolerance) by choosing the lower rank.
    return istqb_risk if RISK_ORDER[istqb_risk] <= RISK_ORDER[org_risk] else org_risk


def _has_security_scenario(tests: GenerateTestsResponse) -> bool:
    for scenario in tests.scenarios:
        text = " ".join(
            [scenario.title, *(step.action for step in scenario.steps)]
        ).lower()
        if any(hint in text for hint in SECURITY_HINTS):
            return True
    return False


def evaluate_governance_gate(
    *,
    coverage_report: dict[str, Any],
    tests: GenerateTestsResponse,
    automation_decision: AutomationDecision,
    critic_decision: ArtifactCriticDecision | None = None,
) -> dict[str, Any]:
    istqb = _load_policy_file("istqb_foundation_v4.json")
    org = _load_policy_file("org_policy.json")
    enforce_istqb = istqb.get("enforcement", {})
    overrides = org.get("overrides", {})

    min_coverage = max(
        float(enforce_istqb.get("minCoverageRatioForAutomation", 0.7)),
        float(overrides.get("minCoverageRatioForAutomation", 0.7)),
    )
    require_security = bool(
        overrides.get(
            "requireSecurityScenarioForAutomation",
            enforce_istqb.get("requireSecurityScenarioForAutomation", True),
        )
    )
    max_allowed_risk = _max_risk(
        str(enforce_istqb.get("maxAllowedAutomationRisk", "medium")),
        str(overrides.get("maxAllowedAutomationRisk", "medium")),
    )
    require_human_at = str(overrides.get("requireHumanApprovalAtRisk", "high"))
    require_critic = bool(overrides.get("requireCriticAcceptableForAutomation", True))
    min_critic_score = float(overrides.get("minCriticOverallScoreForAutomation", 0.7))

    coverage_ratio = float(coverage_report.get("score", 0.0))
    has_security = _has_security_scenario(tests)

    violations: list[str] = []
    if coverage_ratio < min_coverage:
        violations.append(
            f"Coverage ratio {coverage_ratio:.2f} is below required minimum {min_coverage:.2f}."
        )
    if require_security and not has_security:
        violations.append("At least one security-oriented scenario is required for automation.")
    if RISK_ORDER.get(automation_decision.automationRisk, 2) > RISK_ORDER[max_allowed_risk]:
        violations.append(
            f"Automation risk `{automation_decision.automationRisk}` exceeds allowed threshold `{max_allowed_risk}`."
        )
    if critic_decision and critic_decision.overallScore < min_critic_score:
        violations.append(
            f"Critic overall score {critic_decision.overallScore:.2f} is below required minimum {min_critic_score:.2f}."
        )
    if require_critic and (critic_decision is None or not critic_decision.isAcceptable):
        violations.append(
            "Critic gate requires acceptable scenario/playwright quality before automation task creation."
        )

    requires_human_approval = (
        RISK_ORDER.get(automation_decision.automationRisk, 2)
        >= RISK_ORDER.get(require_human_at, 2)
    )
    allowed_for_automation = len(violations) == 0

    return {
        "framework": istqb.get("framework", "ISTQB Foundation 4.0"),
        "policyVersion": {
            "istqb": istqb.get("version", "v1"),
            "organization": org.get("version", "v1"),
        },
        "allowedForAutomation": allowed_for_automation,
        "requiresHumanApproval": requires_human_approval,
        "coverageRatio": round(coverage_ratio, 2),
        "automationRisk": automation_decision.automationRisk,
        "criticOverallScore": round(critic_decision.overallScore, 2) if critic_decision else None,
        "criticAcceptable": critic_decision.isAcceptable if critic_decision else False,
        "violations": violations,
        "summary": (
            "Governance gate passed."
            if allowed_for_automation
            else "Governance gate blocked automation task creation."
        ),
    }
