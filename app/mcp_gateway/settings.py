from __future__ import annotations

from pydantic import AnyHttpUrl, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class McpSettings(BaseSettings):
    """MCP gateway configuration kept separate from the local monolith settings."""

    model_config = SettingsConfigDict(
        env_file=(".env", ".env.local"),
        env_prefix="LEAGUEPILOT_MCP_",
        extra="ignore",
    )

    cloudpod_url: AnyHttpUrl = "https://leaguepilot-ai.cloudpod.pro"
    host: str = "127.0.0.1"
    port: int = Field(default=8787, ge=1, le=65535)
    public_url: AnyHttpUrl = "http://127.0.0.1:8787"
    issuer_url: AnyHttpUrl = "https://leaguepilot.quntm.xyz"
    documentation_url: AnyHttpUrl = "https://leaguepilot.quntm.xyz"
    request_timeout_seconds: float = Field(default=20.0, ge=3.0, le=60.0)
    log_level: str = "INFO"

    @property
    def resource_url(self) -> str:
        return str(self.public_url).rstrip("/")

    @property
    def backend_url(self) -> str:
        return str(self.cloudpod_url).rstrip("/")
