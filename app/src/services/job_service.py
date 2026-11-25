from typing import Any

from app.src.stores import get_job_store


def create_job(
    *,
    job_id: str,
    issue_key: str,
    request_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return get_job_store().create_job(
        job_id=job_id,
        issue_key=issue_key,
        request_payload=request_payload,
    )


def mark_job_running(job_id: str) -> None:
    get_job_store().mark_job_running(job_id)


def mark_job_succeeded(job_id: str, result: dict[str, Any]) -> None:
    get_job_store().mark_job_succeeded(job_id, result)


def mark_job_failed(job_id: str, error: str) -> None:
    get_job_store().mark_job_failed(job_id, error)


def get_job(job_id: str) -> dict[str, Any] | None:
    return get_job_store().get_job(job_id)


def get_job_trace(job_id: str) -> dict[str, Any] | None:
    return get_job_store().get_job_trace(job_id)


def update_job_result(job_id: str, result: dict[str, Any]) -> None:
    get_job_store().update_job_result(job_id, result)


def list_jobs(
    *,
    limit: int = 20,
    status: str | None = None,
    issue_key: str | None = None,
) -> list[dict[str, Any]]:
    return get_job_store().list_jobs(limit=limit, status=status, issue_key=issue_key)


def cleanup_jobs(*, older_than_days: int = 30, status: str | None = None) -> dict[str, int]:
    return get_job_store().cleanup_jobs(older_than_days=older_than_days, status=status)


def upsert_healing_sessions(
    *,
    job_id: str,
    issue_key: str,
    attempts: list[dict[str, Any]],
) -> None:
    get_job_store().upsert_healing_sessions(job_id=job_id, issue_key=issue_key, attempts=attempts)


def list_healing_sessions(
    *,
    limit: int = 20,
    issue_key: str | None = None,
    status: str | None = None,
    strategy: str | None = None,
) -> list[dict[str, Any]]:
    return get_job_store().list_healing_sessions(
        limit=limit,
        issue_key=issue_key,
        status=status,
        strategy=strategy,
    )
