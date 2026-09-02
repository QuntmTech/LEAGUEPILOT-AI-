from __future__ import annotations

from pydantic import AnyHttpUrl, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class AuthServerSettings(BaseSettings):
    """Configuration for the LEAGUEPILOT OAuth 2.1 authorization server.

    Kept separate from the MCP gateway settings so the two services can be deployed,
    scaled and rolled back independently.
    """

    model_config = SettingsConfigDict(
        env_file=(".env", ".env.local"),
        env_prefix="LEAGUEPILOT_AUTH_",
        extra="ignore",
    )

    # The issuer is baked into every token and every discovery document. It must be the
    # exact public HTTPS origin clients reach, including the trailing-slash convention
    # used by RFC 8414, or audience validation and metadata lookup both fail.
    issuer_url: AnyHttpUrl = "https://auth.leaguepilot.quntm.xyz/"
    # The MCP resource this server issues tokens for. Tokens are audience-bound to it.
    resource_url: AnyHttpUrl = "https://mcp.leaguepilot.quntm.xyz/"
    cloudpod_url: AnyHttpUrl = "https://leaguepilot-ai.cloudpod.pro"

    host: str = "127.0.0.1"
    port: int = Field(default=8790, ge=1, le=65535)

    # Storage for clients, codes, grants and signing keys. SQLite is sufficient for a
    # single-node deployment; the path must be on a persistent volume.
    database_url: str = "sqlite:///./.data/leaguepilot-auth.db"

    # Authorization codes are single-use and short-lived (OAuth 2.1 requires <= 10 min;
    # we are far stricter). Access tokens are short-lived and audience-bound.
    authorization_code_ttl_seconds: int = Field(default=60, ge=10, le=600)
    access_token_ttl_seconds: int = Field(default=3600, ge=300, le=86_400)
    refresh_token_ttl_seconds: int = Field(default=1_209_600, ge=3600, le=7_776_000)

    # Signing keys rotate on this cadence. Retired keys stay published in the JWKS for
    # one extra period so tokens issued just before a rotation still verify.
    signing_key_ttl_seconds: int = Field(default=2_592_000, ge=86_400)

    # Shared secret the MCP gateway presents to /introspect. Required: the endpoint
    # reveals whether a grant is live, and without a credential it would be protected
    # only by the unguessability of a grant id. A SecretStr keeps it out of reprs,
    # tracebacks and log lines. It is its own credential - never the Claude Code bearer,
    # the worker key, a signing key or a PocketBase administrator password.
    introspection_secret: SecretStr = Field(min_length=32)

    request_timeout_seconds: float = Field(default=20.0, ge=3.0, le=60.0)
    log_level: str = "INFO"

    @property
    def issuer(self) -> str:
        """RFC 8414 issuer identifier — no trailing slash in the metadata value."""
        return str(self.issuer_url).rstrip("/")

    @property
    def resource(self) -> str:
        return str(self.resource_url).rstrip("/")

    @property
    def backend_url(self) -> str:
        return str(self.cloudpod_url).rstrip("/")

    @property
    def introspection_token(self) -> str:
        return self.introspection_secret.get_secret_value()
