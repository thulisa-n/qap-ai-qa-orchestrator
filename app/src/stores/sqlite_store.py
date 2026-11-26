import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import Lock
from typing import Any

from app.src.stores.models import (
    healing_session_from_sqlite_row,
    healing_sessions_from_attempts,
    job_from_sqlite_row,
    job_record,
    job_trace,
    utc_now_iso,
)


_LOCK = Lock()


class SqliteJobStore:
    def __init__(self, db_path: str) -> None:
        self._db_path = Path(db_path).resolve()

    def _ensure_db(self) -> Path:
        path = self._db_path
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
                    request_json TEXT,
                    error TEXT
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS healing_sessions (
                    session_id TEXT PRIMARY KEY,
                    job_id TEXT NOT NULL,
                    issue_key TEXT NOT NULL,
                    attempt INTEGER NOT NULL,
                    strategy TEXT NOT NULL,
                    status TEXT NOT NULL,
                    score_before REAL,
                    score_after REAL,
                    created_at TEXT NOT NULL
                )
                """
            )
            columns = {row[1] for row in conn.execute("PRAGMA table_info(jobs)").fetchall()}
            if "request_json" not in columns:
                conn.execute("ALTER TABLE jobs ADD COLUMN request_json TEXT")
            conn.commit()
        return path

    def create_job(
        self,
        *,
        job_id: str,
        issue_key: str,
        request_payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        job = job_record(
            job_id=job_id,
            issue_key=issue_key,
            status="pending",
            created_at=utc_now_iso(),
            started_at=None,
            completed_at=None,
            result=None,
            request_payload=request_payload,
            error=None,
        )
        db_path = self._ensure_db()
        with _LOCK:
            with sqlite3.connect(db_path) as conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO jobs (
                        job_id, issue_key, status, created_at, started_at, completed_at, result_json, request_json, error
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        job["jobId"],
                        job["issueKey"],
                        job["status"],
                        job["createdAt"],
                        job["startedAt"],
                        job["completedAt"],
                        None,
                        json.dumps(request_payload) if request_payload else None,
                        None,
                    ),
                )
                conn.commit()
        return job

    def mark_job_running(self, job_id: str) -> None:
        db_path = self._ensure_db()
        with _LOCK:
            with sqlite3.connect(db_path) as conn:
                conn.execute(
                    """
                    UPDATE jobs
                    SET status = ?, started_at = ?
                    WHERE job_id = ?
                    """,
                    ("running", utc_now_iso(), job_id),
                )
                conn.commit()

    def mark_job_succeeded(self, job_id: str, result: dict[str, Any]) -> None:
        db_path = self._ensure_db()
        with _LOCK:
            with sqlite3.connect(db_path) as conn:
                conn.execute(
                    """
                    UPDATE jobs
                    SET status = ?, completed_at = ?, result_json = ?, error = NULL
                    WHERE job_id = ?
                    """,
                    ("succeeded", utc_now_iso(), json.dumps(result), job_id),
                )
                conn.commit()

    def mark_job_failed(self, job_id: str, error: str) -> None:
        db_path = self._ensure_db()
        with _LOCK:
            with sqlite3.connect(db_path) as conn:
                conn.execute(
                    """
                    UPDATE jobs
                    SET status = ?, completed_at = ?, error = ?
                    WHERE job_id = ?
                    """,
                    ("failed", utc_now_iso(), error, job_id),
                )
                conn.commit()

    def get_job(self, job_id: str) -> dict[str, Any] | None:
        db_path = self._ensure_db()
        with _LOCK:
            with sqlite3.connect(db_path) as conn:
                row = conn.execute(
                    """
                    SELECT job_id, issue_key, status, created_at, started_at, completed_at, result_json, request_json, error
                    FROM jobs
                    WHERE job_id = ?
                    """,
                    (job_id,),
                ).fetchone()
                if not row:
                    return None
                return job_from_sqlite_row(row)

    def get_job_trace(self, job_id: str) -> dict[str, Any] | None:
        job = self.get_job(job_id)
        if not job:
            return None
        return job_trace(job)

    def update_job_result(self, job_id: str, result: dict[str, Any]) -> None:
        db_path = self._ensure_db()
        with _LOCK:
            with sqlite3.connect(db_path) as conn:
                conn.execute(
                    """
                    UPDATE jobs
                    SET result_json = ?
                    WHERE job_id = ?
                    """,
                    (json.dumps(result), job_id),
                )
                conn.commit()

    def list_jobs(
        self,
        *,
        limit: int = 20,
        status: str | None = None,
        issue_key: str | None = None,
    ) -> list[dict[str, Any]]:
        db_path = self._ensure_db()
        params: tuple[Any, ...]
        if status and issue_key:
            sql = """
                SELECT job_id, issue_key, status, created_at, started_at, completed_at, result_json, request_json, error
                FROM jobs
                WHERE status = ? AND issue_key = ?
                ORDER BY created_at DESC
                LIMIT ?
            """
            params = (status, issue_key, limit)
        elif status:
            sql = """
                SELECT job_id, issue_key, status, created_at, started_at, completed_at, result_json, request_json, error
                FROM jobs
                WHERE status = ?
                ORDER BY created_at DESC
                LIMIT ?
            """
            params = (status, limit)
        elif issue_key:
            sql = """
                SELECT job_id, issue_key, status, created_at, started_at, completed_at, result_json, request_json, error
                FROM jobs
                WHERE issue_key = ?
                ORDER BY created_at DESC
                LIMIT ?
            """
            params = (issue_key, limit)
        else:
            sql = """
                SELECT job_id, issue_key, status, created_at, started_at, completed_at, result_json, request_json, error
                FROM jobs
                ORDER BY created_at DESC
                LIMIT ?
            """
            params = (limit,)

        with _LOCK:
            with sqlite3.connect(db_path) as conn:
                rows = conn.execute(sql, params).fetchall()
                return [job_from_sqlite_row(row) for row in rows]

    def cleanup_jobs(self, *, older_than_days: int = 30, status: str | None = None) -> dict[str, int]:
        cutoff = datetime.now(timezone.utc) - timedelta(days=older_than_days)
        db_path = self._ensure_db()
        with _LOCK:
            with sqlite3.connect(db_path) as conn:
                if status:
                    rows = conn.execute(
                        "SELECT job_id, created_at FROM jobs WHERE status = ?",
                        (status,),
                    ).fetchall()
                else:
                    rows = conn.execute("SELECT job_id, created_at FROM jobs").fetchall()

                to_delete: list[str] = []
                for job_id, created_at in rows:
                    if not created_at:
                        continue
                    created_dt = datetime.fromisoformat(str(created_at).replace("Z", "+00:00"))
                    if created_dt < cutoff:
                        to_delete.append(str(job_id))

                if to_delete:
                    conn.executemany("DELETE FROM jobs WHERE job_id = ?", [(job_id,) for job_id in to_delete])
                    conn.executemany(
                        "DELETE FROM healing_sessions WHERE job_id = ?",
                        [(job_id,) for job_id in to_delete],
                    )
                    conn.commit()

        return {"deleted": len(to_delete), "evaluated": len(rows)}

    def upsert_healing_sessions(
        self,
        *,
        job_id: str,
        issue_key: str,
        attempts: list[dict[str, Any]],
    ) -> None:
        if not attempts:
            return

        sessions = healing_sessions_from_attempts(
            job_id=job_id,
            issue_key=issue_key,
            attempts=attempts,
            created_at=utc_now_iso(),
        )
        if not sessions:
            return

        rows = [
            (
                session["sessionId"],
                session["jobId"],
                session["issueKey"],
                session["attempt"],
                session["strategy"],
                session["status"],
                session["scoreBefore"],
                session["scoreAfter"],
                session["createdAt"],
            )
            for session in sessions
        ]
        db_path = self._ensure_db()
        with _LOCK:
            with sqlite3.connect(db_path) as conn:
                conn.execute("DELETE FROM healing_sessions WHERE job_id = ?", (job_id,))
                conn.executemany(
                    """
                    INSERT OR REPLACE INTO healing_sessions (
                        session_id, job_id, issue_key, attempt, strategy, status, score_before, score_after, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    rows,
                )
                conn.commit()

    def list_healing_sessions(
        self,
        *,
        limit: int = 20,
        issue_key: str | None = None,
        status: str | None = None,
        strategy: str | None = None,
    ) -> list[dict[str, Any]]:
        db_path = self._ensure_db()
        params: tuple[Any, ...]
        if issue_key and status and strategy:
            sql = """
                SELECT session_id, job_id, issue_key, attempt, strategy, status, score_before, score_after, created_at
                FROM healing_sessions
                WHERE issue_key = ? AND status = ? AND strategy = ?
                ORDER BY created_at DESC, attempt DESC
                LIMIT ?
            """
            params = (issue_key, status, strategy, limit)
        elif issue_key and status:
            sql = """
                SELECT session_id, job_id, issue_key, attempt, strategy, status, score_before, score_after, created_at
                FROM healing_sessions
                WHERE issue_key = ? AND status = ?
                ORDER BY created_at DESC, attempt DESC
                LIMIT ?
            """
            params = (issue_key, status, limit)
        elif issue_key and strategy:
            sql = """
                SELECT session_id, job_id, issue_key, attempt, strategy, status, score_before, score_after, created_at
                FROM healing_sessions
                WHERE issue_key = ? AND strategy = ?
                ORDER BY created_at DESC, attempt DESC
                LIMIT ?
            """
            params = (issue_key, strategy, limit)
        elif status and strategy:
            sql = """
                SELECT session_id, job_id, issue_key, attempt, strategy, status, score_before, score_after, created_at
                FROM healing_sessions
                WHERE status = ? AND strategy = ?
                ORDER BY created_at DESC, attempt DESC
                LIMIT ?
            """
            params = (status, strategy, limit)
        elif issue_key:
            sql = """
                SELECT session_id, job_id, issue_key, attempt, strategy, status, score_before, score_after, created_at
                FROM healing_sessions
                WHERE issue_key = ?
                ORDER BY created_at DESC, attempt DESC
                LIMIT ?
            """
            params = (issue_key, limit)
        elif status:
            sql = """
                SELECT session_id, job_id, issue_key, attempt, strategy, status, score_before, score_after, created_at
                FROM healing_sessions
                WHERE status = ?
                ORDER BY created_at DESC, attempt DESC
                LIMIT ?
            """
            params = (status, limit)
        elif strategy:
            sql = """
                SELECT session_id, job_id, issue_key, attempt, strategy, status, score_before, score_after, created_at
                FROM healing_sessions
                WHERE strategy = ?
                ORDER BY created_at DESC, attempt DESC
                LIMIT ?
            """
            params = (strategy, limit)
        else:
            sql = """
                SELECT session_id, job_id, issue_key, attempt, strategy, status, score_before, score_after, created_at
                FROM healing_sessions
                ORDER BY created_at DESC, attempt DESC
                LIMIT ?
            """
            params = (limit,)
        with _LOCK:
            with sqlite3.connect(db_path) as conn:
                rows = conn.execute(sql, params).fetchall()
                return [healing_session_from_sqlite_row(row) for row in rows]
