from __future__ import annotations

import base64
from functools import lru_cache
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.meta import PRODUCT_NAME


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", ".env.local"),
        env_prefix="FCC_",
        extra="ignore",
    )

    app_name: str = PRODUCT_NAME
    environment: Literal["development", "test", "production"] = "development"
    host: str = "127.0.0.1"
    port: int = Field(default=8765, ge=1, le=65535)
    database_url: str = "sqlite:///./.data/fantasy-command-center.db"
    admin_token: SecretStr | None = None
    encryption_key: SecretStr | None = None
    job_token: SecretStr | None = None
    session_days: int = Field(default=7, ge=1, le=30)
    default_season: int = Field(default=2026, ge=2019, le=2100)
    demo_mode: bool = False
    cors_origins: str = ""
    ai_provider: Literal["rules", "gemini", "openai-compatible"] = "rules"
    ai_model: str = ""
    ai_api_key: SecretStr | None = None
    ai_base_url: str = ""
    ai_timeout_seconds: float = Field(default=18.0, ge=3.0, le=60.0)
    max_ai_input_chars: int = Field(default=18_000, ge=2_000, le=50_000)
    espn_timeout_seconds: float = Field(default=20.0, ge=5.0, le=60.0)
    snapshot_cache_minutes: int = Field(default=10, ge=1, le=120)
    log_level: str = "INFO"
    login_attempt_limit: int = Field(default=6, ge=3, le=50)
    login_window_seconds: int = Field(default=60, ge=10, le=3600)

    @property
    def data_dir(self) -> Path:
        if self.database_url.startswith("sqlite:///./"):
            db_path = Path(self.database_url.removeprefix("sqlite:///"))
            return db_path.parent
        return Path(".data")

    @property
    def parsed_cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @model_validator(mode="after")
    def validate_security_configuration(self) -> Settings:
        if self.encryption_key is not None:
            try:
                decoded_key = base64.urlsafe_b64decode(
                    self.encryption_key.get_secret_value().encode("ascii")
                )
            except Exception as exc:
                raise ValueError("FCC_ENCRYPTION_KEY must be URL-safe base64") from exc
            if len(decoded_key) != 32:
                raise ValueError("FCC_ENCRYPTION_KEY must decode to exactly 32 bytes")
        if self.ai_base_url:
            parsed_ai_url = urlsplit(self.ai_base_url)
            if (
                parsed_ai_url.scheme not in {"http", "https"}
                or not parsed_ai_url.hostname
                or parsed_ai_url.username
                or parsed_ai_url.password
                or parsed_ai_url.fragment
            ):
                raise ValueError("FCC_AI_BASE_URL must be a valid HTTP(S) provider URL")
            if self.environment == "production" and parsed_ai_url.scheme != "https":
                raise ValueError("FCC_AI_BASE_URL must use HTTPS in production")
        if self.environment != "production":
            return self
        if self.demo_mode:
            raise ValueError("FCC_DEMO_MODE must be false in production")
        if self.admin_token is None or len(self.admin_token.get_secret_value()) < 32:
            raise ValueError("FCC_ADMIN_TOKEN must contain at least 32 characters in production")
        if self.encryption_key is None:
            raise ValueError("FCC_ENCRYPTION_KEY is required in production")
        if self.job_token is not None and len(self.job_token.get_secret_value()) < 32:
            raise ValueError("FCC_JOB_TOKEN must contain at least 32 characters")
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
