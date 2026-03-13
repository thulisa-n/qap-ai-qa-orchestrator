from app.src.services.job_service import (
    create_job,
    get_job,
    get_job_trace,
    mark_job_failed,
    mark_job_running,
    mark_job_succeeded,
)
from app.src.settings import get_settings


def test_job_service_persists_state_in_sqlite(monkeypatch, tmp_path):
    db_path = tmp_path / "jobs.db"
    monkeypatch.setenv("JOB_DB_PATH", str(db_path))
    get_settings.cache_clear()

    create_job(job_id="job-1", issue_key="QAP-101")
    mark_job_running("job-1")
    mark_job_succeeded("job-1", {"status": "ok", "issueKey": "QAP-101"})

    job = get_job("job-1")
    assert job is not None
    assert job["jobId"] == "job-1"
    assert job["issueKey"] == "QAP-101"
    assert job["status"] == "succeeded"
    assert job["result"]["status"] == "ok"


def test_job_service_records_failures(monkeypatch, tmp_path):
    db_path = tmp_path / "jobs.db"
    monkeypatch.setenv("JOB_DB_PATH", str(db_path))
    get_settings.cache_clear()

    create_job(job_id="job-2", issue_key="QAP-102")
    mark_job_failed("job-2", "simulated failure")

    job = get_job("job-2")
    assert job is not None
    assert job["status"] == "failed"
    assert job["error"] == "simulated failure"


def test_job_trace_extracts_execution_decisions(monkeypatch, tmp_path):
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
