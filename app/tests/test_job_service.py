import os
import socket
from urllib.parse import urlparse
from uuid import uuid4

import pytest

from app.src.services.job_service import (
    cleanup_jobs,
    create_job,
    get_job,
    get_job_trace,
    list_healing_sessions,
    list_jobs,
    mark_job_failed,
    mark_job_running,
    mark_job_succeeded,
    update_job_result,
    upsert_healing_sessions,
)
from app.src.settings import get_settings
from app.src.stores import get_job_store
from app.src.stores.models import utc_now_iso
from app.src.stores.sqlite_store import SqliteJobStore


BACKENDS = [
    pytest.param("sqlite", id="sqlite"),
    pytest.param("dynamodb", marks=pytest.mark.dynamodb, id="dynamodb"),
]


def _dynamodb_reachable() -> bool:
    endpoint = os.getenv("DYNAMODB_ENDPOINT", "").strip()
    if not endpoint:
        return False
    parsed = urlparse(endpoint)
    if not parsed.hostname or not parsed.port:
        return False
    try:
        with socket.create_connection((parsed.hostname, parsed.port), timeout=0.5):
            return True
    except OSError:
        return False


@pytest.fixture
def job_backend(request, monkeypatch, tmp_path):
    backend = request.param
    table_name = None
    if backend == "dynamodb":
        if not _dynamodb_reachable():
            pytest.skip(
                "DynamoDB Local is not reachable at DYNAMODB_ENDPOINT. "
                "SQLite tests still run. Start it with: docker compose --profile dynamodb up -d"
            )
        from app.src.stores.dynamodb_table import delete_table, ensure_table

        table_name = f"qap-test-{uuid4().hex[:12]}"
        monkeypatch.setenv("JOB_STORE_BACKEND", "dynamodb")
        monkeypatch.setenv("DYNAMODB_TABLE", table_name)
        monkeypatch.setenv("AWS_ACCESS_KEY_ID", os.getenv("AWS_ACCESS_KEY_ID", "local"))
        monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", os.getenv("AWS_SECRET_ACCESS_KEY", "local"))
        monkeypatch.setenv("AWS_DEFAULT_REGION", os.getenv("AWS_DEFAULT_REGION", "us-east-1"))
        get_settings.cache_clear()
        ensure_table(table_name)
    else:
        monkeypatch.setenv("JOB_STORE_BACKEND", "sqlite")
        monkeypatch.setenv("JOB_DB_PATH", str(tmp_path / "jobs.db"))
        get_settings.cache_clear()

    try:
        yield backend
    finally:
        get_settings.cache_clear()
        if table_name:
            from app.src.stores.dynamodb_table import delete_table

            delete_table(table_name)
            get_settings.cache_clear()


def test_default_job_store_is_sqlite(monkeypatch, tmp_path):
    monkeypatch.delenv("JOB_STORE_BACKEND", raising=False)
    monkeypatch.setenv("JOB_DB_PATH", str(tmp_path / "jobs.db"))
    get_settings.cache_clear()
    try:
        store = get_job_store()
        assert isinstance(store, SqliteJobStore)
    finally:
        get_settings.cache_clear()


def test_unknown_job_store_backend_fails(monkeypatch):
    monkeypatch.setenv("JOB_STORE_BACKEND", "memory")
    get_settings.cache_clear()
    try:
        with pytest.raises(RuntimeError, match="Unknown JOB_STORE_BACKEND"):
            get_job_store()
    finally:
        get_settings.cache_clear()


def test_dynamodb_backend_requires_endpoint(monkeypatch):
    monkeypatch.setenv("JOB_STORE_BACKEND", "dynamodb")
    monkeypatch.delenv("DYNAMODB_ENDPOINT", raising=False)
    get_settings.cache_clear()
    try:
        with pytest.raises(RuntimeError, match="DYNAMODB_ENDPOINT"):
            get_job_store()
    finally:
        get_settings.cache_clear()


@pytest.mark.parametrize("job_backend", BACKENDS, indirect=True)
def test_job_service_persists_state_in_sqlite(monkeypatch, tmp_path, job_backend):
    db_path = tmp_path / "jobs.db"
    monkeypatch.setenv("JOB_DB_PATH", str(db_path))
    get_settings.cache_clear()

    create_job(job_id="job-1", issue_key="QAP-101", request_payload={"acceptanceCriteria": "login"})
    mark_job_running("job-1")
    mark_job_succeeded("job-1", {"status": "ok", "issueKey": "QAP-101"})

    job = get_job("job-1")
    assert job is not None
    assert job["jobId"] == "job-1"
    assert job["issueKey"] == "QAP-101"
    assert job["status"] == "succeeded"
    assert job["result"]["status"] == "ok"
    assert job["requestPayload"]["acceptanceCriteria"] == "login"
    assert job["error"] is None

    update_job_result("job-1", {"status": "ok", "executionTrace": {"steps": ["saved"]}})
    updated = get_job("job-1")
    assert updated is not None
    assert updated["result"]["executionTrace"]["steps"] == ["saved"]
    assert updated["status"] == "succeeded"


@pytest.mark.parametrize("job_backend", BACKENDS, indirect=True)
def test_job_service_records_failures(monkeypatch, tmp_path, job_backend):
    db_path = tmp_path / "jobs.db"
    monkeypatch.setenv("JOB_DB_PATH", str(db_path))
    get_settings.cache_clear()

    create_job(job_id="job-2", issue_key="QAP-102")
    mark_job_failed("job-2", "simulated failure")

    job = get_job("job-2")
    assert job is not None
    assert job["status"] == "failed"
    assert job["error"] == "simulated failure"


@pytest.mark.parametrize("job_backend", BACKENDS, indirect=True)
def test_job_trace_extracts_execution_decisions(monkeypatch, tmp_path, job_backend):
    db_path = tmp_path / "jobs.db"
    monkeypatch.setenv("JOB_DB_PATH", str(db_path))
    get_settings.cache_clear()

    create_job(job_id="job-3", issue_key="QAP-103")
    mark_job_succeeded(
        "job-3",
        {
            "status": "ok",
            "executionTrace": {"steps": ["a", "b"], "taskCreated": False},
            "validatorDecision": {"isValid": True, "verdict": "pass"},
            "remediationDecision": {"action": "none", "status": "not_needed"},
            "governanceDecision": {"allowedForAutomation": True},
        },
    )

    trace = get_job_trace("job-3")
    assert trace is not None
    assert trace["jobId"] == "job-3"
    assert trace["executionTrace"]["steps"] == ["a", "b"]
    assert trace["validatorDecision"]["verdict"] == "pass"


@pytest.mark.parametrize("job_backend", BACKENDS, indirect=True)
def test_healing_sessions_persist_and_filter(monkeypatch, tmp_path, job_backend):
    db_path = tmp_path / "jobs.db"
    monkeypatch.setenv("JOB_DB_PATH", str(db_path))
    get_settings.cache_clear()

    create_job(job_id="job-4", issue_key="QAP-104")
    upsert_healing_sessions(
        job_id="job-4",
        issue_key="QAP-104",
        attempts=[
            {
                "attemptNumber": 1,
                "strategy": "initial_generation",
                "scoreBefore": None,
                "scoreAfter": 0.41,
                "outcome": "heal_requested",
            },
            {
                "attemptNumber": 2,
                "strategy": "heal_retry",
                "healStrategy": "enhance_prompt_quality",
                "scoreBefore": 0.41,
                "scoreAfter": 0.77,
                "outcome": "passed",
            },
        ],
    )

    sessions = list_healing_sessions(limit=10, issue_key="QAP-104")
    assert len(sessions) == 2
    assert sessions[0]["jobId"] == "job-4"
    by_attempt = {session["attempt"]: session for session in sessions}
    assert by_attempt[1]["scoreBefore"] is None
    assert by_attempt[1]["scoreAfter"] == pytest.approx(0.41)
    assert by_attempt[2]["scoreBefore"] == pytest.approx(0.41)
    assert by_attempt[2]["scoreAfter"] == pytest.approx(0.77)
    assert by_attempt[2]["strategy"] == "enhance_prompt_quality"

    filtered = list_healing_sessions(limit=10, issue_key="QAP-104", status="passed")
    assert len(filtered) == 1
    assert filtered[0]["status"] == "passed"

    by_strategy = list_healing_sessions(limit=10, strategy="enhance_prompt_quality")
    assert len(by_strategy) == 1
    assert by_strategy[0]["attempt"] == 2


@pytest.mark.parametrize("job_backend", BACKENDS, indirect=True)
def test_list_jobs_filters_by_status_and_issue(monkeypatch, tmp_path, job_backend):
    monkeypatch.setenv("JOB_DB_PATH", str(tmp_path / "jobs.db"))
    get_settings.cache_clear()

    create_job(job_id="job-a", issue_key="QAP-1")
    create_job(job_id="job-b", issue_key="QAP-1")
    mark_job_failed("job-b", "boom")
    create_job(job_id="job-c", issue_key="QAP-2")
    mark_job_succeeded("job-c", {"status": "ok"})

    failed = list_jobs(status="failed")
    assert [job["jobId"] for job in failed] == ["job-b"]

    issue_jobs = list_jobs(issue_key="QAP-1")
    assert {job["jobId"] for job in issue_jobs} == {"job-a", "job-b"}

    both = list_jobs(status="failed", issue_key="QAP-1")
    assert [job["jobId"] for job in both] == ["job-b"]

    other_issue = list_jobs(status="succeeded", issue_key="QAP-1")
    assert other_issue == []


@pytest.mark.parametrize("job_backend", BACKENDS, indirect=True)
def test_cleanup_jobs_drops_old_rows(monkeypatch, tmp_path, job_backend):
    monkeypatch.setenv("JOB_DB_PATH", str(tmp_path / "jobs.db"))
    get_settings.cache_clear()
    monkeypatch.setattr("app.src.stores.sqlite_store.utc_now_iso", lambda: "2000-01-01T00:00:00+00:00")
    monkeypatch.setattr("app.src.stores.dynamodb_store.utc_now_iso", lambda: "2000-01-01T00:00:00+00:00")

    create_job(job_id="old-job", issue_key="QAP-OLD")
    upsert_healing_sessions(
        job_id="old-job",
        issue_key="QAP-OLD",
        attempts=[{"attemptNumber": 1, "strategy": "heal_retry", "outcome": "failed"}],
    )

    monkeypatch.setattr("app.src.stores.sqlite_store.utc_now_iso", utc_now_iso)
    monkeypatch.setattr("app.src.stores.dynamodb_store.utc_now_iso", utc_now_iso)
    create_job(job_id="new-job", issue_key="QAP-NEW")

    result = cleanup_jobs(older_than_days=30)
    assert result["deleted"] == 1
    assert result["evaluated"] >= 1
    assert get_job("old-job") is None
    assert get_job("new-job") is not None
    assert list_healing_sessions(issue_key="QAP-OLD") == []
