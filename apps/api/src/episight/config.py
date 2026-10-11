from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration, read from EPISIGHT_* environment variables or apps/api/.env."""

    model_config = SettingsConfigDict(env_prefix="EPISIGHT_", env_file=".env", extra="ignore")

    env: str = "dev"
    database_url: str = "postgresql+psycopg://episight:episight@localhost:5433/episight"
    cors_origins: list[str] = ["http://localhost:3000"]
    log_level: str = "INFO"

    @field_validator("database_url")
    @classmethod
    def _use_psycopg_driver(cls, url: str) -> str:
        # Managed Postgres hosts (Neon, Render, Railway) hand out postgres:// URLs; we ship psycopg 3 only.
        for scheme in ("postgres://", "postgresql://"):
            if url.startswith(scheme):
                return "postgresql+psycopg://" + url.removeprefix(scheme)
        return url


@lru_cache
def get_settings() -> Settings:
    return Settings()
