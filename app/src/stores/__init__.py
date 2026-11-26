from app.src.settings import get_settings
from app.src.stores.dynamodb_store import DynamoDbJobStore
from app.src.stores.protocol import JobStore
from app.src.stores.sqlite_store import SqliteJobStore


def get_job_store() -> JobStore:
    settings = get_settings()
    backend = (settings.job_store_backend or "sqlite").strip().lower()
    if not backend:
        backend = "sqlite"
    if backend == "sqlite":
        return SqliteJobStore(settings.job_db_path)
    if backend == "dynamodb":
        if not (settings.dynamodb_endpoint or "").strip():
            raise RuntimeError(
                "JOB_STORE_BACKEND=dynamodb requires DYNAMODB_ENDPOINT. "
                "Refusing to start so a missing endpoint cannot call real AWS."
            )
        return DynamoDbJobStore()
    raise RuntimeError(
        f"Unknown JOB_STORE_BACKEND: {settings.job_store_backend!r}. Expected 'sqlite' or 'dynamodb'."
    )


__all__ = ["DynamoDbJobStore", "JobStore", "SqliteJobStore", "get_job_store"]
