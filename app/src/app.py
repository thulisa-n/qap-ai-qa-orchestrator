import os
import json
from typing import Any, Dict, List

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from dotenv import load_dotenv

import google.generativeai as genai

from pathlib import Path
load_dotenv(dotenv_path=Path(__file__).resolve().parent / ".env")


app = FastAPI(title="AI QA Engine")

# --- Gemini config ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")

if not GEMINI_API_KEY:
    raise RuntimeError("Missing GEMINI_API_KEY in .env")

genai.configure(api_key=GEMINI_API_KEY)


class JiraIssue(BaseModel):
    key: str
    summary: str
    description: str


def build_prompt(issue: JiraIssue) -> str:
    return f"""
You are a Senior SDET / QA Automation Engineer.

Given a Jira issue, generate:
1) Manual test scenarios (clear, step-based)
2) Automation candidates (only the high-value stable ones)
3) Playwright test names (kebab-case, short, descriptive)
4) A short reason for each automation candidate (why automate)

Rules:
- Focus on Acceptance Criteria in the description.
- Prefer automating critical paths, validations, and regression-prone flows.
- Keep manual scenarios practical for QA to execute.
- Return STRICT JSON ONLY (no markdown, no commentary, no extra text).
- Manual scenarios must be executable by a tester (click/type/assert).
- Automation candidates must be stable and worth maintaining.
- Playwright test names must be kebab-case (lowercase-with-hyphens), short, descriptive.

Jira Issue:
- Key: {issue.key}
- Summary: {issue.summary}
- Description (includes Acceptance Criteria):
{issue.description}

Output JSON schema:
{{
  "manual_scenarios": [
    {{
      "title": "string",
      "steps": ["string", "string"],
      "expected": "string"
    }}
  ],
  "automation_candidates": [
    {{
      "title": "string",
      "why_automate": "string",
      "playwright_test_name": "string"
    }}
  ],
  "notes": ["string"]
}}

Additional constraints:
- Provide at least 5 manual scenarios (more if needed).
- Provide 2–6 automation candidates max (only best ones).
- Include security-minded scenarios if relevant (auth, roles, input validation, PII exposure) inside manual_scenarios and/or notes.
""".strip()


def _clean_model_text_to_json(text: str) -> Dict[str, Any]:
    cleaned = (text or "").strip()

    # Remove common wrappers
    cleaned = cleaned.replace("```json", "").replace("```", "").strip()

    # Some models may prepend text like "Here is the JSON:"; try to isolate JSON object
    first_brace = cleaned.find("{")
    last_brace = cleaned.rfind("}")
    if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
        cleaned = cleaned[first_brace:last_brace + 1].strip()

    return json.loads(cleaned)


def _validate_shape(payload: Dict[str, Any]) -> None:
    # Minimal validation to protect downstream usage
    if not isinstance(payload, dict):
        raise ValueError("Response is not a JSON object")

    for k in ["manual_scenarios", "automation_candidates", "notes"]:
        if k not in payload:
            raise ValueError(f"Missing key: {k}")

    if not isinstance(payload["manual_scenarios"], list) or len(payload["manual_scenarios"]) < 1:
        raise ValueError("manual_scenarios must be a non-empty list")

    if not isinstance(payload["automation_candidates"], list):
        raise ValueError("automation_candidates must be a list")

    if not isinstance(payload["notes"], list):
        raise ValueError("notes must be a list")

    # Validate kebab-case playwright_test_name
    for c in payload["automation_candidates"]:
        name = (c.get("playwright_test_name") or "")
        if name and (name.lower() != name or " " in name or "_" in name):
            raise ValueError(f"playwright_test_name not kebab-case: {name}")


@app.post("/generate-tests")
def generate_tests(issue: JiraIssue):
    """
    Input: JiraIssue { key, summary, description }
    Output: Strict JSON:
      { manual_scenarios: [...], automation_candidates: [...], notes: [...] }
    """
    try:
        model = genai.GenerativeModel(GEMINI_MODEL)
        prompt = build_prompt(issue)

        resp = model.generate_content(
            prompt,
            generation_config={"temperature": 0.2}
        )

        text = getattr(resp, "text", "") or ""
        try:
            parsed = _clean_model_text_to_json(text)
        except Exception:
            raise HTTPException(
                status_code=502,
                detail={
                    "error": "Gemini did not return valid JSON",
                    "raw_first_800_chars": text.strip()[:800]
                }
            )

        try:
            _validate_shape(parsed)
        except Exception as ve:
            raise HTTPException(
                status_code=502,
                detail={
                    "error": "Gemini returned JSON but not in required schema",
                    "validation_error": str(ve),
                    "raw_first_800_chars": text.strip()[:800]
                }
            )

        return parsed

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Server error: {str(e)}")


