import json
from pathlib import Path

from app.src.services.llm_service import build_playwright_prompt, build_tests_prompt
from evals.assertions import env_credentials_only, scenario_schema
from evals.render_prompt import render_prompt


def test_eval_renderer_matches_live_prompts():
    acceptance_criteria = "Valid credentials allow login and redirect to the dashboard."
    context = "Use the existing login form."
    scenario = render_prompt(
        {
            "vars": {
                "prompt_kind": "scenarios",
                "acceptance_criteria": acceptance_criteria,
                "context": context,
            }
        }
    )
    assert scenario == build_tests_prompt(acceptance_criteria, context)
    assert "AC_SENTINEL_VALUE" not in scenario
    assert acceptance_criteria in scenario

    playwright = render_prompt(
        {
            "vars": {
                "prompt_kind": "playwright",
                "acceptance_criteria": acceptance_criteria,
                "context": "",
                "base_url": "https://example.test",
            }
        }
    )
    assert playwright == build_playwright_prompt(acceptance_criteria, None, "https://example.test")
    assert "https://example.test" in playwright
    assert "TEST_USER" in playwright
    assert "Never invent selectors" in playwright


def test_scenario_schema_assertion():
    payload = {
        "tags": ["security"],
        "scenarios": [{"id": f"S{index}", "title": "login security check"} for index in range(1, 6)],
    }
    assert scenario_schema(json.dumps(payload))["pass"] is True
    assert scenario_schema(json.dumps({"scenarios": [{"id": "S1"}]}))["pass"] is False
    assert scenario_schema("```json\n{}")["pass"] is False


def test_credential_assertion_rejects_hard_coded_password():
    assert env_credentials_only("const user = process.env.TEST_USER;")["pass"] is True
    leaked = "password = 'SecretAdmin123'; process.env.TEST_PASS"
    assert env_credentials_only(leaked)["pass"] is False


def test_promptfoo_config_uses_only_gemini():
    config_path = Path(__file__).resolve().parents[2] / "evals" / "promptfooconfig.yaml"
    text = config_path.read_text(encoding="utf-8")
    assert "google:gemini-3.8-flash" in text
    assert "anthropic" not in text.lower()
    assert "openai" not in text.lower()
    assert "AIza" not in text
    assert "file://render_prompt.py:render_prompt" in text
