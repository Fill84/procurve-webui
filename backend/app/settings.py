"""Application settings loaded from environment variables."""
from __future__ import annotations

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All runtime configuration. Values come from `.env` or OS env."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", case_sensitive=False)

    switch_host: str = Field(..., description="IP or hostname of the ProCurve switch")
    switch_port: int = Field(default=80)
    host: str = Field(default="127.0.0.1", description="Bind address for the UI")
    port: int = Field(default=8080)
    read_only: bool = Field(default=True)
    poll_interval_seconds: float = Field(default=2.0)
    session_secret: str = Field(..., min_length=32, description="Random signing key")
    session_ttl_hours: int = Field(default=8, gt=0)
    metrics_enabled: bool = Field(default=False)

    @field_validator("session_secret")
    @classmethod
    def _reject_placeholder(cls, v: str) -> str:
        if v.strip() in {"", "change-me", "your-secret-here"}:
            raise ValueError("SESSION_SECRET must be a real random value")
        return v
