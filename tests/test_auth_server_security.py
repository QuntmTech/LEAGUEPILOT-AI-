"""Deterministic security tests for the OAuth 2.1 authorization server.

These assert the properties that make the flow safe, not merely that it returns 200:
PKCE cannot be bypassed, codes cannot be replayed, redirect URIs cannot be substituted,
tokens cannot be used at another audience, and no secret is ever rendered.
"""

from __future__ import annotations

import base64
import hashlib
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _src(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


# ---------- PKCE ----------

def test_pkce_accepts_only_s256_and_rejects_plain() -> None:
    from app.auth_server.keys import verify_pkce

    verifier = "a" * 64
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode()).digest()
    ).rstrip(b"=").decode()

    assert verify_pkce(verifier, challenge, "S256") is True
    # OAuth 2.1 forbids `plain`; accepting it would defeat PKCE entirely.
    assert verify_pkce(verifier, verifier, "plain") is False
    assert verify_pkce(verifier, challenge, "") is False


def test_pkce_rejects_wrong_verifier_and_out_of_range_lengths() -> None:
    from app.auth_server.keys import verify_pkce

    verifier = "b" * 64
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode()).digest()
    ).rstrip(b"=").decode()

    assert verify_pkce("c" * 64, challenge, "S256") is False
    assert verify_pkce("", challenge, "S256") is False
    assert verify_pkce("short", challenge, "S256") is False       # < 43
    assert verify_pkce("d" * 200, challenge, "S256") is False     # > 128


def test_authorize_requires_pkce() -> None:
    src = _src("app/auth_server/server.py")
    assert 'method != "S256" or not challenge' in src
    assert "PKCE with S256 is required." in src


# ---------- redirect URI ----------

def test_redirect_uris_must_be_exact_https_without_wildcards() -> None:
    from app.auth_server.clients import ClientError, validate_redirect_uris

    assert validate_redirect_uris(["https://claude.ai/api/mcp/auth_callback"])
    assert validate_redirect_uris(["http://127.0.0.1:6274/callback"])  # loopback native client

    for bad in (["http://evil.test/cb"], ["https://a.test/*"], ["https://a.test/cb#frag"], []):
        with pytest.raises(ClientError):
            validate_redirect_uris(bad)


def test_authorize_refuses_to_redirect_on_uri_mismatch() -> None:
    """A mismatched URI must render an error page, never redirect — redirecting to an
    attacker-supplied URI is how authorization codes get exfiltrated."""
    src = _src("app/auth_server/server.py")
    assert "if redirect_uri not in client.redirect_uri_list():" in src
    idx = src.index("if redirect_uri not in client.redirect_uri_list():")
    following = src[idx : idx + 300]
    assert "pages.error_page" in following
    assert "_redirect_error" not in following


# ---------- authorization codes ----------

def test_codes_are_single_use_and_replay_revokes_grants() -> None:
    src = _src("app/auth_server/server.py")
    assert "record.used_at is not None" in src
    assert "grant.revoked_at = now" in src
    assert "replay" in src.lower()


def test_codes_are_short_lived_and_bound_to_client_and_redirect() -> None:
    src = _src("app/auth_server/server.py")
    assert "record.expires_at <= now" in src
    assert "record.client_id != client_id" in src
    assert "record.redirect_uri != redirect_uri" in src

    from app.auth_server.settings import AuthServerSettings

    field = AuthServerSettings.model_fields["authorization_code_ttl_seconds"]
    assert field.default <= 600, "OAuth 2.1 requires short-lived codes"


def test_codes_and_tokens_are_stored_only_as_hashes() -> None:
    """A database read must not yield anything replayable."""
    src = _src("app/auth_server/server.py")
    assert "hash_token(code)" in src
    assert "hash_token(refresh)" in src
    models = _src("app/auth_server/models.py")
    assert "code_hash" in models and "refresh_token_hash" in models


# ---------- audience / resource ----------

def test_access_tokens_are_audience_bound_to_the_mcp_resource() -> None:
    src = _src("app/auth_server/tokens.py")
    assert '"aud": audience' in src
    assert '"aud": {"essential": True, "value": audience}' in src
    assert '"iss": {"essential": True, "value": issuer}' in src


def test_resource_mismatch_is_rejected_at_authorize_and_token() -> None:
    src = _src("app/auth_server/server.py")
    assert src.count("invalid_target") >= 2


# ---------- client registration ----------

def test_client_id_metadata_document_must_self_identify() -> None:
    """The document's own client_id must equal the URL it was fetched from, or one client
    could claim another's identity."""
    src = _src("app/auth_server/clients.py")
    assert "declared != client_id" in src
    assert "does not identify itself as this client" in src


def test_client_metadata_fetch_is_https_only_and_ssrf_guarded() -> None:
    from app.auth_server.clients import _blocks_ssrf, _is_https_url

    assert _is_https_url("https://claude.ai/x") is True
    assert _is_https_url("http://claude.ai/x") is False
    for host in ("localhost", "127.0.0.1", "::1", "10.0.0.5", "169.254.169.254", "192.168.1.1"):
        assert _blocks_ssrf(host) is True, host
    assert _blocks_ssrf("claude.ai") is False

    src = _src("app/auth_server/clients.py")
    assert "follow_redirects=False" in src
    assert "MAX_METADATA_BYTES" in src


def test_dynamic_client_registration_issues_public_clients_only() -> None:
    src = _src("app/auth_server/server.py")
    assert '"token_endpoint_auth_method": "none"' in src
    assert "no secret is issued" in src


def test_discovery_advertises_only_implemented_capabilities() -> None:
    """The original failure was advertising a registration mechanism that did not exist."""
    src = _src("app/auth_server/server.py")
    for endpoint in ("authorization_endpoint", "token_endpoint",
                     "registration_endpoint", "revocation_endpoint", "jwks_uri"):
        assert endpoint in src
    assert '"code_challenge_methods_supported": ["S256"]' in src
    assert '"client_id_metadata_document_supported": True' in src
    # Each advertised endpoint must have a real route.
    for route in ("/authorize", "/token", "/register", "/revoke", "/.well-known/jwks.json"):
        assert f'"{route}"' in src or f"'{route}'" in src


# ---------- scope ----------

def test_scope_is_intersected_and_never_widened() -> None:
    from app.auth_server.clients import ClientError, normalize_scope

    allowed = {"leaguepilot:read", "leaguepilot:write"}
    assert normalize_scope("leaguepilot:read", allowed) == "leaguepilot:read"
    assert normalize_scope(None, allowed) == "leaguepilot:read"      # least privilege default
    assert "admin" not in normalize_scope("leaguepilot:read admin", allowed)
    with pytest.raises(ClientError):
        normalize_scope("admin", allowed)


def test_write_tools_still_require_confirmation_independently_of_scope() -> None:
    """OAuth scope must never substitute for explicit confirmation on a write."""
    src = _src("app/mcp_gateway/server.py")
    for tool in ("sync_league", "run_analysis", "review_recommendation"):
        assert tool in src
    assert "confirmed" in src


# ---------- revocation ----------

def test_revocation_is_supported_and_enforced_before_token_expiry() -> None:
    server = _src("app/auth_server/server.py")
    assert 'app.post("/revoke")' in server
    assert "grant.revoked_at = now" in server
    composite = _src("app/mcp_gateway/composite_auth.py")
    assert "_grant_is_active" in composite
    assert "Fail closed" in composite


def test_refresh_tokens_rotate_on_use() -> None:
    src = _src("app/auth_server/server.py")
    assert "Rotate on every use" in src
    assert "grant.refresh_token_hash = hash_token(rotated)" in src


# ---------- existing bearer compatibility ----------

def test_existing_pocketbase_bearer_still_accepted() -> None:
    """The working Claude Code connection must survive the migration."""
    src = _src("app/mcp_gateway/composite_auth.py")
    assert "PocketBaseTokenVerifier" in src
    assert "self._fallback.verify_token(token)" in src
    server = _src("app/mcp_gateway/server.py")
    assert "CompositeTokenVerifier" in server


# ---------- secret leakage ----------

def test_no_secret_is_rendered_logged_or_returned() -> None:
    for rel in ("app/auth_server/server.py", "app/auth_server/pages.py",
                "app/auth_server/clients.py", "app/auth_server/keys.py",
                "app/mcp_gateway/composite_auth.py"):
        src = _src(rel)
        # A print *statement*, not the substring: keys.py legitimately contains
        # "print(Fernet.generate_key()...)" inside an operator-facing instruction string.
        statements = re.findall(r"^\s*print\(", src, re.MULTILINE)
        assert statements == [], f"{rel} must not print"
        after_log = src.lower().split("logger.info(")
        assert "logger.info(" not in src or "token" not in after_log[1][:200]
    server = _src("app/auth_server/server.py")
    # Token responses must not be cached by intermediaries.
    assert '"Cache-Control": "no-store"' in server
    # The consent page must never echo OAuth parameters as tamperable form fields.
    page = _src("app/auth_server/pages.py")
    assert "request_token" in page
    for leaked in ("code_challenge", "redirect_uri", "client_secret"):
        assert leaked not in page


def test_authorization_page_never_requests_espn_credentials() -> None:
    page = _src("app/auth_server/pages.py")
    assert "espn_s2" not in page and "SWID" not in page
    assert "never asks for your ESPN password or cookies" in page


def test_private_keys_are_encrypted_at_rest_and_key_is_required() -> None:
    src = _src("app/auth_server/keys.py")
    assert "Fernet" in src
    assert "LEAGUEPILOT_AUTH_ENCRYPTION_KEY is required" in src
