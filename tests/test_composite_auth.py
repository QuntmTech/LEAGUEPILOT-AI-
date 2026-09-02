"""Behavioral tests for the MCP gateway's composite token verifier.

The gateway must accept two kinds of bearer at once during the migration:

  1. OAuth access tokens minted by the new authorization server, and
  2. the existing PocketBase session bearer, which is what the owner's already-working
     Claude Code connection uses.

Breaking (2) would take down a live integration, so it is asserted explicitly here.

These tests mint *real* tokens from a real authorization server running under TestClient
and let the verifier fetch the real JWKS and real introspection endpoint over a shim that
forwards httpx calls into that app. Nothing about signing, verification or revocation is
mocked — only the network hop is.
"""

from __future__ import annotations

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from app.auth_server import clients as clients_mod
from app.auth_server import server as server_mod
from app.auth_server.settings import AuthServerSettings
from app.mcp_gateway import composite_auth as composite_mod
from app.mcp_gateway.composite_auth import CompositeTokenVerifier
from tests.test_auth_server_flow import (
    FakeAsyncClient,
    _authorize,
    _code_from,
    _consent,
    _exchange,
    _pkce,
    _pocketbase_ok,
    _register,
)

ISSUER = "https://auth.test.invalid"
RESOURCE = "https://mcp.test.invalid"
REDIRECT = "https://claude.ai/api/mcp/auth_callback"
INTROSPECTION_SECRET = "test-introspection-secret-value-0123456789"
STATIC_BEARER = "existing-claude-code-pocketbase-bearer"
PB_USER = "user0000000001x"


# --------------------------------------------------------------------------- harness


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"



@pytest.fixture
def auth(tmp_path, monkeypatch):
    """A real authorization server, reachable at ISSUER through the httpx shim."""
    monkeypatch.setenv("LEAGUEPILOT_AUTH_ENCRYPTION_KEY", Fernet.generate_key().decode())
    monkeypatch.setattr(server_mod.httpx, "AsyncClient", _ForwardingClient)
    monkeypatch.setattr(clients_mod.httpx, "AsyncClient", _ForwardingClient)
    FakeAsyncClient.routes = {
        ("POST", "https://pb.test.invalid/api/collections/users/auth-with-password"):
            _pocketbase_ok(),
    }
    FakeAsyncClient.calls = []
    server_mod._PENDING.clear()
    app = server_mod.create_app(
        AuthServerSettings(
            issuer_url=f"{ISSUER}/",
            resource_url=f"{RESOURCE}/",
            cloudpod_url="https://pb.test.invalid",
            database_url=f"sqlite:///{tmp_path/'auth.db'}",
            introspection_secret=INTROSPECTION_SECRET,
        authorization_code_ttl_seconds=60,
            access_token_ttl_seconds=300,
        )
    )
    with TestClient(app) as test_client:
        yield test_client


class _ForwardingClient(FakeAsyncClient):
    """One shim for both sides of the test.

    `composite_auth.httpx` and `server.httpx` are the same module object, so a single
    class has to serve the verifier's outbound calls *and* the authorization server's
    own PocketBase call. GETs aimed at the issuer are forwarded into the live app;
    everything else falls through to the route table the auth fixture registered.

    `offline` simulates only the authorization server being unreachable — PocketBase
    sign-in keeps working, which is the exact asymmetry the migration relies on.
    """

    target: TestClient | None = None
    offline: bool = False
    seen: list = []

    async def get(self, url, **kwargs):
        if url.startswith(ISSUER):
            _ForwardingClient.seen.append(url)
            if _ForwardingClient.offline:
                raise ConnectionError("authorization server unreachable")
            return _ForwardingClient.target.get(
                url[len(ISSUER):], headers=kwargs.get("headers") or {}
            )
        return await super().get(url, **kwargs)


class _FakeFallback:
    """Stands in for PocketBase. Accepts exactly one known static bearer."""

    def __init__(self):
        self.calls = []

    async def verify_token(self, token):
        from mcp.server.auth.provider import AccessToken

        self.calls.append(token)
        if token != STATIC_BEARER:
            return None
        return AccessToken(
            token=token,
            client_id="leaguepilot-pocketbase",
            scopes=["leaguepilot:read", "leaguepilot:write"],
            subject=PB_USER,
            claims={"sub": PB_USER},
        )


@pytest.fixture
def verifier(auth, monkeypatch):
    monkeypatch.setattr(composite_mod.httpx, "AsyncClient", _ForwardingClient)
    _ForwardingClient.target = auth
    _ForwardingClient.offline = False
    _ForwardingClient.seen = []
    v = CompositeTokenVerifier(
        cloudpod_url="https://pb.test.invalid",
        issuer_url=ISSUER,
        resource_url=RESOURCE,
        introspection_secret=INTROSPECTION_SECRET,
    )
    v._fallback = _FakeFallback()
    return v


def _mint(auth, scope="leaguepilot:read leaguepilot:write"):
    """Run a complete authorization code flow and return the token response body.

    Deliberately reuses the authorization-server test helpers rather than restating the
    flow, so a change to the real protocol surface cannot leave a stale copy here.
    """
    verifier, challenge = _pkce()
    client_id = _register(auth, scope=scope)
    page = _authorize(auth, client_id, challenge, scope=scope, resource=RESOURCE)
    assert page.status_code == 200, page.text
    code = _code_from(_consent(auth, page.text))
    exchanged = _exchange(auth, client_id, code, verifier, resource=RESOURCE)
    assert exchanged.status_code == 200, exchanged.text
    return exchanged.json()


# ------------------------------------------------- OAuth tokens are accepted


@pytest.mark.anyio
async def test_valid_oauth_token_is_accepted_with_subject_and_scopes(verifier, auth):
    body = _mint(auth)
    result = await verifier.verify_token(body["access_token"])
    assert result is not None
    assert result.subject == PB_USER
    assert set(result.scopes) == {"leaguepilot:read", "leaguepilot:write"}
    assert result.claims["sub"] == PB_USER


@pytest.mark.anyio
async def test_oauth_scopes_are_carried_through_not_widened(verifier, auth):
    body = _mint(auth, scope="leaguepilot:read")
    result = await verifier.verify_token(body["access_token"])
    assert result.scopes == ["leaguepilot:read"]
    assert "leaguepilot:write" not in result.scopes


@pytest.mark.anyio
async def test_oauth_token_never_reaches_pocketbase(verifier, auth):
    """A valid OAuth token must be settled locally, not replayed upstream."""
    body = _mint(auth)
    await verifier.verify_token(body["access_token"])
    assert verifier._fallback.calls == []


# ------------------------------------------ the existing static bearer still works


@pytest.mark.anyio
async def test_existing_pocketbase_bearer_still_authenticates(verifier):
    """Regression guard: the owner's live Claude Code connection uses this path."""
    result = await verifier.verify_token(STATIC_BEARER)
    assert result is not None
    assert result.subject == PB_USER
    assert result.client_id == "leaguepilot-pocketbase"


@pytest.mark.anyio
async def test_static_bearer_survives_an_authorization_server_outage(verifier):
    """An OAuth outage must degrade new sign-ins, never the existing connection."""
    _ForwardingClient.offline = True
    result = await verifier.verify_token(STATIC_BEARER)
    assert result is not None, "PocketBase bearers must not depend on the OAuth server"
    assert result.subject == PB_USER


@pytest.mark.anyio
async def test_unknown_bearer_is_rejected(verifier):
    assert await verifier.verify_token("not-a-valid-token-at-all") is None


@pytest.mark.anyio
@pytest.mark.parametrize("token", ["", "x" * 4097])
async def test_empty_and_oversized_tokens_are_rejected_without_network(verifier, token):
    _ForwardingClient.seen = []
    assert await verifier.verify_token(token) is None
    assert _ForwardingClient.seen == [], "must reject before making any request"
    assert verifier._fallback.calls == []


# ------------------------------------------------------- revocation is enforced


@pytest.mark.anyio
async def test_revoked_grant_stops_being_accepted_before_token_expiry(verifier, auth):
    """The JWT is still cryptographically valid and unexpired; revocation must win."""
    body = _mint(auth)
    access = body["access_token"]
    assert await verifier.verify_token(access) is not None

    assert auth.post("/revoke", data={"token": body["refresh_token"]}).status_code == 200

    verifier._jwks = None  # ensure no stale caching masks the result
    assert await verifier.verify_token(access) is None, "revoked grant must be refused"


@pytest.mark.anyio
async def test_introspection_failure_fails_closed(verifier, auth):
    """An unverifiable grant is treated as revoked, not as valid."""
    body = _mint(auth)
    assert await verifier.verify_token(body["access_token"]) is not None

    _ForwardingClient.offline = True
    assert await verifier.verify_token(body["access_token"]) is None


# ------------------------------------------------- forged and foreign tokens


@pytest.mark.anyio
async def test_token_signed_by_a_different_key_is_rejected(verifier, auth, tmp_path,
                                                            monkeypatch):
    """A token from another issuer's keypair must not validate against our JWKS."""
    from authlib.jose import JsonWebKey, jwt

    key = JsonWebKey.generate_key("RSA", 2048, is_private=True)
    forged = jwt.encode(
        {"alg": "RS256", "kid": "attacker"},
        {
            "iss": ISSUER,
            "sub": PB_USER,
            "aud": RESOURCE,
            "gid": "anything",
            "scope": "leaguepilot:write",
            "exp": 4102444800,
        },
        key,
    ).decode()
    _mint(auth)  # ensure a real signing key exists to compare against
    assert await verifier.verify_token(forged) is None


@pytest.mark.anyio
async def test_token_for_a_different_audience_is_rejected(verifier, auth, monkeypatch):
    """A token minted for another resource server must not unlock this one."""
    body = _mint(auth)
    other = CompositeTokenVerifier(
        cloudpod_url="https://pb.test.invalid",
        issuer_url=ISSUER,
        resource_url="https://someone-elses-mcp.invalid",
        introspection_secret=INTROSPECTION_SECRET,
    )
    other._fallback = _FakeFallback()
    assert await other.verify_token(body["access_token"]) is None


@pytest.mark.anyio
async def test_unparseable_jwt_falls_through_to_pocketbase(verifier, auth):
    """Garbage that merely looks like a JWT must not 500 — it degrades to the fallback."""
    _mint(auth)
    assert await verifier.verify_token("aaa.bbb.ccc") is None
    assert verifier._fallback.calls == ["aaa.bbb.ccc"]


@pytest.mark.anyio
async def test_missing_jwks_degrades_to_pocketbase_rather_than_erroring(verifier):
    _ForwardingClient.offline = True
    assert await verifier.verify_token("some-pocketbase-looking-token") is None
    assert verifier._fallback.calls == ["some-pocketbase-looking-token"]


# ------------------------------------------- introspection service authentication


@pytest.mark.anyio
async def test_verifier_presents_the_service_credential_to_introspection(verifier, auth):
    body = _mint(auth)
    assert await verifier.verify_token(body["access_token"]) is not None
    assert any("/introspect/grant/" in url for url in _ForwardingClient.seen)


@pytest.mark.anyio
async def test_missing_service_credential_fails_closed(auth, monkeypatch):
    """No credential must mean no OAuth tokens accepted — never blanket acceptance."""
    monkeypatch.setattr(composite_mod.httpx, "AsyncClient", _ForwardingClient)
    _ForwardingClient.target = auth
    _ForwardingClient.offline = False
    body = _mint(auth)

    v = CompositeTokenVerifier(
        cloudpod_url="https://pb.test.invalid",
        issuer_url=ISSUER,
        resource_url=RESOURCE,
        introspection_secret=None,
    )
    v._fallback = _FakeFallback()
    assert await v.verify_token(body["access_token"]) is None


@pytest.mark.anyio
async def test_invalid_service_credential_fails_closed(auth, monkeypatch):
    monkeypatch.setattr(composite_mod.httpx, "AsyncClient", _ForwardingClient)
    _ForwardingClient.target = auth
    _ForwardingClient.offline = False
    body = _mint(auth)

    v = CompositeTokenVerifier(
        cloudpod_url="https://pb.test.invalid",
        issuer_url=ISSUER,
        resource_url=RESOURCE,
        introspection_secret="wrong-secret-that-is-long-enough-1234",
    )
    v._fallback = _FakeFallback()
    assert await v.verify_token(body["access_token"]) is None, (
        "a rejected service credential must deny the token, not pass it through"
    )


@pytest.mark.anyio
async def test_a_rejected_service_credential_does_not_fall_through_to_pocketbase(auth,
                                                                                monkeypatch):
    """An OAuth token that fails introspection must be denied outright — not retried as
    if it were a PocketBase bearer, which would hand the decision to a different system."""
    monkeypatch.setattr(composite_mod.httpx, "AsyncClient", _ForwardingClient)
    _ForwardingClient.target = auth
    _ForwardingClient.offline = False
    body = _mint(auth)

    v = CompositeTokenVerifier(
        cloudpod_url="https://pb.test.invalid",
        issuer_url=ISSUER,
        resource_url=RESOURCE,
        introspection_secret="wrong-secret-that-is-long-enough-1234",
    )
    v._fallback = _FakeFallback()
    assert await v.verify_token(body["access_token"]) is None
    assert v._fallback.calls == []


@pytest.mark.anyio
async def test_static_bearer_unaffected_by_a_bad_service_credential(auth, monkeypatch):
    """Introspection misconfiguration must not touch the existing Claude Code path."""
    monkeypatch.setattr(composite_mod.httpx, "AsyncClient", _ForwardingClient)
    _ForwardingClient.target = auth
    _ForwardingClient.offline = False

    v = CompositeTokenVerifier(
        cloudpod_url="https://pb.test.invalid",
        issuer_url=ISSUER,
        resource_url=RESOURCE,
        introspection_secret=None,
    )
    v._fallback = _FakeFallback()
    result = await v.verify_token(STATIC_BEARER)
    assert result is not None and result.subject == PB_USER


@pytest.mark.anyio
async def test_internal_url_is_used_for_jwks_and_introspection_not_the_public_issuer(auth,
                                                                                     monkeypatch):
    """The issuer stays the public identity; the traffic goes over the private origin."""
    internal = "https://auth-internal.test.invalid"

    class _InternalOnly(_ForwardingClient):
        async def get(self, url, **kwargs):
            if url.startswith(internal):
                _ForwardingClient.seen.append(url)
                return _ForwardingClient.target.get(url[len(internal):],
                                                    headers=kwargs.get("headers") or {})
            if url.startswith(ISSUER):
                raise AssertionError(f"public issuer must not be called internally: {url}")
            return await FakeAsyncClient.get(self, url, **kwargs)

    monkeypatch.setattr(composite_mod.httpx, "AsyncClient", _InternalOnly)
    _ForwardingClient.target = auth
    _ForwardingClient.offline = False
    _ForwardingClient.seen = []
    body = _mint(auth)

    v = CompositeTokenVerifier(
        cloudpod_url="https://pb.test.invalid",
        issuer_url=ISSUER,
        resource_url=RESOURCE,
        internal_auth_url=internal,
        introspection_secret=INTROSPECTION_SECRET,
    )
    v._fallback = _FakeFallback()
    result = await v.verify_token(body["access_token"])
    assert result is not None, "token minted by the public issuer must still validate"
    assert any(u.startswith(f"{internal}/.well-known/jwks.json")
               for u in _ForwardingClient.seen)
    assert any(u.startswith(f"{internal}/introspect/grant/") for u in _ForwardingClient.seen)
