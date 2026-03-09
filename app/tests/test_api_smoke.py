import os

from fastapi.testclient import TestClient

from app.src.app import app
from app.src.settings import get_settings


VALID_TESTS_JSON = """
{
  "tags": ["smoke", "regression"],
  "scenarios": [
    {"id":"S1","title":"Happy path","priority":"P1","type":"e2e","steps":[{"action":"Open app","data":{}}]},
    {"id":"S2","title":"Negative input","priority":"P2","type":"api","steps":[{"action":"Send bad payload","data":{}}]},
    {"id":"S3","title":"Role guard","priority":"P1","type":"api","steps":[{"action":"Call protected endpoint","data":{}}]},
    {"id":"S4","title":"Session expiry","priority":"P2","type":"e2e","steps":[{"action":"Expire session","data":{}}]},
    {"id":"S5","title":"Rate limit","priority":"P2","type":"api","steps":[{"action":"Burst requests","data":{}}]}
  ],
  "notes": "ok"
}
""".strip()

VALID_PLAYWRIGHT_JSON = """
{
  "tags": ["smoke"],
  "files": [
    {
      "path": "tests/auth/login.spec.js",
      "content": "import { test, expect } from '@playwright/test';\\ntest('login', async ({ page }) => { await page.goto('/login'); });"
    }
  ],
  "notes": ["generated"]
}
""".strip()

VALID_QA_REPORT_JSON = """
{
  "note": "This report summarizes QA validation progress from provided acceptance criteria.",
  "testScenariosAndResults": [
    {
      "scenario": "API Request Audit",
      "stepsTaken": ["Monitor network tab on initial render", "Verify request count"],
      "expectedResult": "Expected baseline requests are reduced after optimization.",
      "actualResult": "Request count reduced and redundant calls removed.",
      "status": "Pass"
    },
    {
      "scenario": "User Info Optimization",
      "stepsTaken": ["Inspect request parameters"],
      "expectedResult": "Lite mode is used where applicable.",
      "actualResult": "mode=lite observed.",
      "status": "Pass"
    },
    {
      "scenario": "Caching Validation",
      "stepsTaken": ["Trigger repeated data requests"],
      "expectedResult": "Responses should be served from cache.",
      "actualResult": "Cache hits confirmed.",
      "status": "Pass"
    },
    {
      "scenario": "Data Integrity Check",
      "stepsTaken": ["Compare with baseline behavior"],
      "expectedResult": "Optimizations do not change business correctness.",
      "actualResult": "Functional parity maintained.",
      "status": "Pass"
    }
  ],
  "performanceBenchmarking": [
    {
      "page": "Dashboard",
      "baseline": "Not provided",
      "postOptimization": "Not provided",
      "improvement": "Not provided"
    }
  ],
  "environment": {
    "browser": "Not provided",
    "operatingSystem": "Not provided",
    "buildVersion": "Not provided",
    "testedUserAccount": "Not provided",
    "testedUrl": "Not provided"
  },
  "testOutcome": "Pass",
  "attachments": ["Video: Not provided"],
  "recommendations": [
    "Keep monitoring TTFB trends in CI performance dashboards.",
    "Add threshold alerts for regressions."
  ]
}
""".strip()

VALID_AUTOMATION_DECISION_YES_JSON = """
{
  "shouldCreateAutomationTask": true,
  "confidence": 0.92,
  "reason": "The flow is deterministic and high value for regression, so automation should be created now.",
  "recommendedCoverage": "full_automation",
  "automationRisk": "low",
  "riskReasons": ["Stable selectors", "Deterministic data and access patterns"]
}
""".strip()

VALID_AUTOMATION_DECISION_NO_JSON = """
{
  "shouldCreateAutomationTask": false,
  "confidence": 0.86,
  "reason": "Current criteria are exploratory and unstable, so keep this manual for now.",
  "recommendedCoverage": "manual_only",
  "automationRisk": "high",
  "riskReasons": ["Frequent UI/content changes", "Exploratory assertions are subjective"]
}
""".strip()


def _client_with_auth_token() -> TestClient:
    os.environ["API_AUTH_TOKEN"] = "smoke-token"
    get_settings.cache_clear()
    return TestClient(app)


def test_generate_both_smoke_contract(monkeypatch):
    client = _client_with_auth_token()

    responses = iter([VALID_TESTS_JSON, VALID_PLAYWRIGHT_JSON])

    def _mock_call_llm(_prompt: str) -> str:
        return next(responses)

    monkeypatch.setattr("app.src.routers.generation.call_llm", _mock_call_llm)

    response = client.post(
        "/generate-both",
        headers={"X-API-Key": "smoke-token"},
        json={"acceptanceCriteria": "Given a user logs in, when valid credentials are used, then access is granted."},
    )
    assert response.status_code == 200
    payload = response.json()
    assert "tests" in payload
    assert "playwright" in payload
    assert len(payload["tests"]["scenarios"]) >= 5
    assert payload["playwright"]["files"][0]["path"].startswith("tests/")


def test_jira_full_qa_flow_smoke_contract(monkeypatch):
    client = _client_with_auth_token()

    responses = iter(
        [VALID_TESTS_JSON, VALID_PLAYWRIGHT_JSON, VALID_AUTOMATION_DECISION_YES_JSON]
    )

    def _mock_call_llm(_prompt: str) -> str:
        return next(responses)

    monkeypatch.setattr("app.src.routers.jira.call_llm", _mock_call_llm)
    monkeypatch.setattr("app.src.routers.jira.jira_add_comment", lambda *args, **kwargs: {"ok": True})
    monkeypatch.setattr(
        "app.src.routers.jira.write_playwright_files",
        lambda _files: ["/tmp/playwright-tests/tests/auth/login.spec.js"],
    )
    monkeypatch.setattr(
        "app.src.routers.jira.jira_link_issues",
        lambda **kwargs: {"status": "linked"},
    )
    monkeypatch.setattr(
        "app.src.routers.jira.jira_create_issue",
        lambda **kwargs: {"key": "QAP-123", "summary": kwargs.get("summary", "")},
    )

    response = client.post(
        "/jira/full-qa-flow",
        headers={"X-API-Key": "smoke-token"},
        json={
            "issueKey": "QAP-10",
            "acceptanceCriteria": "Given valid credentials, when user signs in, then dashboard is shown with role access.",
            "commentOnJira": True,
            "writePlaywrightFiles": True,
            "createAutomationTask": True,
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["jiraComment"]["issueKey"] == "QAP-10"
    assert payload["automationDecision"]["shouldCreateAutomationTask"] is True
    assert payload["automationTask"]["key"] == "QAP-123"


def test_generate_qa_report_smoke_contract(monkeypatch):
    client = _client_with_auth_token()

    def _mock_call_llm(_prompt: str) -> str:
        return VALID_QA_REPORT_JSON

    monkeypatch.setattr("app.src.routers.generation.call_llm", _mock_call_llm)

    response = client.post(
        "/generate-qa-report",
        headers={"X-API-Key": "smoke-token"},
        json={
            "acceptanceCriteria": "Dashboard performance must improve and caching should reduce repeated data fetch latency.",
            "context": "Generate report using provided template style.",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert "testScenariosAndResults" in payload
    assert len(payload["testScenariosAndResults"]) >= 4
    assert payload["testOutcome"] in {"Pass", "Partial Pass", "Fail"}
    assert "tableView" in payload
    assert "||Scenario||Steps Taken||Expected Result||Actual Result||Status||" in payload["tableView"]


def test_jira_full_qa_flow_skips_task_when_ai_says_no(monkeypatch):
    client = _client_with_auth_token()
    responses = iter(
        [VALID_TESTS_JSON, VALID_PLAYWRIGHT_JSON, VALID_AUTOMATION_DECISION_NO_JSON]
    )

    def _mock_call_llm(_prompt: str) -> str:
        return next(responses)

    monkeypatch.setattr("app.src.routers.jira.call_llm", _mock_call_llm)
    monkeypatch.setattr("app.src.routers.jira.jira_add_comment", lambda *args, **kwargs: {"ok": True})
    monkeypatch.setattr(
        "app.src.routers.jira.write_playwright_files",
        lambda _files: ["/tmp/playwright-tests/tests/auth/login.spec.js"],
    )
    monkeypatch.setattr(
        "app.src.routers.jira.jira_link_issues",
        lambda **kwargs: {"status": "linked"},
    )

    called = {"count": 0}

    def _mock_create_issue(**kwargs):
        called["count"] += 1
        return {"key": "QAP-999", "summary": kwargs.get("summary", "")}

    monkeypatch.setattr("app.src.routers.jira.jira_create_issue", _mock_create_issue)

    response = client.post(
        "/jira/full-qa-flow",
        headers={"X-API-Key": "smoke-token"},
        json={
            "issueKey": "QAP-11",
            "acceptanceCriteria": "Given frequent UI experiments, when behavior changes weekly, then exploratory testing should lead.",
            "commentOnJira": True,
            "writePlaywrightFiles": True,
            "createAutomationTask": True,
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["automationDecision"]["shouldCreateAutomationTask"] is False
    assert payload["automationTask"] is None
    assert called["count"] == 0


def test_jira_full_qa_flow_async_accepts_request(monkeypatch):
    client = _client_with_auth_token()
    monkeypatch.setattr("app.src.routers.jira._run_full_qa_flow_background", lambda _payload_data: None)

    response = client.post(
        "/jira/full-qa-flow-async",
        headers={"X-API-Key": "smoke-token"},
        json={
            "issueKey": "QAP-12",
            "acceptanceCriteria": "Given an admin user, when billing page is opened, then access control should be enforced.",
            "commentOnJira": True,
            "writePlaywrightFiles": True,
            "createAutomationTask": True,
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "accepted"
    assert payload["mode"] == "async"


def test_create_issue_falls_back_from_subtask_to_task(monkeypatch):
    from app.src.routers.jira import _create_issue_with_fallback

    calls = {"count": 0}

    def _mock_create_issue(**kwargs):
        calls["count"] += 1
        if calls["count"] == 1:
            raise RuntimeError('Jira create issue error 400: {"errors":{"issuetype":"Specify a valid issue type"}}')
        return {"key": "QAP-456", "summary": kwargs.get("summary", "")}

    monkeypatch.setattr("app.src.routers.jira.jira_create_issue", _mock_create_issue)

    created, used_issue_type, warning = _create_issue_with_fallback(
        summary="Automation: Test",
        description="desc",
        issue_type="Sub-task",
        parent_key="QAP-10",
    )
    assert created["key"] == "QAP-456"
    assert used_issue_type == "Task"
    assert warning is not None


def test_extract_acceptance_criteria_ignores_non_ac_sections():
    from app.src.routers.jira import _extract_acceptance_criteria_items

    payload = """
h3. Description
We need QA coverage for role-based access behavior on the Billing area.

h3. Acceptance Criteria
- Admin users can access /admin/billing.
- Standard users receive 403 when navigating to /admin/billing.
- Unauthenticated users are redirected to /login.

h3. Optional Context
Environment is stable.

h3. Expected QAP output
- New test scenarios comment
""".strip()

    items = _extract_acceptance_criteria_items(payload)
    assert len(items) == 3
    assert items[0].startswith("Admin users")
    assert items[-1].startswith("Unauthenticated users")
