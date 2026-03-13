import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any

from app.src.settings import get_settings


_LOCK = Lock()


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _db_path() -> Path:
    return Path(get_settings().job_db_path).resolve()


def _ensure_db() -> Path:
    path = _db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS jobs (
                job_id TEXT PRIMARY KEY,
                issue_key TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                started_at TEXT,
                completed_at TEXT,
                result_json TEXT,
                error TEXT
            )
            """
        )
        conn.commit()
    return path


def _row_to_job(row: tuple[Any, ...]) -> dict[str, Any]:
    (
        job_id,
        issue_key,
        status,
        created_at,
        started_at,
        completed_at,
        result_json,
        error,
    ) = row
    return {
        "jobId": job_id,
        "issueKey": issue_key,
        "status": status,
        "createdAt": created_at,
        "startedAt": started_at,
        "completedAt": completed_at,
        "result": json.loads(result_json) if result_json else None,
        "error": error,
    }


def create_job(*, job_id: str, issue_key: str) -> dict[str, Any]:
    job = {
        "jobId": job_id,
        "issueKey": issue_key,
        "status": "pending",
        "createdAt": _utc_now_iso(),
        "startedAt": None,
        "completedAt": None,
        "result": None,
        "error": None,
    }
    db_path = _ensure_db()
    with _LOCK:
        with sqlite3.connect(db_path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO jobs (
                    job_id, issue_key, status, created_at, started_at, completed_at, result_json, error
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    job["jobId"],
                    job["issueKey"],
                    job["status"],
                    job["createdAt"],
                    job["startedAt"],
                    job["completedAt"],
                    None,
                    None,
                ),
            )
            conn.commit()
    return job


def mark_job_running(job_id: str) -> None:
    db_path = _ensure_db()
    with _LOCK:
        with sqlite3.connect(db_path) as conn:
            conn.execute(
                """
                UPDATE jobs
                SET status = ?, started_at = ?
                WHERE job_id = ?
                """,
                ("running", _utc_now_iso(), job_id),
            )
            conn.commit()


def mark_job_succeeded(job_id: str, result: dict[str, Any]) -> None:
    db_path = _ensure_db()
    with _LOCK:
        with sqlite3.connect(db_path) as conn:
            conn.execute(
                """
                UPDATE jobs
                SET status = ?, completed_at = ?, result_json = ?, error = NULL
                WHERE job_id = ?
                """,
                ("succeeded", _utc_now_iso(), json.dumps(result), job_id),
            )
            conn.commit()


def mark_job_failed(job_id: str, error: str) -> None:
    db_path = _ensure_db()
    with _LOCK:
        with sqlite3.connect(db_path) as conn:
            conn.execute(
                """
                UPDATE jobs
                SET status = ?, completed_at = ?, error = ?
                WHERE job_id = ?
                """,
                ("failed", _utc_now_iso(), error, job_id),
            )
            conn.commit()


def get_job(job_id: str) -> dict[str, Any] | None:
    db_path = _ensure_db()
    with _LOCK:
        with sqlite3.connect(db_path) as conn:
            row = conn.execute(
                """
                SELECT job_id, issue_key, status, created_at, started_at, completed_at, result_json, error
                FROM jobs
                WHERE job_id = ?
                """,
                (job_id,),
            ).fetchone()
            if not row:
                return None
            return _row_to_job(row)


def get_job_trace(job_id: str) -> dict[str, Any] | None:
    job = get_job(job_id)
    if not job:
        return None
    result = job.get("result") or {}
    return {
        "jobId": job["jobId"],
        "issueKey": job["issueKey"],
        "status": job["status"],
        "executionTrace": result.get("executionTrace"),
        "validatorDecision": result.get("validatorDecision"),
        "remediationDecision": result.get("remediationDecision"),
        "governanceDecision": result.get("governanceDecision"),
        "error": job.get("error"),
    }


def list_jobs(
    *,
    limit: int = 20,
    status: str | None = None,
    issue_key: str | None = None,
) -> list[dict[str, Any]]:
    db_path = _ensure_db()
    params: tuple[Any, ...]
    if status and issue_key:
        sql = """
            SELECT job_id, issue_key, status, created_at, started_at, completed_at, result_json, error
            FROM jobs
            WHERE status = ? AND issue_key = ?
            ORDER BY created_at DESC
            LIMIT ?
        """
        params = (status, issue_key, limit)
    elif status:
        sql = """
            SELECT job_id, issue_key, status, created_at, started_at, completed_at, result_json, error
            FROM jobs
            WHERE status = ?
            ORDER BY created_at DESC
            LIMIT ?
        """
        params = (status, limit)
    elif issue_key:
        sql = """
            SELECT job_id, issue_key, status, created_at, started_at, completed_at, result_json, error
            FROM jobs
            WHERE issue_key = ?
            ORDER BY created_at DESC
            LIMIT ?
        """
        params = (issue_key, limit)
    else:
        sql = """
            SELECT job_id, issue_key, status, created_at, started_at, completed_at, result_json, error
            FROM jobs
            ORDER BY created_at DESC
            LIMIT ?
        """
        params = (limit,)

    with _LOCK:
        with sqlite3.connect(db_path) as conn:
            rows = conn.execute(sql, params).fetchall()
            return [_row_to_job(row) for row in rows]
