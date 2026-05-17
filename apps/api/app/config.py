from __future__ import annotations

from pathlib import Path
from typing import Annotated

from pydantic import BeforeValidator, Field
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


def _split_csv(v: object) -> object:
    """Accept comma-separated env values so `API_KEYS=a,b` works.

    Bypasses pydantic-settings' default JSON decoder for list fields.
    """
    if isinstance(v, str):
        return [item.strip() for item in v.split(",") if item.strip()]
    return v


CsvList = Annotated[list[str], NoDecode, BeforeValidator(_split_csv)]


class Settings(BaseSettings):
    """Runtime configuration loaded from environment variables."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    trajectories_dir: Path = Field(
        default=Path("./fixtures/trajectories"),
        description="Root directory containing run subfolders with .traj files.",
    )
    db_path: Path = Field(
        default=Path("./data/index.sqlite"),
        description="SQLite file backing the metadata index.",
    )
    api_host: str = "0.0.0.0"
    api_port: int = 8080
    cors_origins: CsvList = Field(
        default_factory=lambda: ["http://localhost:3000", "http://localhost:3001"]
    )
    indexer_enabled: bool = True

    # Phase 8: optional auth + AI summary.
    api_keys: CsvList = Field(default_factory=list)
    anthropic_api_key: str | None = None
    summary_model: str = "claude-sonnet-4-5"

    # Phase 11: shares + embeddings.
    # `app_secret` signs share tokens. A blank value disables share creation.
    app_secret: str = ""
    site_url: str = "http://localhost:3001"
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"


settings = Settings()
