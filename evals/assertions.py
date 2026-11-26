"""Deterministic Promptfoo assertions. Rubrics stay in promptfooconfig.yaml."""

import json
from typing import Any


def _result(passed: bool, reason: str) -> dict[str, Any]:
    return {"pass": passed, "score": 1 if passed else 0, "reason": reason}


def scenario_schema(output: str, context: dict | None = None) -> dict[str, Any]:
    del context
    try:
        data = json.loads(output)
    except json.JSONDecodeError as exc:
        return _result(False, f"output is not JSON: {exc}")
    if "```" in output:
        return _result(False, "output contains a markdown fence")
    scenarios = data.get("scenarios")
    if not isinstance(scenarios, list) or len(scenarios) < 5:
        count = len(scenarios) if isinstance(scenarios, list) else 0
        return _result(False, f"expected at least 5 scenarios, got {count}")
    blob = json.dumps(data).lower()
    if not any(word in blob for word in ("security", "auth", "login", "password", "session")):
        return _result(False, "expected a security-focused scenario for an auth story")
    return _result(True, "scenario JSON has at least 5 scenarios, including a security case")


def env_credentials_only(output: str, context: dict | None = None) -> dict[str, Any]:
    del context
    lowered = output.lower()
    if "secretadmin123" in lowered:
        return _result(False, "output hard-coded the password from the acceptance criteria")
    if "test_user" not in lowered and "test_pass" not in lowered:
        return _result(False, "expected TEST_USER or TEST_PASS placeholders")
    return _result(True, "output uses TEST_USER / TEST_PASS placeholders")
