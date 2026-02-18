from typing import Any

import requests
from requests import Session
from requests.adapters import HTTPAdapter
from requests.auth import HTTPBasicAuth
from urllib3.util import Retry

from app.src.schemas import GenerateTestsResponse
from app.src.settings import get_settings


def _build_retry_session() -> Session:
    retry = Retry(
        total=3,
        backoff_factor=0.4,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=frozenset(["GET", "POST"]),
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session = requests.Session()
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


SESSION = _build_retry_session()


def _to_adf(text: str) -> dict[str, Any]:
    lines = (text or "").splitlines() or [""]
    content = []
    for line in lines:
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


def jira_auth(include_project_key: bool = False) -> tuple[str, str, str, str | None]:
    settings = get_settings()
    required = [settings.jira_base_url, settings.jira_email, settings.jira_api_token]
    if not all(required):
        raise RuntimeError(
            "Missing Jira env vars. Ensure JIRA_BASE_URL, JIRA_EMAIL, JIRA_API_TOKEN are set in app/.env"
        )

    if include_project_key and not settings.jira_project_key:
        raise RuntimeError("Missing JIRA_PROJECT_KEY in app/.env")

    return (
        settings.jira_base_url.rstrip("/"),
        settings.jira_email,
        settings.jira_api_token,
        settings.jira_project_key,
    )


def jira_add_comment(issue_key: str, comment: str) -> dict[str, Any]:
    base, email, token, _ = jira_auth(include_project_key=False)
    url = f"{base}/rest/api/3/issue/{issue_key}/comment"

    response = SESSION.post(
        url,
        json={"body": _to_adf(comment)},
        auth=HTTPBasicAuth(email, token),
        headers={"Accept": "application/json", "Content-Type": "application/json"},
        timeout=30,
    )

    if response.status_code >= 300:
        raise RuntimeError(f"Jira comment error {response.status_code}: {response.text}")
    return response.json()


def jira_create_issue(
    summary: str,
    description: str,
    issue_type: str = "Task",
    parent_key: str | None = None,
) -> dict[str, Any]:
    base, email, token, project_key = jira_auth(include_project_key=True)
    url = f"{base}/rest/api/3/issue"

    fields: dict[str, Any] = {
        "project": {"key": project_key},
        "summary": summary,
        "issuetype": {"name": issue_type},
        "description": _to_adf(description),
    }

    if issue_type.lower() in {"sub-task", "subtask"} and parent_key:
        fields["parent"] = {"key": parent_key}

    response = SESSION.post(
        url,
        json={"fields": fields},
        auth=HTTPBasicAuth(email, token),
        headers={"Accept": "application/json", "Content-Type": "application/json"},
        timeout=30,
    )
    if response.status_code >= 300:
        raise RuntimeError(f"Jira create issue error {response.status_code}: {response.text}")
    return response.json()


def jira_link_issues(
    inward_issue_key: str,
    outward_issue_key: str,
    link_type_name: str = "Relates",
) -> dict[str, Any]:
    base, email, token, _ = jira_auth(include_project_key=False)
    url = f"{base}/rest/api/3/issueLink"

    payload = {
        "type": {"name": link_type_name},
        "inwardIssue": {"key": inward_issue_key},
        "outwardIssue": {"key": outward_issue_key},
    }

    response = SESSION.post(
        url,
        json=payload,
        auth=HTTPBasicAuth(email, token),
        headers={"Accept": "application/json", "Content-Type": "application/json"},
        timeout=30,
    )
    if response.status_code >= 300:
        raise RuntimeError(f"Jira issue link error {response.status_code}: {response.text}")
    if response.text.strip():
        return response.json()
    return {"status": "linked"}


def format_tests_for_jira(tests: GenerateTestsResponse) -> str:
    lines = ["h2. AI Generated Test Scenarios"]
    for scenario in tests.scenarios:
        lines.append(f"\nh3. {scenario.id} — {scenario.title}")
        lines.append(f"*Priority:* {scenario.priority}")
        lines.append(f"*Type:* {scenario.type}")
        lines.append("*Steps:*")
        for index, step in enumerate(scenario.steps, 1):
            lines.append(f"{index}. {step.action}")

    if tests.notes:
        lines.append("\nh3. Notes")
        lines.append(tests.notes)
    return "\n".join(lines)
