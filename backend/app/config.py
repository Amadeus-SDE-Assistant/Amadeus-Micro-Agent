from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="AMADEUS_", env_file=".env", extra="ignore")

    app_name: str = "amadeus-micro-agent"
    log_level: str = "INFO"
    cors_origins: list[str] = ["http://localhost:5173"]

    # All agent file access stays inside this directory (SPEC §11).
    data_dir: Path = Path("./data")

    # Model + spend caps (SPEC §10 cost).
    agent_model: str = "claude-sonnet-5"
    agent_timeout_seconds: float = 120.0
    # Must stay below agent_timeout_seconds: the gate resolves (expired -> deny)
    # before the service's per-gap timeout treats the silence as a hang.
    approval_timeout_seconds: float = 90.0

    database_url: str = "postgresql+asyncpg://postgres:amadeus@localhost:5433/amadeus"


@lru_cache
def get_settings() -> Settings:
    return Settings()
