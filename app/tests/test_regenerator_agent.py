from app.src.agents.regenerator_agent import build_fix_plan, build_regeneration_context
from app.src.schemas import ArtifactCriticDecision, RemediationDecision, ValidatorDecision


def _validator_needs_fix() -> ValidatorDecision:
    return ValidatorDecision(
        isValid=False,
        verdict="needs_fix",
        findings=["Generated scenarios are below minimum expected count (5)."],
        suggestedFixes=["Regenerate scenarios with broader AC decomposition."],
    )


def _critic_needs_revision() -> ArtifactCriticDecision:
    return ArtifactCriticDecision(
        overallScore=0.41,
        scenarioQualityScore=0.5,
        playwrightQualityScore=0.3,
        isAcceptable=False,
        findings=["Critical assertions missing for security behavior."],
        recommendations=["Regenerate tests with stronger deterministic assertions."],
        verdict="needs_revision",
    )


def test_build_fix_plan_uses_strategy_specific_constraints():
    validator = _validator_needs_fix()
    critic = _critic_needs_revision()
    remediation = RemediationDecision(
        action="heal",
        status="succeeded",
        failureCategory="fixable_completeness",
        healStrategy="decompose_and_rebuild",
        notes=[],
    )

    plan = build_fix_plan(
        validator_decision=validator,
        critic_decision=critic,
        remediation_decision=remediation,
    )
    assert plan.strategy == "decompose_and_rebuild"
    assert any("scenario-level" in item for item in plan.prompt_enhancements)
    assert any("must map" in item.lower() for item in plan.constraints)


def test_build_regeneration_context_embeds_fix_plan_metadata():
    validator = _validator_needs_fix()
    critic = _critic_needs_revision()
    remediation = RemediationDecision(
        action="heal",
        status="succeeded",
        failureCategory="fixable_consistency",
        healStrategy="add_consistency_constraints",
        notes=[],
    )

    context, plan = build_regeneration_context(
        base_context="Triggered by Jira transition.",
        validator_decision=validator,
        critic_decision=critic,
        remediation_decision=remediation,
    )

    assert plan.strategy == "add_consistency_constraints"
    assert "Strategy: add_consistency_constraints" in context
    assert "Mandatory constraints:" in context
    assert "Triggered by Jira transition." in context
