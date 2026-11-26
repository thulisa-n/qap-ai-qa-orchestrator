import json
from datetime import datetime, timezone
from typing import Any


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def job_record(
    *,
    job_id: str,
    issue_key: str,
    status: str,
    created_at: str,
    started_at: str | None,
    completed_at: str | None,
    result: dict[str, Any] | None,
    request_payload: dict[str, Any] | None,
    error: str | None,
) -> dict[str, Any]:
    return {
        "jobId": job_id,
        "issueKey": issue_key,
        "status": status,
        "createdAt": created_at,
        "startedAt": started_at,
        "completedAt": completed_at,
        "result": result,
        "requestPayload": request_payload,
        "error": error,
    }


def job_from_sqlite_row(row: tuple[Any, ...]) -> dict[str, Any]:
    (
        job_id,
        issue_key,
        status,
        created_at,
        started_at,
        completed_at,
        result_json,
        request_json,
        error,
    ) = row
    return job_record(
        job_id=job_id,
        issue_key=issue_key,
        status=status,
        created_at=created_at,
        started_at=started_at,
        completed_at=completed_at,
        result=json.loads(result_json) if result_json else None,
        request_payload=json.loads(request_json) if request_json else None,
        error=error,
    )


def job_trace(job: dict[str, Any]) -> dict[str, Any]:
    result = job.get("result") or {}
    return {
        "jobId": job["jobId"],
        "issueKey": job["issueKey"],
        "status": job["status"],
        "executionTrace": result.get("executionTrace"),
        "criticDecision": result.get("criticDecision"),
        "validatorDecision": result.get("validatorDecision"),
        "remediationDecision": result.get("remediationDecision"),
        "governanceDecision": result.get("governanceDecision"),
        "decisionExplanation": result.get("decisionExplanation"),
        "error": job.get("error"),
    }


def healing_session_record(
    *,
    session_id: str,
    job_id: str,
    issue_key: str,
    attempt: int,
    strategy: str,
    status: str,
    score_before: float | None,
    score_after: float | None,
    created_at: str,
) -> dict[str, Any]:
    return {
        "sessionId": session_id,
        "jobId": job_id,
        "issueKey": issue_key,
        "attempt": attempt,
        "strategy": strategy,
        "status": status,
        "scoreBefore": score_before,
        "scoreAfter": score_after,
        "createdAt": created_at,
    }


def healing_sessions_from_attempts(
    *,
    job_id: str,
    issue_key: str,
    attempts: list[dict[str, Any]],
    created_at: str,
) -> list[dict[str, Any]]:
    sessions: list[dict[str, Any]] = []
    for attempt in attempts:
        attempt_number = int(attempt.get("attemptNumber") or 0)
        if attempt_number <= 0:
            continue
        strategy = str(attempt.get("healStrategy") or attempt.get("strategy") or "unknown")
        status = str(attempt.get("outcome") or "unknown")
        sessions.append(
            healing_session_record(
                session_id=f"{job_id}:attempt:{attempt_number}",
                job_id=job_id,
                issue_key=issue_key,
                attempt=attempt_number,
                strategy=strategy,
                status=status,
                score_before=attempt.get("scoreBefore"),
                score_after=attempt.get("scoreAfter"),
                created_at=created_at,
            )
        )
    return sessions


def healing_session_from_sqlite_row(row: tuple[Any, ...]) -> dict[str, Any]:
    (
        session_id,
        job_id,
        issue_key,
        attempt,
        strategy,
        status,
        score_before,
        score_after,
        created_at,
    ) = row
    return healing_session_record(
        session_id=session_id,
        job_id=job_id,
        issue_key=issue_key,
        attempt=attempt,
        strategy=strategy,
        status=status,
        score_before=score_before,
        score_after=score_after,
        created_at=created_at,
    )
