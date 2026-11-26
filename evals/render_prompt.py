"""Render the prompt text QAP sends to Gemini.

Promptfoo calls ``render_prompt`` with ``{"vars": ..., "provider": ..., "config": ...}``.
Clean inputs match ``build_tests_prompt`` / ``build_playwright_prompt``. Injection-marker
text is still rendered here so the eval can grade the prompt itself. The keyword
pre-filter stays covered by pytest and still rejects those inputs on the API.
"""

from app.src.services.llm_service import render_playwright_prompt, render_scenario_prompt


def render_prompt(context: dict) -> str:
    variables = context.get("vars", context) if isinstance(context, dict) else {}
    kind = str(variables.get("prompt_kind") or "scenarios")
    acceptance_criteria = str(variables.get("acceptance_criteria") or "")
    raw_context = variables.get("context")
    context_text = str(raw_context) if raw_context else None
    if kind == "playwright":
        raw_base_url = variables.get("base_url")
        base_url = str(raw_base_url) if raw_base_url else None
        return render_playwright_prompt(acceptance_criteria, context_text, base_url)
    if kind != "scenarios":
        raise ValueError(f"Unknown prompt_kind: {kind}")
    return render_scenario_prompt(acceptance_criteria, context_text)
