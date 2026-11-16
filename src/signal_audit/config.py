"""Runtime settings, read from environment variables prefixed ``SIGAUDIT_``."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="SIGAUDIT_", env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    data_dir: Path = Path("data/cache")
    ledger_path: Path = Path("ledger/predictions.jsonl")

    reddit_client_id: str | None = None
    reddit_client_secret: SecretStr | None = None
    reddit_user_agent: str = "signal-audit-lab/0.1 (research; non-commercial)"


@lru_cache
def get_settings() -> Settings:
    return Settings()
