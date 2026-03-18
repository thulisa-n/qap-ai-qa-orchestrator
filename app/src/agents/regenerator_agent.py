from dataclasses import dataclass

from app.src.schemas import ArtifactCriticDecision, RemediationDecision, ValidatorDecision


@dataclass
class FixPlan:
    strategy: str
    diagnosis: str
    prompt_enhancements: list[str]
    constraints: list[str]


def build_fix_plan(
    *,
    validator_decision: ValidatorDecision,
    critic_decision: ArtifactCriticDecision,
    remediation_decision: RemediationDecision,
) -> FixPlan:
    strategy = remediation_decision.healStrategy or "enhance_prompt_quality"
    findings = validator_decision.findings + critic_decision.findings
    diagnosis = findings[0] if findings else "Quality gate mismatch detected."

    if strategy == "decompose_and_rebuild":
        return FixPlan(
            strategy=strategy,
            diagnosis=diagnosis,
            prompt_enhancements=[
                "Break requirements into scenario-level units before generating Playwright.",
                "Implement each scenario explicitly; avoid partial coverage.",
            ],
            constraints=[
                "Every generated scenario must map to at least one executable Playwright assertion.",
                "Do not leave TODO placeholders for required acceptance checks.",
            ],
        )

    if strategy == "add_consistency_constraints":
        return FixPlan(
            strategy=strategy,
            diagnosis=diagnosis,
            prompt_enhancements=[
                "Enforce strict alignment across AC, scenarios, and Playwright assertions.",
                "Validate naming and expected outcomes for internal consistency before final output.",
            ],
            constraints=[
                "No contradiction between automation decision and recommended coverage.",
                "Risk reasons must align with the chosen coverage recommendation.",
            ],
        )

    # Default strategy: enhance_prompt_quality
    return FixPlan(
        strategy="enhance_prompt_quality",
        diagnosis=diagnosis,
        prompt_enhancements=[
            "Increase assertion specificity and deterministic checks.",
            "Prefer robust selectors and explicit expected outcomes for each scenario.",
        ],
        constraints=[
            "Generated artifacts must be reviewer-ready and implementation-complete.",
            "Retain secure-by-default behavior and avoid speculative assumptions.",
        ],
    )


def build_regeneration_context(
    *,
    base_context: str | None,
    validator_decision: ValidatorDecision,
    critic_decision: ArtifactCriticDecision,
    remediation_decision: RemediationDecision,
) -> tuple[str, FixPlan]:
    plan = build_fix_plan(
        validator_decision=validator_decision,
        critic_decision=critic_decision,
        remediation_decision=remediation_decision,
    )

    existing_context = base_context or ""
    findings = "; ".join(validator_decision.findings) or "None"
    suggested = "; ".join(validator_decision.suggestedFixes) or "None"
    enhancements = "\n".join(f"- {item}" for item in plan.prompt_enhancements)
    constraints = "\n".join(f"- {item}" for item in plan.constraints)

    regen_context = (
        f"{existing_context}\n\n"
        "[HEAL_RETRY]\n"
        f"Strategy: {plan.strategy}\n"
        f"Diagnosis: {plan.diagnosis}\n"
        f"Validator findings: {findings}\n"
        f"Suggested fixes: {suggested}\n"
        "Prompt enhancements:\n"
        f"{enhancements}\n"
        "Mandatory constraints:\n"
        f"{constraints}\n"
    ).strip()

    return regen_context, plan
