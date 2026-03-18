from app.src.governance.engine import evaluate_governance_gate
from app.src.schemas import ArtifactCriticDecision, AutomationDecision, GenerateTestsResponse


def test_governance_allows_automation_when_policy_is_satisfied():
    tests = GenerateTestsResponse.model_validate(
        {
            "tags": ["security", "access"],
            "scenarios": [
                {
                    "id": "S1",
                    "title": "Role access validation",
                    "priority": "P1",
                    "type": "e2e",
                    "steps": [{"action": "Verify admin access and user forbidden behavior", "data": {}}],
                },
                {
                    "id": "S2",
                    "title": "Session security check",
                    "priority": "P1",
                    "type": "api",
                    "steps": [{"action": "Validate expired session token is rejected", "data": {}}],
                },
            ],
            "notes": "ok",
        }
    )
    decision = AutomationDecision.model_validate(
        {
            "shouldCreateAutomationTask": True,
            "confidence": 0.91,
            "reason": "Deterministic and high-value security/access checks.",
            "recommendedCoverage": "full_automation",
            "automationRisk": "medium",
            "riskReasons": ["Cross-browser adds maintenance overhead."],
        }
    )
    critic = ArtifactCriticDecision.model_validate(
        {
            "overallScore": 0.9,
            "scenarioQualityScore": 0.92,
            "playwrightQualityScore": 0.88,
            "isAcceptable": True,
            "findings": [],
            "recommendations": [],
            "verdict": "pass",
        }
    )
    report = evaluate_governance_gate(
        coverage_report={"score": 0.9},
        tests=tests,
        automation_decision=decision,
        critic_decision=critic,
    )
    assert report["allowedForAutomation"] is True
    assert report["violations"] == []


def test_governance_blocks_automation_when_coverage_is_low_and_security_missing():
    tests = GenerateTestsResponse.model_validate(
        {
            "tags": ["smoke"],
            "scenarios": [
                {
                    "id": "S1",
                    "title": "Basic happy path",
                    "priority": "P2",
                    "type": "e2e",
                    "steps": [{"action": "Open dashboard and verify welcome text", "data": {}}],
                }
            ],
            "notes": "ok",
        }
    )
    decision = AutomationDecision.model_validate(
        {
            "shouldCreateAutomationTask": True,
            "confidence": 0.83,
            "reason": "Could be automated later.",
            "recommendedCoverage": "partial_automation",
            "automationRisk": "high",
            "riskReasons": ["Unstable UI behavior."],
        }
    )
    critic = ArtifactCriticDecision.model_validate(
        {
            "overallScore": 0.45,
            "scenarioQualityScore": 0.5,
            "playwrightQualityScore": 0.4,
            "isAcceptable": False,
            "findings": ["Weak assertions."],
            "recommendations": ["Improve test determinism."],
            "verdict": "needs_revision",
        }
    )
    report = evaluate_governance_gate(
        coverage_report={"score": 0.4},
        tests=tests,
        automation_decision=decision,
        critic_decision=critic,
    )
    assert report["allowedForAutomation"] is False
    assert len(report["violations"]) >= 2


def test_governance_blocks_when_confidence_is_below_policy_minimum():
    tests = GenerateTestsResponse.model_validate(
        {
            "tags": ["security"],
            "scenarios": [
                {
                    "id": "S1",
                    "title": "Security access validation",
                    "priority": "P1",
                    "type": "api",
                    "steps": [{"action": "Verify forbidden access for non-admin token", "data": {}}],
                }
            ],
            "notes": "ok",
        }
    )
    decision = AutomationDecision.model_validate(
        {
            "shouldCreateAutomationTask": True,
            "confidence": 0.61,
            "reason": "Automation should happen.",
            "recommendedCoverage": "partial_automation",
            "automationRisk": "low",
            "riskReasons": ["API is deterministic."],
        }
    )
    critic = ArtifactCriticDecision.model_validate(
        {
            "overallScore": 0.82,
            "scenarioQualityScore": 0.84,
            "playwrightQualityScore": 0.8,
            "isAcceptable": True,
            "findings": [],
            "recommendations": [],
            "verdict": "pass",
        }
    )
    report = evaluate_governance_gate(
        coverage_report={"score": 0.92},
        tests=tests,
        automation_decision=decision,
        critic_decision=critic,
    )
    assert report["allowedForAutomation"] is False
    assert any("confidence" in violation.lower() for violation in report["violations"])
