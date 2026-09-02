from __future__ import annotations

import datetime as dt

from sqlalchemy import (
    Boolean, DateTime, Index, Integer, String, Text, create_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker


class Base(DeclarativeBase):
    pass


def _utcnow() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


class OAuthClient(Base):
    """A registered MCP client.

    Two registration paths produce rows here:

    - Dynamic Client Registration (RFC 7591), where the client POSTs its metadata.
    - Client ID Metadata Documents, where the client_id is itself an HTTPS URL that
      resolves to the metadata. Anthropic's hosted client metadata uses this. Such rows
      are cached copies of a remote document, refreshed on expiry, and are marked
      `is_url_client` so they are never treated as bearer-secret clients.
    """

    __tablename__ = "oauth_clients"

    client_id: Mapped[str] = mapped_column(String(512), primary_key=True)
    # Public clients (PKCE, no secret) are the only kind MCP browser flows use. A secret
    # is stored only if a DCR client explicitly asked for a confidential method.
    client_secret_hash: Mapped[str | None] = mapped_column(String(128), default=None)
    client_name: Mapped[str] = mapped_column(String(255), default="")
    redirect_uris: Mapped[str] = mapped_column(Text, default="")  # newline-separated
    scope: Mapped[str] = mapped_column(String(512), default="leaguepilot:read")
    token_endpoint_auth_method: Mapped[str] = mapped_column(String(64), default="none")
    is_url_client: Mapped[bool] = mapped_column(Boolean, default=False)
    metadata_fetched_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    def redirect_uri_list(self) -> list[str]:
        return [u for u in (self.redirect_uris or "").split("\n") if u]


class AuthorizationCode(Base):
    """A single-use authorization code bound to a PKCE challenge and a resource.

    `used_at` makes replay detectable rather than merely improbable: a second
    presentation is rejected AND the associated grant is revoked, per OAuth 2.1
    guidance on code injection.
    """

    __tablename__ = "oauth_codes"

    code_hash: Mapped[str] = mapped_column(String(128), primary_key=True)
    client_id: Mapped[str] = mapped_column(String(512), index=True)
    subject: Mapped[str] = mapped_column(String(64), index=True)
    redirect_uri: Mapped[str] = mapped_column(String(2048))
    scope: Mapped[str] = mapped_column(String(512))
    resource: Mapped[str] = mapped_column(String(512))
    code_challenge: Mapped[str] = mapped_column(String(256))
    code_challenge_method: Mapped[str] = mapped_column(String(16), default="S256")
    # The PocketBase token captured at consent, so tool calls act as the real user and
    # inherit PocketBase's owner-scoped rules. Encrypted at rest.
    upstream_token_encrypted: Mapped[str] = mapped_column(Text)
    expires_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), index=True)
    used_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class Grant(Base):
    """A durable authorization grant. Revoking it invalidates every derived token."""

    __tablename__ = "oauth_grants"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    client_id: Mapped[str] = mapped_column(String(512), index=True)
    subject: Mapped[str] = mapped_column(String(64), index=True)
    scope: Mapped[str] = mapped_column(String(512))
    resource: Mapped[str] = mapped_column(String(512))
    upstream_token_encrypted: Mapped[str] = mapped_column(Text)
    refresh_token_hash: Mapped[str | None] = mapped_column(String(128), index=True, default=None)
    revoked_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    expires_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class SigningKey(Base):
    """An RSA signing key. Rotation publishes a new key while retaining the previous one
    in the JWKS until every token it signed has expired."""

    __tablename__ = "oauth_signing_keys"

    kid: Mapped[str] = mapped_column(String(64), primary_key=True)
    private_pem_encrypted: Mapped[str] = mapped_column(Text)
    public_jwk: Mapped[str] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    retire_after: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True))


Index("ix_codes_expiry", AuthorizationCode.expires_at, AuthorizationCode.used_at)
Index("ix_grants_active", Grant.subject, Grant.revoked_at)


def build_session_factory(database_url: str):
    engine = create_engine(database_url, future=True)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False, future=True)
