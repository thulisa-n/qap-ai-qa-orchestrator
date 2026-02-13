import os
import json
import warnings
from pathlib import Path
from typing import Dict, Any, List, Optional
import requests
import traceback
from requests.auth import HTTPBasicAuth

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from dotenv import load_dotenv

warnings.filterwarnings(
    "ignore",
    message=".*google\\.generativeai.*has ended.*",
    category=FutureWarning,
)
import google.generativeai as genai




# Correct location: app/.env
BASE_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = BASE_DIR / ".env"
load_dotenv(ENV_PATH)
api_key = os.getenv("GEMINI_API_KEY")



GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise RuntimeError("Missing GEMINI_API_KEY in environment (.env)")

genai.configure(api_key=GEMINI_API_KEY)

# Prefer newer model if you set it in .env, otherwise default:
MODEL_NAME = os.getenv("GEMINI_MODEL", "models/gemini-2.5-flash")

app = FastAPI(title="AI QA Engine")

class GenerateTestsRequest(BaseModel):
    acceptanceCriteria: str = Field(validation_alias="acceptance_criteria")
    context: str | None = None

class FileItem(BaseModel):
    path: str
    content: str



# -----------------------------
# Request Models
# -----------------------------
class GenerateTestsRequest(BaseModel):
    acceptanceCriteria: str
    context: str | None = None  # optional (e.g., feature area, notes)


class GeneratePlaywrightRequest(BaseModel):
    acceptanceCriteria: str
    context: str | None = None
    baseUrl: str | None = None  # optional override, otherwise env BASE_URL

class GenerateBothRequest(BaseModel):
    acceptanceCriteria: str
    context: str | None = None
    baseUrl: str | None = None

class JiraAutomationTaskRequest(BaseModel):
    parentIssueKey: str | None = None  # optional, only needed if you want Sub-task
    issueType: str = "Task"            # "Task" or "Sub-task"
    acceptanceCriteria: str
    context: str | None = None
    baseUrl: str | None = None

class FullQAFlowRequest(BaseModel):
    issueKey: str
    acceptanceCriteria: str
    context: str | None = None
    baseUrl: str | None = None

    # toggles
    commentOnJira: bool = True
    writePlaywrightFiles: bool = True
    createAutomationTask: bool = True

    # task config
    automationIssueType: str = "Task"
    automationSummaryPrefix: str = "Automation: Implement generated Playwright tests"


class FullQAFlowResponse(BaseModel):
    scenarios: Dict[str, Any]
    playwright: Dict[str, Any]
    jiraComment: Dict[str, Any] | None = None
    filesWritten: Dict[str, Any] | None = None
    automationTask: Dict[str, Any] | None = None


# -----------------------------
# Response Models (Best practice)
# -----------------------------
class Step(BaseModel):
    action: str
    data: Dict[str, Any] = {}

class Scenario(BaseModel):
    id: str
    title: str
    priority: str  # P1|P2|P3
    type: str      # e2e|api|component
    steps: List[Step]

class GenerateTestsResponse(BaseModel):
    tags: List[str]
    scenarios: List[Scenario]
    notes: str

class FileItem(BaseModel):
    path: str
    content: str

class GeneratePlaywrightResponse(BaseModel):
    tags: List[str]
    files: List[FileItem]
    notes: List[str]

class GenerateBothRequest(BaseModel):
    acceptanceCriteria: str
    context: str | None = None
    baseUrl: str | None = None

class GenerateBothResponse(BaseModel):
    tests: GenerateTestsResponse
    playwright: GeneratePlaywrightResponse



# -----------------------------
# Shared helpers
# -----------------------------
def _clean_json_text(text: str) -> str:
    """
    Defensive cleanup if Gemini wraps JSON in markdown fences.
    """
    cleaned = (text or "").strip()
    cleaned = cleaned.removeprefix("```json").removeprefix("```").strip()
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3].strip()
    return cleaned


def call_llm(prompt: str) -> str:
    model = genai.GenerativeModel(MODEL_NAME)
    resp = model.generate_content(
        prompt,
        generation_config={"temperature": 0.2},
    )
    return (resp.text or "").strip()

def _to_adf(text: str) -> Dict[str, Any]:
    """
    Convert plain text into Atlassian Document Format (ADF) for Jira Cloud (API v3).
    Each line becomes a paragraph.
    """
    lines = (text or "").splitlines() or [""]
    content = []
    for line in lines:
        # Empty line -> empty paragraph
        if line.strip() == "":
            content.append({"type": "paragraph", "content": []})
        else:
            content.append(
                {
                    "type": "paragraph",
                    "content": [{"type": "text", "text": line}],
                }
            )

    return {"type": "doc", "version": 1, "content": content}


def jira_add_comment(issue_key: str, comment: str):
    base = os.getenv("JIRA_BASE_URL")
    email = os.getenv("JIRA_EMAIL")
    token = os.getenv("JIRA_API_TOKEN")

    if not all([base, email, token]):
        raise RuntimeError("Jira env vars missing (JIRA_BASE_URL, JIRA_EMAIL, JIRA_API_TOKEN)")

    url = f"{base}/rest/api/3/issue/{issue_key}/comment"

    adf_body = _to_adf(comment)

    resp = requests.post(
        url,
        json={"body": adf_body},
        auth=HTTPBasicAuth(email, token),
        headers={"Accept": "application/json", "Content-Type": "application/json"},
        timeout=30,
    )

    if resp.status_code >= 300:
        raise RuntimeError(f"Jira error {resp.status_code}: {resp.text}")

    return resp.json()


def format_tests_for_jira(tests: GenerateTestsResponse) -> str:
    lines = ["h2. AI Generated Test Scenarios"]

    for s in tests.scenarios:
        lines.append(f"\nh3. {s.id} — {s.title}")
        lines.append(f"*Priority:* {s.priority}")
        lines.append(f"*Type:* {s.type}")
        lines.append("*Steps:*")

        for i, step in enumerate(s.steps, 1):
            lines.append(f"{i}. {step.action}")

    if tests.notes:
        lines.append("\nh3. Notes")
        lines.append(tests.notes)

    return "\n".join(lines)

def write_playwright_files(files: List[FileItem]) -> List[str]:
    base_dir = Path(__file__).resolve().parent.parent.parent / "playwright-tests"
    created_files = []

    for f in files:
        path = base_dir / f.path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f.content, encoding="utf-8")
        created_files.append(str(path))

    return created_files



def jira_create_issue(summary: str, description: str, issue_type: str = "Task", parent_key: str | None = None):
    base = os.getenv("JIRA_BASE_URL")
    email = os.getenv("JIRA_EMAIL")
    token = os.getenv("JIRA_API_TOKEN")
    project_key = os.getenv("JIRA_PROJECT_KEY")

    if not all([base, email, token, project_key]):
        raise RuntimeError("Jira env vars missing (JIRA_BASE_URL, JIRA_EMAIL, JIRA_API_TOKEN, JIRA_PROJECT_KEY)")

    url = f"{base}/rest/api/3/issue"

    fields = {
        "project": {"key": project_key},
        "summary": summary,
        "issuetype": {"name": issue_type},
        "description": _to_adf(description),
    }

    # If you're using Sub-task, Jira requires a parent issue
    if issue_type.lower() in ["sub-task", "subtask"] and parent_key:
        fields["parent"] = {"key": parent_key}

    resp = requests.post(
        url,
        json={"fields": fields},
        auth=HTTPBasicAuth(email, token),
        headers={"Accept": "application/json", "Content-Type": "application/json"},
        timeout=30,
    )

    if resp.status_code >= 300:
        raise RuntimeError(f"Jira error {resp.status_code}: {resp.text}")

    return resp.json()

def jira_auth():
    base = os.getenv("JIRA_BASE_URL")
    email = os.getenv("JIRA_EMAIL")
    token = os.getenv("JIRA_API_TOKEN")
    if not base or not email or not token:
        raise RuntimeError("Missing Jira env vars. Ensure JIRA_BASE_URL, JIRA_EMAIL, JIRA_API_TOKEN are set in app/.env")
    return base.rstrip("/"), email, token







# -----------------------------
# Prompt builders
# -----------------------------
def build_tests_prompt(acceptance_criteria: str, context: str | None) -> str:
    return f"""
You are a QA Automation Engineer.

Return STRICT JSON only. No markdown. No code fences.

Create test scenarios from acceptance criteria.
Also include security-focused scenarios where relevant.

Acceptance Criteria:
{acceptance_criteria}

Optional Context:
{context or ""}

Return JSON schema:
{{
  "tags": ["smoke","regression","security","api","ui"],
  "scenarios": [
    {{
      "id": "S1",
      "title": "string",
      "priority": "P1|P2|P3",
      "type": "e2e|api|component",
      "steps": [
        {{"action":"string","data":{{}}}}
      ]
    }}
  ],
  "notes": "string"
}}

Rules:
- Provide at least 5 scenarios.
- Provide at least 2 security scenarios if auth/roles/input validation/PII are involved.
""".strip()


def build_playwright_prompt(acceptance_criteria: str, context: str | None, base_url: str | None) -> str:
    base_url_hint = base_url or "use process.env.BASE_URL"
    return f"""
You are a Senior SDET.

Generate Playwright (JavaScript) tests from the Acceptance Criteria.

Return STRICT JSON ONLY (no markdown, no code fences, no extra commentary).
Output JSON schema:
{{
  "tags": ["smoke","regression","security","api","ui"],
  "files": [
    {{
      "path": "tests/<something>.spec.js",
      "content": "string"
    }}
  ],
  "notes": ["string"]
}}

Rules:
- Use @playwright/test.
- Use baseURL = {base_url_hint}.
- Prefer data-testid selectors. If unknown, use placeholders and add a note.
- Keep tests stable/deterministic. Do NOT automate flaky or unclear scenarios.
- Include at least 1 security-minded test when relevant (auth, session, input validation, PII, access control).
- Do NOT invent credentials. Use env vars: TEST_USER and TEST_PASS.
- If API validation is needed, use request fixtures (APIRequestContext) where appropriate.
- Create 1-3 spec files max, grouped logically.
- Keep code clean and ready to run.

Acceptance Criteria:
{acceptance_criteria}

Optional Context:
{context or ""}
""".strip()

@app.get("/health")
def health():
    return {"status": "ok"}

class JiraCommentRequest(BaseModel):
    issueKey: str
    acceptanceCriteria: str
    context: str | None = None


# -----------------------------
# Endpoints
# -----------------------------
@app.post("/generate-tests", response_model=GenerateTestsResponse,
operation_id="generate_tests")
def generate_tests_endpoint(payload: GenerateTestsRequest) -> GenerateTestsResponse:
    try:
        prompt = build_tests_prompt(payload.acceptanceCriteria, payload.context)
        raw = call_llm(prompt)
        text = _clean_json_text(raw)

        try:
            return GenerateTestsResponse.model_validate_json(text)
        except Exception:
            raise HTTPException(
                status_code=502,
                detail=f"Gemini did not return valid JSON matching schema. Raw response (first 800 chars): {text[:800]}",
            )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Server error: {str(e)}")



@app.post("/generate-playwright", response_model=GeneratePlaywrightResponse,
operation_id="generate_playwright")
def generate_playwright_endpoint(payload: GeneratePlaywrightRequest) -> GeneratePlaywrightResponse:
    try:
        prompt = build_playwright_prompt(
            payload.acceptanceCriteria,
            payload.context,
            payload.baseUrl,
        )
        raw = call_llm(prompt)
        text = _clean_json_text(raw)

        try:
            return GeneratePlaywrightResponse.model_validate_json(text)
        except Exception:
            raise HTTPException(
                status_code=502,
                detail=f"Gemini did not return valid JSON matching schema. Raw response (first 800 chars): {text[:800]}",
            )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Server error: {str(e)}")


@app.post("/generate-both",response_model=GenerateBothResponse,
operation_id="generate_both")
def generate_both_endpoint(payload: GenerateBothRequest) -> Dict[str, Any]:
    """
    Generates:
    - structured manual test scenarios JSON
    - Playwright spec file JSON
    In one call.
    """
    try:
        # 1) tests
        tests_prompt = build_tests_prompt(payload.acceptanceCriteria, payload.context)
        tests_raw = call_llm(tests_prompt)
        tests_text = _clean_json_text(tests_raw)
        try:
            tests_json = json.loads(tests_text)
        except json.JSONDecodeError:
            raise HTTPException(
                status_code=502,
                detail=f"Gemini tests output not valid JSON. First 800 chars: {tests_text[:800]}",
            )

        # 2) playwright
        pw_prompt = build_playwright_prompt(payload.acceptanceCriteria, payload.context, payload.baseUrl)
        pw_raw = call_llm(pw_prompt)
        pw_text = _clean_json_text(pw_raw)
        try:
            pw_json = json.loads(pw_text)
        except json.JSONDecodeError:
            raise HTTPException(
                status_code=502,
                detail=f"Gemini Playwright output not valid JSON. First 800 chars: {pw_text[:800]}",
            )

        return {
            "tests": tests_json,
            "playwright": pw_json,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Server error: {str(e)}")

@app.post("/generate-both", response_model=GenerateBothResponse,
operation_id="generate_both")
def generate_both_endpoint(payload: GenerateBothRequest) -> GenerateBothResponse:
    try:
        # Tests JSON
        tests_prompt = build_tests_prompt(payload.acceptanceCriteria, payload.context)
        tests_raw = call_llm(tests_prompt)
        tests_text = _clean_json_text(tests_raw)
        try:
            tests_obj = GenerateTestsResponse.model_validate_json(tests_text)
        except Exception:
            raise HTTPException(
                status_code=502,
                detail=f"Gemini tests output not valid JSON matching schema. First 800 chars: {tests_text[:800]}",
            )

        # Playwright JSON
        pw_prompt = build_playwright_prompt(payload.acceptanceCriteria, payload.context, payload.baseUrl)
        pw_raw = call_llm(pw_prompt)
        pw_text = _clean_json_text(pw_raw)
        try:
            pw_obj = GeneratePlaywrightResponse.model_validate_json(pw_text)
        except Exception:
            raise HTTPException(
                status_code=502,
                detail=f"Gemini Playwright output not valid JSON matching schema. First 800 chars: {pw_text[:800]}",
            )

        return GenerateBothResponse(tests=tests_obj, playwright=pw_obj)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Server error: {str(e)}")

def jira_comment_test(issue_key: str, comment: str) -> Dict[str, Any]:
    jira_add_comment(issue_key, comment)
    return {"status": "comment_added", "issueKey": issue_key}
@app.post("/jira/comment-tests", operation_id="jira_comment_tests")
def jira_comment_tests_endpoint(payload: JiraCommentRequest):
    try:
        # Generate tests (keep this for convenience)
        prompt = build_tests_prompt(payload.acceptanceCriteria, payload.context)
        raw = call_llm(prompt)
        text = _clean_json_text(raw)
        tests = GenerateTestsResponse.model_validate_json(text)

        # Format
        comment = format_tests_for_jira(tests)

        # Send to Jira (via internal helper)
        return jira_comment_test(payload.issueKey, comment)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/playwright/write-files", operation_id="playwright_write_files")
def playwright_write_files_endpoint(payload: GeneratePlaywrightRequest):
    try:
        prompt = build_playwright_prompt(payload.acceptanceCriteria, payload.context, payload.baseUrl)
        raw = call_llm(prompt)
        text = _clean_json_text(raw)

        try:
            pw = GeneratePlaywrightResponse.model_validate_json(text)
        except Exception:
            raise HTTPException(
                status_code=502,
                detail=f"Gemini Playwright output not valid JSON matching schema. First 800 chars: {text[:800]}",
            )

        created = write_playwright_files([f.model_dump() for f in pw.files])

        return {
            "message": "Playwright tests written successfully",
            "files": created,
            "notes": pw.notes,
            "tags": pw.tags,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/jira/create-automation-task", operation_id="jira_create_automation_task")
def jira_create_automation_task_endpoint(payload: JiraAutomationTaskRequest):
    try:
        # Generate tests + playwright in one go (recommended)
        tests_prompt = build_tests_prompt(payload.acceptanceCriteria, payload.context)
        tests_text = _clean_json_text(call_llm(tests_prompt))
        tests = GenerateTestsResponse.model_validate_json(tests_text)

        pw_prompt = build_playwright_prompt(payload.acceptanceCriteria, payload.context, payload.baseUrl)
        pw_text = _clean_json_text(call_llm(pw_prompt))
        pw = GeneratePlaywrightResponse.model_validate_json(pw_text)

        # Build a clean description for Jira
        desc_lines = []
        desc_lines.append("AI Generated Test Scenarios")
        desc_lines.append("--------------------------")
        for s in tests.scenarios:
            desc_lines.append(f"\n{s.id} — {s.title}")
            desc_lines.append(f"Priority: {s.priority} | Type: {s.type}")
            desc_lines.append("Steps:")
            for i, step in enumerate(s.steps, 1):
                desc_lines.append(f"{i}. {step.action}")

        desc_lines.append("\n\nGenerated Playwright Files")
        desc_lines.append("-------------------------")
        for f in pw.files:
            desc_lines.append(f"- {f.path}")

        if pw.notes:
            desc_lines.append("\nNotes")
            desc_lines.append("-----")
            desc_lines.extend([f"- {n}" for n in pw.notes])

        description = "\n".join(desc_lines)

        summary = "Automation: Generate Playwright tests from acceptance criteria"

        created = jira_create_issue(
            summary=summary,
            description=description,
            issue_type=payload.issueType,
            parent_key=payload.parentIssueKey,
        )

        return {"status": "created", "issue": created}

    except Exception as e:
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))

class FullQAFlowRequest(BaseModel):
    issueKey: str
    acceptanceCriteria: str
    context: str | None = None
    baseUrl: str | None = None
    writePlaywrightFiles: bool = True
    createAutomationTask: bool = True
    automationIssueType: str = "Task"


@app.post("/jira/full-qa-flow", operation_id="jira_full_qa_flow")
def jira_full_qa_flow(payload: FullQAFlowRequest):
    try:
        # A) Generate tests (once)
        tests_prompt = build_tests_prompt(payload.acceptanceCriteria, payload.context)
        tests_raw = call_llm(tests_prompt)
        tests_text = _clean_json_text(tests_raw)
        tests = GenerateTestsResponse.model_validate_json(tests_text)

        # B) Comment tests to Jira
        comment = format_tests_for_jira(tests)
        jira_comment_test(payload.issueKey, comment)

        # C) Generate Playwright (once)
        pw_prompt = build_playwright_prompt(payload.acceptanceCriteria, payload.context, payload.baseUrl)
        pw_raw = call_llm(pw_prompt)
        pw_text = _clean_json_text(pw_raw)
        playwright = GeneratePlaywrightResponse.model_validate_json(pw_text)

        # D) Optionally write files
        files_written = None
        if payload.writePlaywrightFiles:
            files_written = write_playwright_files(playwright.files)  # use your existing internal fn

        # E) Optionally create Jira automation task
        task_created = None
        if payload.createAutomationTask:
            summary = f"{payload.issueKey} | Automation: Implement Playwright tests"
            description = "Generated Playwright tests are ready.\n\nFiles:\n" + "\n".join(
                f"- {f.path}" for f in playwright.files
            )
            task_created = jira_create_task(
                summary=summary,
                description=description,
                issue_type=payload.automationIssueType,
                parent_key=payload.issueKey,
            )

        return {
            "status": "ok",
            "jiraComment": {"issueKey": payload.issueKey},
            "tests": tests.model_dump(),
            "playwright": playwright.model_dump(),
            "filesWritten": files_written,
            "automationTask": task_created,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))






