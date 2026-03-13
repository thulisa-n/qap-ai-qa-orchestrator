from collections.abc import Callable

from app.src.schemas import ArtifactCriticDecision
from app.src.services.llm_service import build_artifact_critic_prompt, call_llm


def run_artifact_critic(
    *,
    acceptance_criteria: str,
    context: str | None,
    tests_json: str,
    playwright_json: str,
    llm_caller: Callable[[str], str] | None = None,
) -> ArtifactCriticDecision:
    prompt = build_artifact_critic_prompt(
        acceptance_criteria,
        context,
        tests_json,
        playwright_json,
    )
    caller = llm_caller or call_llm
    critic_text = caller(prompt)
    return ArtifactCriticDecision.model_validate_json(critic_text)
