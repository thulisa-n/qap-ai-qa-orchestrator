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

VALID_FEEDBACK_ANALYSIS_JSON = """
{
  "summary": "Most failures appear to be environment-related with one likely regression candidate.",
  "dominantClassification": "environment",
  "confidence": 0.82,
  "findings": [
    {
      "testName": "Authentication Tests › should allow login",
      "classification": "environment",
      "confidence": 0.86,
      "evidence": ["net::ERR_CONNECTION_REFUSED", "Base URL unreachable during run"],
      "suggestedAction": "Verify target environment availability and retry before opening a bug."
    },
    {
      "testName": "Billing API contract check",
      "classification": "regression",
      "confidence": 0.74,
      "evidence": ["Expected 200 but got 500", "Schema mismatch on required field"],
      "suggestedAction": "Open regression defect and add contract regression coverage for required fields."
    }
  ],
  "recommendations": [
    "Add a preflight health check in CI before running browser tests.",
    "Tag unstable selectors and monitor retry trend by spec."
  ],
  "suggestedRegressionTests": [
    "Add API contract test for billing widget required fields.",
    "Add smoke check to assert environment health endpoint returns 200 before E2E."
  ],
  "suggestedJiraTaskSummary": "Closed-loop follow-up: harden environment preflight and billing API contract regression coverage"
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

VALID_ARTIFACT_CRITIC_JSON = """
{
  "overallScore": 0.88,
  "scenarioQualityScore": 0.9,
  "playwrightQualityScore": 0.85,
  "isAcceptable": true,
  "findings": ["Minor selector hardening needed for one path."],
  "recommendations": ["Prefer role/label selectors where possible."],
  "verdict": "pass"
}
""".strip()

VALID_ARTIFACT_CRITIC_NEEDS_FIX_JSON = """
{
  "overallScore": 0.42,
  "scenarioQualityScore": 0.4,
  "playwrightQualityScore": 0.45,
  "isAcceptable": false,
  "findings": ["Critical assertions missing for security behavior."],
  "recommendations": ["Regenerate tests with stronger deterministic assertions."],
  "verdict": "needs_revision"
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
        [
            VALID_TESTS_JSON,
            VALID_PLAYWRIGHT_JSON,
            VALID_ARTIFACT_CRITIC_JSON,
            VALID_AUTOMATION_DECISION_YES_JSON,
        ]
    )

    def _mock_call_llm(_prompt: str) -> str:
        return next(responses)

    monkeypatch.setattr("app.src.routers.jira.call_llm", _mock_call_llm)
    monkeypatch.setattr("app.src.routers.jira.jira_add_comment", lambda *args, **kwargs: {"ok": True})
    label_calls = {"labels": []}
    monkeypatch.setattr(
        "app.src.routers.jira.jira_add_labels",
        lambda issue_key, labels: label_calls["labels"].append((issue_key, labels)) or {"ok": True},
    )
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
            "acceptanceCriteria": "Given role guard rules, when protected endpoint access is attempted, then session expiry and role-based access must be enforced.",
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
    assert payload["criticDecision"]["isAcceptable"] is True
    assert payload["validatorDecision"]["isValid"] is True
    assert payload["governanceDecision"]["allowedForAutomation"] is True
    assert "decisionExplanation" in payload
    assert payload["decisionExplanation"]["blocked"] is False
    assert payload["automationTask"]["key"] == "QAP-123"
    assert label_calls["labels"]
    assert label_calls["labels"][0][0] == "QAP-10"
    assert "qap-approved" in label_calls["labels"][0][1]
    assert "qap-automation-complete" in label_calls["labels"][0][1]


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


def test_pki_validate_profile_contract():
    client = _client_with_auth_token()
    response = client.post(
        "/pki/validate-profile",
        headers={"X-API-Key": "smoke-token"},
        json={
            "commonName": "localhost",
            "sanDns": [],
            "validityDays": 450,
            "keyAlgorithm": "RSA",
            "keySize": 2048,
            "environment": "prod",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["compliant"] is False
    assert payload["findings"]
    assert payload["policyVersion"] == "v1"


def test_pki_discover_demo_mode_contract():
    client = _client_with_auth_token()
    response = client.get(
        "/pki/discover?mode=demo&target=the-internet.herokuapp.com",
        headers={"X-API-Key": "smoke-token"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["mode"] == "demo"
    assert "certificates" in payload


def test_feedback_analysis_smoke_contract(monkeypatch):
    client = _client_with_auth_token()

    def _mock_call_llm(_prompt: str) -> str:
        return VALID_FEEDBACK_ANALYSIS_JSON

    monkeypatch.setattr("app.src.routers.generation.call_llm", _mock_call_llm)

    response = client.post(
        "/feedback/analyze-failures",
        headers={"X-API-Key": "smoke-token"},
        json={
            "source": "playwright",
            "failureReport": "Error: net::ERR_CONNECTION_REFUSED\\nExpected status 200, received 500 for /api/billing/widget-data",
            "context": "CI run #122 failed on auth and billing suites.",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["dominantClassification"] in {"flake", "environment", "regression"}
    assert payload["findings"]
    assert payload["suggestedJiraTaskSummary"]
    assert payload["resolvedIssueKey"] is None
    assert payload["jiraComment"] is None


def test_feedback_analysis_can_auto_comment_on_jira(monkeypatch):
    client = _client_with_auth_token()

    def _mock_call_llm(_prompt: str) -> str:
        return VALID_FEEDBACK_ANALYSIS_JSON

    monkeypatch.setattr("app.src.routers.generation.call_llm", _mock_call_llm)
    monkeypatch.setattr("app.src.routers.generation.jira_add_comment", lambda *_args, **_kwargs: {"ok": True})

    response = client.post(
        "/feedback/analyze-failures",
        headers={"X-API-Key": "smoke-token"},
        json={
            "source": "playwright",
            "issueKey": "QAP-20",
            "commentOnJira": True,
            "failureReport": "Error: Timeout 30000ms exceeded while waiting for locator",
            "context": "Nightly run on chrome only.",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["resolvedIssueKey"] == "QAP-20"
    assert payload["jiraComment"]["issueKey"] == "QAP-20"
    assert payload["jiraComment"]["status"] == "comment_added"


def test_feedback_analysis_requires_issue_key_for_auto_comment(monkeypatch):
    client = _client_with_auth_token()

    def _mock_call_llm(_prompt: str) -> str:
        return VALID_FEEDBACK_ANALYSIS_JSON

    monkeypatch.setattr("app.src.routers.generation.call_llm", _mock_call_llm)

    response = client.post(
        "/feedback/analyze-failures",
        headers={"X-API-Key": "smoke-token"},
        json={
            "source": "playwright",
            "commentOnJira": True,
            "failureReport": "Error: net::ERR_CONNECTION_REFUSED",
        },
    )
    assert response.status_code == 400
    assert "Could not resolve issueKey" in response.json()["detail"]


def test_feedback_analysis_can_infer_issue_key_from_branch(monkeypatch):
    client = _client_with_auth_token()

    def _mock_call_llm(_prompt: str) -> str:
        return VALID_FEEDBACK_ANALYSIS_JSON

    monkeypatch.setattr("app.src.routers.generation.call_llm", _mock_call_llm)
    monkeypatch.setattr(
        "app.src.routers.generation.jira_add_comment",
        lambda *_args, **_kwargs: {"ok": True},
    )

    response = client.post(
        "/feedback/analyze-failures",
        headers={"X-API-Key": "smoke-token"},
        json={
            "source": "playwright",
            "branchName": "feature/QAP-77-feedback-automation",
            "commentOnJira": True,
            "failureReport": "Error: locator timed out after 30s",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["resolvedIssueKey"] == "QAP-77"
    assert payload["jiraComment"]["issueKey"] == "QAP-77"


def test_jira_full_qa_flow_skips_task_when_ai_says_no(monkeypatch):
    client = _client_with_auth_token()
    responses = iter(
        [
            VALID_TESTS_JSON,
            VALID_PLAYWRIGHT_JSON,
            VALID_ARTIFACT_CRITIC_JSON,
            VALID_AUTOMATION_DECISION_NO_JSON,
        ]
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


def test_jira_full_qa_flow_blocks_task_when_governance_fails(monkeypatch):
    client = _client_with_auth_token()
    responses = iter(
        [
            VALID_TESTS_JSON,
            VALID_PLAYWRIGHT_JSON,
            VALID_ARTIFACT_CRITIC_JSON,
            VALID_AUTOMATION_DECISION_YES_JSON,
        ]
    )

    def _mock_call_llm(_prompt: str) -> str:
        return next(responses)

    monkeypatch.setattr("app.src.routers.jira.call_llm", _mock_call_llm)
    monkeypatch.setattr("app.src.routers.jira.jira_add_comment", lambda *args, **kwargs: {"ok": True})
    label_calls = {"labels": []}
    monkeypatch.setattr(
        "app.src.routers.jira.jira_add_labels",
        lambda issue_key, labels: label_calls["labels"].append((issue_key, labels)) or {"ok": True},
    )
    monkeypatch.setattr(
        "app.src.routers.jira.write_playwright_files",
        lambda _files: ["/tmp/playwright-tests/tests/auth/login.spec.js"],
    )
    monkeypatch.setattr(
        "app.src.routers.jira.evaluate_governance_gate",
        lambda **kwargs: {
            "framework": "ISTQB Foundation 4.0 (baseline principles mapping)",
            "policyVersion": {"istqb": "v1", "organization": "v1"},
            "allowedForAutomation": False,
            "requiresHumanApproval": True,
            "coverageRatio": 0.5,
            "automationRisk": "high",
            "violations": ["Coverage ratio 0.50 is below required minimum 0.75."],
            "summary": "Governance gate blocked automation task creation.",
        },
    )

    called = {"count": 0}

    def _mock_create_issue(**kwargs):
        called["count"] += 1
        return {"key": "QAP-998", "summary": kwargs.get("summary", "")}

    monkeypatch.setattr("app.src.routers.jira.jira_create_issue", _mock_create_issue)

    response = client.post(
        "/jira/full-qa-flow",
        headers={"X-API-Key": "smoke-token"},
        json={
            "issueKey": "QAP-13",
            "acceptanceCriteria": "Given admin and user roles, when billing page is accessed, then enforce role-based authorization with clear security messaging.",
            "commentOnJira": True,
            "writePlaywrightFiles": True,
            "createAutomationTask": True,
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["automationDecision"]["shouldCreateAutomationTask"] is True
    assert payload["governanceDecision"]["allowedForAutomation"] is False
    assert payload["automationTask"] is None
    assert called["count"] == 0
    assert label_calls["labels"]
    assert label_calls["labels"][0][0] == "QAP-13"
    assert "qap-needs-review" in label_calls["labels"][0][1]


def test_jira_full_qa_flow_blocks_task_when_validator_fails(monkeypatch):
    client = _client_with_auth_token()
    responses = iter(
        [
            VALID_TESTS_JSON,
            VALID_PLAYWRIGHT_JSON,
            VALID_ARTIFACT_CRITIC_NEEDS_FIX_JSON,
            VALID_AUTOMATION_DECISION_YES_JSON,
            VALID_TESTS_JSON,
            VALID_PLAYWRIGHT_JSON,
            VALID_ARTIFACT_CRITIC_NEEDS_FIX_JSON,
            VALID_AUTOMATION_DECISION_YES_JSON,
        ]
    )

    def _mock_call_llm(_prompt: str) -> str:
        return next(responses)

    monkeypatch.setattr("app.src.routers.jira.call_llm", _mock_call_llm)
    monkeypatch.setattr("app.src.routers.jira.jira_add_comment", lambda *args, **kwargs: {"ok": True})
    monkeypatch.setattr(
        "app.src.routers.jira.write_playwright_files",
        lambda _files: ["/tmp/playwright-tests/tests/auth/login.spec.js"],
    )

    called = {"count": 0}

    def _mock_create_issue(**kwargs):
        called["count"] += 1
        return {"key": "QAP-777", "summary": kwargs.get("summary", "")}

    monkeypatch.setattr("app.src.routers.jira.jira_create_issue", _mock_create_issue)

    response = client.post(
        "/jira/full-qa-flow",
        headers={"X-API-Key": "smoke-token"},
        json={
            "issueKey": "QAP-14",
            "acceptanceCriteria": "Given role-based controls, when user accesses protected endpoint, then authorization and session checks must be enforced.",
            "commentOnJira": True,
            "writePlaywrightFiles": True,
            "createAutomationTask": True,
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["automationDecision"]["shouldCreateAutomationTask"] is True
    assert payload["validatorDecision"]["isValid"] is False
    assert payload["remediationDecision"]["action"] in {"heal", "escalate"}
    assert payload["automationTask"] is None
    assert called["count"] == 0


def test_jira_full_qa_flow_async_accepts_request(monkeypatch):
    client = _client_with_auth_token()
    monkeypatch.setattr(
        "app.src.routers.jira._run_full_qa_flow_background",
        lambda _payload_data, _job_id: None,
    )

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
    assert payload["jobId"]
    assert payload["jobStatusPath"] == f"/jobs/{payload['jobId']}"

    job_response = client.get(
        f"/jobs/{payload['jobId']}",
        headers={"X-API-Key": "smoke-token"},
    )
    assert job_response.status_code == 200
    job_payload = job_response.json()
    assert job_payload["jobId"] == payload["jobId"]
    assert job_payload["issueKey"] == "QAP-12"
    assert job_payload["status"] in {"pending", "running", "succeeded", "failed"}


def test_get_async_job_status_returns_404_for_unknown_job():
    client = _client_with_auth_token()
    response = client.get(
        "/jobs/non-existent-job",
        headers={"X-API-Key": "smoke-token"},
    )
    assert response.status_code == 404


def test_get_async_job_trace_returns_404_for_unknown_job():
    client = _client_with_auth_token()
    response = client.get(
        "/jobs/non-existent-job/trace",
        headers={"X-API-Key": "smoke-token"},
    )
    assert response.status_code == 404


def test_retry_async_job_creates_new_job(monkeypatch):
    client = _client_with_auth_token()
    monkeypatch.setattr(
        "app.src.routers.jira._run_full_qa_flow_background",
        lambda _payload_data, _job_id: None,
    )

    create_response = client.post(
        "/jira/full-qa-flow-async",
        headers={"X-API-Key": "smoke-token"},
        json={
            "issueKey": "QAP-88",
            "acceptanceCriteria": "Given role checks, when API is called, then authorization is enforced.",
            "commentOnJira": False,
            "writePlaywrightFiles": False,
            "createAutomationTask": False,
        },
    )
    assert create_response.status_code == 200
    source_job_id = create_response.json()["jobId"]

    retry_response = client.post(
        f"/jobs/{source_job_id}/retry",
        headers={"X-API-Key": "smoke-token"},
    )
    assert retry_response.status_code == 200
    retry_payload = retry_response.json()
    assert retry_payload["mode"] == "retry"
    assert retry_payload["sourceJobId"] == source_job_id
    assert retry_payload["jobId"] != source_job_id


def test_proceed_anyway_creates_manual_override_task(monkeypatch):
    from app.src.services.job_service import create_job, mark_job_succeeded

    client = _client_with_auth_token()
    create_job(
        job_id="job-override-1",
        issue_key="QAP-89",
        request_payload={
            "issueKey": "QAP-89",
            "acceptanceCriteria": "Given blocked automation, when override is approved, then task may still be created.",
        },
    )
    mark_job_succeeded(
        "job-override-1",
        {
            "automationDecision": {
                "recommendedCoverage": "full_automation",
                "confidence": 0.91,
                "automationRisk": "medium",
            },
            "playwright": {"files": [{"path": "tests/auth.spec.js"}]},
            "validatorDecision": {"isValid": False, "verdict": "needs_fix"},
            "governanceDecision": {"allowedForAutomation": False},
        },
    )

    monkeypatch.setattr(
        "app.src.routers.jira._create_issue_with_fallback",
        lambda **_kwargs: ({"key": "QAP-900", "summary": "override task"}, "Task", None),
    )
    monkeypatch.setattr(
        "app.src.routers.jira.jira_link_issues",
        lambda **_kwargs: {"status": "linked"},
    )
    monkeypatch.setattr(
        "app.src.routers.jira.jira_add_comment",
        lambda *_args, **_kwargs: {"ok": True},
    )

    response = client.post(
        "/jobs/job-override-1/proceed-anyway",
        headers={"X-API-Key": "smoke-token"},
        json={"approvedBy": "qa.lead", "reason": "High-value regression path needed for release"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["mode"] == "proceed_anyway"
    assert payload["automationTask"]["key"] == "QAP-900"
    assert payload["overrideAudit"]["approvedBy"] == "qa.lead"
    assert payload["overrideAudit"]["reason"].startswith("High-value")
    assert payload["overrideAudit"]["approvedAt"]

    job_response = client.get(
        "/jobs/job-override-1",
        headers={"X-API-Key": "smoke-token"},
    )
    assert job_response.status_code == 200
    job_payload = job_response.json()
    assert job_payload["result"]["manualOverride"]["approvedBy"] == "qa.lead"


def test_explain_decision_endpoint_returns_trace_summary(monkeypatch):
    client = _client_with_auth_token()
    monkeypatch.setattr(
        "app.src.routers.jira._run_full_qa_flow_background",
        lambda _payload_data, _job_id: None,
    )

    create_response = client.post(
        "/jira/full-qa-flow-async",
        headers={"X-API-Key": "smoke-token"},
        json={
            "issueKey": "QAP-300",
            "acceptanceCriteria": "Given role checks, when API is called, then authorization is enforced.",
            "commentOnJira": False,
            "writePlaywrightFiles": False,
            "createAutomationTask": False,
        },
    )
    assert create_response.status_code == 200
    job_id = create_response.json()["jobId"]

    explain_response = client.get(
        f"/jobs/{job_id}/explain-decision",
        headers={"X-API-Key": "smoke-token"},
    )
    assert explain_response.status_code == 200
    payload = explain_response.json()
    assert payload["jobId"] == job_id
    assert "decisionExplanation" in payload


def test_list_async_jobs_supports_filters(monkeypatch):
    client = _client_with_auth_token()
    monkeypatch.setattr(
        "app.src.routers.jira._run_full_qa_flow_background",
        lambda _payload_data, _job_id: None,
    )

    for issue_key in ["QAP-30", "QAP-31"]:
        create_response = client.post(
            "/jira/full-qa-flow-async",
            headers={"X-API-Key": "smoke-token"},
            json={
                "issueKey": issue_key,
                "acceptanceCriteria": "Given admin role checks, when secured route is accessed, then authorization must be enforced.",
                "commentOnJira": False,
                "writePlaywrightFiles": False,
                "createAutomationTask": False,
            },
        )
        assert create_response.status_code == 200

    list_response = client.get(
        "/jobs?limit=10",
        headers={"X-API-Key": "smoke-token"},
    )
    assert list_response.status_code == 200
    list_payload = list_response.json()
    assert list_payload["count"] >= 2
    assert list_payload["jobs"]

    filtered_response = client.get(
        "/jobs?issueKey=QAP-31&limit=10",
        headers={"X-API-Key": "smoke-token"},
    )
    assert filtered_response.status_code == 200
    filtered_payload = filtered_response.json()
    assert filtered_payload["filters"]["issueKey"] == "QAP-31"
    assert all(job["issueKey"] == "QAP-31" for job in filtered_payload["jobs"])


def test_cleanup_jobs_endpoint_contract(monkeypatch):
    from app.src.services.job_service import create_job

    client = _client_with_auth_token()
    create_job(
        job_id="job-cleanup-1",
        issue_key="QAP-200",
        request_payload={"issueKey": "QAP-200", "acceptanceCriteria": "Given x then y"},
    )
    create_job(
        job_id="job-cleanup-2",
        issue_key="QAP-201",
        request_payload={"issueKey": "QAP-201", "acceptanceCriteria": "Given x then z"},
    )

    response = client.post(
        "/jobs/cleanup?olderThanDays=3650&status=failed",
        headers={"X-API-Key": "smoke-token"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["retention"]["olderThanDays"] == 3650
    assert "deleted" in payload
    assert "evaluated" in payload


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


def test_extract_acceptance_criteria_handles_markdown_subheadings():
    from app.src.routers.jira import _extract_acceptance_criteria_items

    payload = """
Goal
Validate the end-to-end flow.

Acceptance Criteria
# Full async QA flow
* Move ticket to In QA
* Confirm POST /jira/full-qa-flow-async returns jobId

# Jira comments are posted
* Verify comments appear for AI Generated Test Scenarios and QAP Governance Gate

Definition of Done
* Attach screenshots
""".strip()

    items = _extract_acceptance_criteria_items(payload)
    assert len(items) >= 3
    assert any("Move ticket to In QA" in item for item in items)
    assert any("returns jobId" in item for item in items)
    assert not any("Definition of Done" in item for item in items)


def test_format_tests_for_jira_filters_internal_notes():
    from app.src.schemas import GenerateTestsResponse
    from app.src.services.jira_service import format_tests_for_jira

    tests = GenerateTestsResponse.model_validate(
        {
            "tags": ["smoke"],
            "scenarios": [
                {
                    "id": "S1",
                    "title": "Happy path",
                    "priority": "P1",
                    "type": "e2e",
                    "steps": [{"action": "Open app", "data": {}}],
                }
            ],
            "notes": "Placeholder values are for illustration and would be dynamically generated.",
        }
    )

    comment = format_tests_for_jira(tests)
    assert "h3. Notes" not in comment


def test_dashboard_metrics_contract(monkeypatch):
    client = _client_with_auth_token()

    def _mock_list_jobs(*, limit=20, status=None, issue_key=None):
        if status == "failed":
            return [
                {
                    "jobId": "job-f1",
                    "issueKey": "QAP-2",
                    "status": "failed",
                    "createdAt": "2026-01-01T00:00:00Z",
                    "startedAt": "2026-01-01T00:00:02Z",
                    "completedAt": "2026-01-01T00:00:05Z",
                    "result": None,
                    "error": "LLM timeout",
                }
            ]

        return [
            {
                "jobId": "job-s1",
                "issueKey": "QAP-1",
                "status": "succeeded",
                "createdAt": "2026-01-01T00:00:00Z",
                "startedAt": "2026-01-01T00:00:02Z",
                "completedAt": "2026-01-01T00:00:10Z",
                "result": {
                    "governanceDecision": {"allowedForAutomation": True},
                    "validatorDecision": {"isValid": True},
                    "executionTrace": {"taskCreated": True},
                },
                "error": None,
            },
            {
                "jobId": "job-f1",
                "issueKey": "QAP-2",
                "status": "failed",
                "createdAt": "2026-01-01T00:00:00Z",
                "startedAt": "2026-01-01T00:00:02Z",
                "completedAt": "2026-01-01T00:00:05Z",
                "result": {
                    "governanceDecision": {"allowedForAutomation": False},
                    "validatorDecision": {"isValid": False},
                    "executionTrace": {"taskCreated": False},
                },
                "error": "LLM timeout",
            },
            {
                "jobId": "job-r1",
                "issueKey": "QAP-3",
                "status": "running",
                "createdAt": "2026-01-01T00:01:00Z",
                "startedAt": "2026-01-01T00:01:02Z",
                "completedAt": None,
                "result": None,
                "error": None,
            },
        ]

    monkeypatch.setattr("app.src.routers.dashboard.list_jobs", _mock_list_jobs)

    response = client.get(
        "/dashboard/metrics?sample_limit=50",
        headers={"X-API-Key": "smoke-token"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["sampleSize"] == 3
    assert payload["statusCounts"]["succeeded"] == 1
    assert payload["statusCounts"]["failed"] == 1
    assert payload["governanceBlockedCount"] == 1
    assert payload["validatorFailedCount"] == 1
    assert payload["automationTasksCreatedCount"] == 1
    assert payload["recentFailedJobs"][0]["jobId"] == "job-f1"


def test_dashboard_html_view_contract(monkeypatch):
    client = _client_with_auth_token()
    monkeypatch.setattr(
        "app.src.routers.dashboard.list_jobs",
        lambda **kwargs: [],
    )

    response = client.get(
        "/dashboard",
        headers={"X-API-Key": "smoke-token"},
    )
    assert response.status_code == 200
    assert "QAP Operations Dashboard" in response.text
    assert "No failed jobs in sample." in response.text
