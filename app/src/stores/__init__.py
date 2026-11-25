from app.src.settings import get_settings
from app.src.stores.protocol import JobStore
from app.src.stores.sqlite_store import SqliteJobStore


def get_job_store() -> JobStore:
    settings = get_settings()
    backend = (settings.job_store_backend or "sqlite").strip().lower()
    if not backend:
        backend = "sqlite"
    if backend == "sqlite":
        return SqliteJobStore(settings.job_db_path)
    raise RuntimeError(
        f"Unknown JOB_STORE_BACKEND: {settings.job_store_backend!r}. Expected 'sqlite'."
    )


__all__ = ["JobStore", "SqliteJobStore", "get_job_store"]
