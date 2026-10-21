from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "sqlite:///./taskflow.db"
    session_secret: str = Field(min_length=24, default="local-development-secret-change-me")
    session_ttl_hours: int = 168
    cookie_secure: bool = False
    frontend_origin: str = "http://localhost:5173"
    upload_dir: Path = Path("./storage/resumes")

    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parents[2] / ".env",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
