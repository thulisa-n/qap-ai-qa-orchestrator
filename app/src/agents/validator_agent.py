from app.src.schemas import (
    ArtifactCriticDecision,
    AutomationDecision,
    GeneratePlaywrightResponse,
    GenerateTestsResponse,
    ValidatorDecision,
)


def validate_agent_outputs(
    *,
    tests: GenerateTestsResponse,
    playwright: GeneratePlaywrightResponse,
    critic: ArtifactCriticDecision,
    automation: AutomationDecision,
) -> ValidatorDecision:
    findings: list[str] = []
    fixes: list[str] = []

    if len(tests.scenarios) < 5:
        findings.append("Generated scenarios are below minimum expected count (5).")
        fixes.append("Regenerate scenarios with broader AC decomposition.")

    if not playwright.files:
        findings.append("No Playwright files were generated.")
        fixes.append("Regenerate Playwright artifacts with explicit stable paths/selectors.")

    if critic.verdict != "pass" or not critic.isAcceptable:
        findings.append("Critic gate did not pass artifacts as acceptable.")
        fixes.append("Address critic findings before creating automation tasks.")

    if automation.recommendedCoverage == "manual_only" and automation.shouldCreateAutomationTask:
        findings.append("Automation decision is inconsistent: manual_only with task creation true.")
        fixes.append("Set shouldCreateAutomationTask to false for manual_only.")

    if findings:
        verdict = "needs_fix" if len(findings) <= 2 else "fail"
        return ValidatorDecision(
            isValid=False,
            verdict=verdict,
            findings=findings,
            suggestedFixes=fixes,
        )

    return ValidatorDecision(
        isValid=True,
        verdict="pass",
        findings=[],
        suggestedFixes=[],
    )
