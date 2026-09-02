from __future__ import annotations

from pydantic import AnyHttpUrl, Field, SecretStr
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
    # The OAuth 2.1 authorization server. Deliberately NOT the dashboard host: that runs
    # on temporary cPanel infrastructure and will move, while an issuer baked into every
    # issued token must be permanent.
    issuer_url: AnyHttpUrl = "https://auth.leaguepilot.quntm.xyz/"
    documentation_url: AnyHttpUrl = "https://leaguepilot.quntm.xyz"
    # Where this gateway reaches the authorization server for JWKS and grant
    # introspection. Deliberately separate from `issuer_url`: the issuer is the public
    # identity stamped into every token and must stay the public HTTPS origin, while
    # these calls should travel the private network and never leave the host. Defaults
    # to the issuer so a single-host deployment still works unconfigured.
    internal_auth_url: AnyHttpUrl | None = None
    # Service credential presented to /introspect. Its own secret - never the Claude Code
    # bearer, the worker key, a signing key or a PocketBase administrator password.
    introspection_secret: SecretStr | None = None

    request_timeout_seconds: float = Field(default=20.0, ge=3.0, le=60.0)
    log_level: str = "INFO"

    @property
    def resource_url(self) -> str:
        return str(self.public_url).rstrip("/")

    @property
    def backend_url(self) -> str:
        return str(self.cloudpod_url).rstrip("/")

    @property
    def internal_auth_origin(self) -> str:
        """Private origin for JWKS and introspection, falling back to the public issuer."""
        return str(self.internal_auth_url or self.issuer_url).rstrip("/")

    @property
    def introspection_token(self) -> str | None:
        return (
            self.introspection_secret.get_secret_value()
            if self.introspection_secret is not None
            else None
        )
