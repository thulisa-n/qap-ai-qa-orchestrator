from typing import Any, Protocol


class JobStore(Protocol):
    """Persistence API used by the QA job and healing-session routes.

    Implementations must return the same dict shapes the HTTP layer already exposes.
    `get_job_trace` is a projection of the stored job result, not a second record.
    """

    def create_job(
        self,
        *,
        job_id: str,
        issue_key: str,
        request_payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]: ...

    def mark_job_running(self, job_id: str) -> None: ...

    def mark_job_succeeded(self, job_id: str, result: dict[str, Any]) -> None: ...

    def mark_job_failed(self, job_id: str, error: str) -> None: ...

    def get_job(self, job_id: str) -> dict[str, Any] | None: ...

    def get_job_trace(self, job_id: str) -> dict[str, Any] | None: ...

    def update_job_result(self, job_id: str, result: dict[str, Any]) -> None: ...

    def list_jobs(
        self,
        *,
        limit: int = 20,
        status: str | None = None,
        issue_key: str | None = None,
    ) -> list[dict[str, Any]]: ...

    def cleanup_jobs(
        self,
        *,
        older_than_days: int = 30,
        status: str | None = None,
    ) -> dict[str, int]: ...

    def upsert_healing_sessions(
        self,
        *,
        job_id: str,
        issue_key: str,
        attempts: list[dict[str, Any]],
    ) -> None: ...

    def list_healing_sessions(
        self,
        *,
        limit: int = 20,
        issue_key: str | None = None,
        status: str | None = None,
        strategy: str | None = None,
    ) -> list[dict[str, Any]]: ...
