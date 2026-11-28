"""All settings come from environment variables (or a local .env file)."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from rti_mate.db.url import to_asyncpg_url


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "rti_mate"
    app_env: Literal["local", "ci", "production"]
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    data_file: Path = Path("data/sample_records.json")
    database_url: str = "postgresql://localhost:5432/rti_mate"
    db_pool_size: int = 5
    db_max_overflow: int = 10
    # The commit this image was built from. CI sets it (Dockerfile ARG GIT_SHA); locally "dev".
    git_sha: str = "dev"

    @field_validator("database_url", mode="before")
    @classmethod
    def convert_database_url(cls, value: str) -> str:
        return to_asyncpg_url(value)
        # LLM gateway (Day 8). Keys default to empty so tests and CI never need them.

    gemini_api_key: str = ""
    groq_api_key: str = ""
    llm_primary_model: str = "gemini-3.8-flash"
    llm_fallback_model: str = "openai/gpt-oss-20b"
    # Both providers speak the OpenAI API, so any compatible server works (Ollama, a test fake).
    llm_primary_base_url: str = "https://generativelanguage.googleapis.com/v1beta/openai"
    llm_fallback_base_url: str = "https://api.groq.com/openai/v1"
    llm_timeout_seconds: float = 30.0
    usd_inr: float = 95.0  # rupees per US dollar, for cost estimates
    prompts_dir: Path = Path("prompts")
    # Queue and worker (Day 10). One Redis; the worker is a second process running the same code.
    redis_url: str = "redis://localhost:6379"
    manifest_file: Path = Path("data/manifest.jsonl")
    admin_token: str = ""  # whoever sends this in X-Admin-Token may start an ingestion
    worker_in_api: bool = False  # True where no separate worker service exists (free hosting)
    ingest_concurrency: int = 2  # documents a worker handles at the same time
    ingest_rpm: float = 12.0  # model calls per minute, shared by those documents
    ingest_job_timeout: int = 60  # seconds; a longer job is stopped and tried again
    ingest_max_tries: int = 3


@lru_cache
def get_settings() -> Settings:
    """Build the settings once and reuse them."""
    return Settings()
