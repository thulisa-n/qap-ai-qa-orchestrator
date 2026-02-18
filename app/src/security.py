from fastapi import Header, HTTPException

from app.src.settings import get_settings


def require_api_key(x_api_key: str | None = Header(default=None, alias="X-API-Key")) -> None:
    settings = get_settings()
    # If API_AUTH_TOKEN is not configured, auth is intentionally disabled for local/dev.
    if not settings.api_auth_token:
        return

    if not x_api_key or x_api_key != settings.api_auth_token:
        raise HTTPException(status_code=401, detail="Unauthorized")
