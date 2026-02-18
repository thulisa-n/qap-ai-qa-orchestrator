import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = BASE_DIR / ".env"
load_dotenv(ENV_PATH)


@dataclass(frozen=True)
class Settings:
    gemini_api_key: str | None
    gemini_model: str
    api_auth_token: str | None
    jira_base_url: str | None
    jira_email: str | None
    jira_api_token: str | None
    jira_project_key: str | None
    base_url: str | None


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings(
        gemini_api_key=os.getenv("GEMINI_API_KEY"),
        gemini_model=os.getenv("GEMINI_MODEL", "models/gemini-2.5-flash"),
        api_auth_token=os.getenv("API_AUTH_TOKEN"),
        jira_base_url=os.getenv("JIRA_BASE_URL"),
        jira_email=os.getenv("JIRA_EMAIL"),
        jira_api_token=os.getenv("JIRA_API_TOKEN"),
        jira_project_key=os.getenv("JIRA_PROJECT_KEY"),
        base_url=os.getenv("BASE_URL"),
    )
