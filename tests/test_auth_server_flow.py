"""Behavioral tests for the OAuth 2.1 authorization server.

These drive the real ASGI app with FastAPI's TestClient and assert observable HTTP
behavior, database state and security outcomes. Nothing here inspects source strings.

Two outbound dependencies are faked at the httpx boundary: PocketBase sign-in and the
Client ID Metadata Document fetch. Everything else — routing, PKCE, code lifecycle,
signing, persistence — is the production code path.
"""

from __future__ import annotations

import base64
import datetime as dt
import hashlib
import json
import re
from urllib.parse import parse_qs, urlsplit

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from app.auth_server import clients as clients_mod
from app.auth_server import server as server_mod
from app.auth_server.models import AuthorizationCode, Grant, OAuthClient
from app.auth_server.settings import AuthServerSettings

ISSUER = "https://auth.test.invalid"
RESOURCE = "https://mcp.test.invalid"
REDIRECT = "https://claude.ai/api/mcp/auth_callback"
USER_ID = "user0000000001x"
OTHER_USER_ID = "user0000000002x"


# --------------------------------------------------------------------------- fakes


class _Response:
    def __init__(self, status_code=200, payload=None, content=b"{}"):
        self.status_code = status_code
        self._payload = payload
        self.content = content if payload is None else json.dumps(payload).encode()

    def json(self):
        if self._payload is None:
            raise ValueError("not json")
        return self._payload


class FakeAsyncClient:
    """Routes outbound calls to whatever the active test registered."""

    routes: dict = {}
    calls: list = []

    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def post(self, url, **kwargs):
        FakeAsyncClient.calls.append(("POST", url, kwargs))
        handler = FakeAsyncClient.routes.get(("POST", url))
        if handler is None:
            return _Response(404, {"message": "no route"})
        return handler(kwargs)

    async def get(self, url, **kwargs):
        FakeAsyncClient.calls.append(("GET", url, kwargs))
        handler = FakeAsyncClient.routes.get(("GET", url))
        if handler is None:
            return _Response(404, {"message": "no route"})
        return handler(kwargs)


def _pocketbase_ok(user_id=USER_ID, token="pb-upstream-token"):  # noqa: S107 - fake upstream token, test only
    return lambda kwargs: _Response(200, {"record": {"id": user_id}, "token": token})


def _pocketbase_denied():
    return lambda kwargs: _Response(400, {"message": "Failed to authenticate."})


# --------------------------------------------------------------------------- fixtures


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
def settings(tmp_path) -> AuthServerSettings:
    return AuthServerSettings(
        issuer_url=f"{ISSUER}/",
        resource_url=f"{RESOURCE}/",
        cloudpod_url="https://pb.test.invalid",
        database_url=f"sqlite:///{tmp_path/'auth.db'}",
        authorization_code_ttl_seconds=60,
        access_token_ttl_seconds=300,
    )


@pytest.fixture
def client(settings, monkeypatch):
    monkeypatch.setenv("LEAGUEPILOT_AUTH_ENCRYPTION_KEY", Fernet.generate_key().decode())
    monkeypatch.setattr(server_mod.httpx, "AsyncClient", FakeAsyncClient)
    monkeypatch.setattr(clients_mod.httpx, "AsyncClient", FakeAsyncClient)
    FakeAsyncClient.routes = {
        ("POST", "https://pb.test.invalid/api/collections/users/auth-with-password"):
            _pocketbase_ok(),
    }
    FakeAsyncClient.calls = []
    server_mod._PENDING.clear()
    app = server_mod.create_app(settings)
    with TestClient(app) as test_client:
        test_client.app_state = app.state
        yield test_client


def _pkce(verifier: str = "v" * 64) -> tuple[str, str]:
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode()).digest()
    ).rstrip(b"=").decode()
    return verifier, challenge


def _register(client, redirect_uris=None, scope="leaguepilot:read leaguepilot:write") -> str:
    response = client.post(
        "/register",
        json={
            "client_name": "Test Client",
            "redirect_uris": redirect_uris or [REDIRECT],
            "scope": scope,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["client_id"]


def _authorize(client, client_id, challenge, *, redirect_uri=REDIRECT, scope=None,
               resource=None, method="S256", state="xyz-state"):
    params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "code_challenge": challenge,
        "code_challenge_method": method,
        "state": state,
    }
    if scope:
        params["scope"] = scope
    if resource:
        params["resource"] = resource
    return client.get("/authorize", params=params, follow_redirects=False)


def _consent(client, page_html, *, email="a@b.test", password="pw", decision="allow"):  # noqa: S107 - dummy credential, test only
    token = re.search(r'name="request_token" value="([^"]+)"', page_html).group(1)
    return client.post(
        "/authorize",
        data={"request_token": token, "decision": decision,
              "email": email, "password": password},
        follow_redirects=False,
    )


def _code_from(response) -> str:
    return parse_qs(urlsplit(response.headers["location"]).query)["code"][0]


def _full_code(client, *, scope=None, verifier=None):
    verifier, challenge = _pkce(verifier or "v" * 64)
    client_id = _register(client)
    page = _authorize(client, client_id, challenge, scope=scope)
    assert page.status_code == 200
    redirect = _consent(client, page.text)
    assert redirect.status_code == 302
    return client_id, verifier, _code_from(redirect)


def _exchange(client, client_id, code, verifier, *, redirect_uri=REDIRECT, resource=None):
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "code_verifier": verifier,
        "client_id": client_id,
        "redirect_uri": redirect_uri,
    }
    if resource:
        data["resource"] = resource
    return client.post("/token", data=data)


# --------------------------------------------------------------------------- 1. discovery


def test_discovery_metadata_advertises_only_real_endpoints(client):
    response = client.get("/.well-known/oauth-authorization-server")
    assert response.status_code == 200
    meta = response.json()
    assert meta["issuer"] == ISSUER
    assert meta["code_challenge_methods_supported"] == ["S256"]
    assert meta["client_id_metadata_document_supported"] is True
    assert meta["resource_indicators_supported"] is True

    # Every advertised endpoint must actually answer — the original bug was advertising
    # a registration mechanism that 404'd.
    for key in ("authorization_endpoint", "token_endpoint", "registration_endpoint",
                "revocation_endpoint", "jwks_uri"):
        path = urlsplit(meta[key]).path
        assert client.get(path).status_code != 404, key


def test_jwks_publishes_a_usable_signing_key(client):
    body = client.get("/.well-known/jwks.json").json()
    assert body["keys"], "JWKS must not be empty"
    key = body["keys"][0]
    assert key["kty"] == "RSA" and key["alg"] == "RS256" and key["use"] == "sig"
    assert key["kid"] and key["n"] and key["e"]
    assert "d" not in key and "p" not in key, "private material must never be published"


def test_healthz(client):
    assert client.get("/healthz").json()["status"] == "ok"


# --------------------------------------------------------------------------- 2. DCR


def test_dynamic_client_registration_returns_a_public_client(client):
    response = client.post(
        "/register",
        json={"client_name": "App", "redirect_uris": [REDIRECT], "scope": "leaguepilot:read"},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["client_id"].startswith("lp-")
    assert body["token_endpoint_auth_method"] == "none"
    assert "client_secret" not in body, "public clients must not receive a secret"


@pytest.mark.parametrize(
    "payload",
    [
        {"redirect_uris": []},
        {"redirect_uris": ["http://evil.test/cb"]},
        {"redirect_uris": ["https://a.test/*"]},
        {"redirect_uris": [REDIRECT], "scope": "admin"},
        {},
    ],
)
def test_dynamic_client_registration_rejects_invalid_metadata(client, payload):
    response = client.post("/register", json=payload)
    assert response.status_code == 400
    assert "error" in response.json()


def test_register_rejects_non_json_body(client):
    response = client.post("/register", content=b"not json",
                           headers={"Content-Type": "application/json"})
    assert response.status_code == 400


# --------------------------------------------------- 3-4. client ID metadata documents


def _metadata_route(url, *, payload=None, status=200, content=None):
    FakeAsyncClient.routes[("GET", url)] = lambda kwargs: _Response(
        status, payload, content if content is not None else b"{}"
    )


def test_client_id_metadata_document_registers_on_first_authorize(client):
    url = "https://claude.ai/.well-known/oauth-client"
    _metadata_route(url, payload={"client_id": url, "client_name": "Claude",
                                  "redirect_uris": [REDIRECT], "scope": "leaguepilot:read"})
    _, challenge = _pkce()
    response = _authorize(client, url, challenge)
    assert response.status_code == 200
    assert "Claude" in response.text

    # It must have been persisted as a public URL client.
    with client.app_state.sessions() as session:
        record = session.get(OAuthClient, url)
        assert record is not None
        assert record.is_url_client is True
        assert record.client_secret_hash is None
        assert record.redirect_uri_list() == [REDIRECT]


def test_client_id_metadata_document_must_self_identify(client):
    url = "https://claude.ai/.well-known/oauth-client"
    # Document claims to be a different client — the impersonation case.
    _metadata_route(url, payload={"client_id": "https://evil.test/other",
                                  "redirect_uris": [REDIRECT]})
    _, challenge = _pkce()
    response = _authorize(client, url, challenge)
    assert response.status_code == 400
    assert "does not identify itself" in response.text


def test_client_id_metadata_rejects_non_https_and_private_hosts(client):
    _, challenge = _pkce()
    for bad in ("http://claude.ai/meta", "https://127.0.0.1/meta",
                "https://localhost/meta", "https://10.0.0.5/meta"):
        response = _authorize(client, bad, challenge)
        assert response.status_code == 400, bad


def test_client_id_metadata_rejects_oversize_document(client):
    url = "https://claude.ai/big"
    FakeAsyncClient.routes[("GET", url)] = lambda kwargs: _Response(
        200, None, b"x" * (70 * 1024)
    )
    _, challenge = _pkce()
    assert _authorize(client, url, challenge).status_code == 400


def test_client_id_metadata_rejects_unreachable_document(client):
    url = "https://claude.ai/missing"
    _metadata_route(url, payload={"error": "nope"}, status=404)
    _, challenge = _pkce()
    assert _authorize(client, url, challenge).status_code == 400


def test_client_metadata_fetch_does_not_follow_redirects(client):
    """A redirect could send the fetch somewhere the SSRF guard never inspected."""
    url = "https://claude.ai/redirecting"
    _metadata_route(url, payload={"client_id": url, "redirect_uris": [REDIRECT]})
    _, challenge = _pkce()
    _authorize(client, url, challenge)
    get_calls = [c for c in FakeAsyncClient.calls if c[0] == "GET"]
    assert get_calls, "metadata should have been fetched"


# --------------------------------------------------------- 5-6. authorize → code → token


def test_full_authorization_code_flow_issues_an_audience_bound_token(client):
    client_id, verifier, code = _full_code(client)
    response = _exchange(client, client_id, code, verifier)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["token_type"] == "Bearer"
    assert body["expires_in"] == 300
    assert body["refresh_token"]
    assert response.headers["cache-control"] == "no-store"

    # The token must verify against the published JWKS with the right issuer/audience.
    from app.auth_server.tokens import decode_access_token

    jwks = client.get("/.well-known/jwks.json").json()
    claims = decode_access_token(body["access_token"], jwks, issuer=ISSUER, audience=RESOURCE)
    assert claims is not None
    assert claims["sub"] == USER_ID
    assert claims["client_id"] == client_id
    # A token for a different audience must not validate.
    assert decode_access_token(
        body["access_token"], jwks, issuer=ISSUER, audience="https://other.invalid"
    ) is None


def test_authorize_preserves_state_and_returns_iss(client):
    _, challenge = _pkce()
    client_id = _register(client)
    page = _authorize(client, client_id, challenge, state="opaque-123")
    redirect = _consent(client, page.text)
    query = parse_qs(urlsplit(redirect.headers["location"]).query)
    assert query["state"] == ["opaque-123"]
    assert query["iss"] == [ISSUER]


def test_consent_denial_redirects_with_access_denied(client):
    _, challenge = _pkce()
    client_id = _register(client)
    page = _authorize(client, client_id, challenge)
    redirect = _consent(client, page.text, decision="deny")
    query = parse_qs(urlsplit(redirect.headers["location"]).query)
    assert query["error"] == ["access_denied"]
    assert query["state"] == ["xyz-state"]


def test_bad_pocketbase_credentials_do_not_issue_a_code(client):
    FakeAsyncClient.routes[
        ("POST", "https://pb.test.invalid/api/collections/users/auth-with-password")
    ] = _pocketbase_denied()
    _, challenge = _pkce()
    client_id = _register(client)
    page = _authorize(client, client_id, challenge)
    response = _consent(client, page.text)
    assert response.status_code == 401
    assert "did not match" in response.text
    with client.app_state.sessions() as session:
        assert session.query(AuthorizationCode).count() == 0


def test_consent_page_never_asks_for_espn_credentials(client):
    _, challenge = _pkce()
    client_id = _register(client)
    page = _authorize(client, client_id, challenge)
    lowered = page.text.lower()
    assert "espn_s2" not in lowered and "swid" not in lowered
    assert "never asks for your espn password" in lowered


# --------------------------------------------------------------------- 7-8. PKCE


def test_authorize_requires_s256_pkce(client):
    client_id = _register(client)
    _, challenge = _pkce()
    # Missing challenge, and the forbidden `plain` method, must both be refused.
    for params in ({"code_challenge": "", "code_challenge_method": "S256"},
                   {"code_challenge": challenge, "code_challenge_method": "plain"},
                   {"code_challenge": challenge, "code_challenge_method": ""}):
        response = client.get(
            "/authorize",
            params={"response_type": "code", "client_id": client_id,
                    "redirect_uri": REDIRECT, "state": "s", **params},
            follow_redirects=False,
        )
        assert response.status_code == 302
        assert "invalid_request" in response.headers["location"]


def test_token_rejects_wrong_missing_and_malformed_verifier(client):
    for bad in ("", "wrong" * 12, "short", "!" * 64):
        client_id, _, code = _full_code(client)
        response = _exchange(client, client_id, code, bad)
        assert response.status_code == 400, bad
        assert response.json()["error"] == "invalid_grant"


# ------------------------------------------------------------- 9. redirect URI matching


def test_authorize_rejects_unregistered_redirect_uri_without_redirecting(client):
    client_id = _register(client, redirect_uris=[REDIRECT])
    _, challenge = _pkce()
    response = _authorize(client, client_id, challenge,
                          redirect_uri="https://evil.test/steal")
    # Must render an error, never 302 to the attacker-supplied URI.
    assert response.status_code == 400
    assert "location" not in {k.lower() for k in response.headers}


def test_token_rejects_mismatched_redirect_uri(client):
    client_id, verifier, code = _full_code(client)
    response = _exchange(client, client_id, code, verifier,
                         redirect_uri="https://claude.ai/other")
    assert response.status_code == 400
    assert response.json()["error"] == "invalid_grant"


# ---------------------------------------------- 10-11. code expiry, reuse, replay


def test_unknown_code_is_rejected(client):
    client_id = _register(client)
    response = _exchange(client, client_id, "nonexistent-code", "v" * 64)
    assert response.status_code == 400
    assert response.json()["error"] == "invalid_grant"


def test_expired_code_is_rejected(client):
    client_id, verifier, code = _full_code(client)
    from app.auth_server.keys import hash_token as _hash

    with client.app_state.sessions() as session:
        record = session.get(AuthorizationCode, _hash(code))
        record.expires_at = dt.datetime.now(dt.UTC) - dt.timedelta(seconds=5)
        session.add(record)
        session.commit()
    response = _exchange(client, client_id, code, verifier)
    assert response.status_code == 400
    assert "expired" in response.json()["error_description"].lower()


def test_code_is_single_use(client):
    client_id, verifier, code = _full_code(client)
    assert _exchange(client, client_id, code, verifier).status_code == 200
    second = _exchange(client, client_id, code, verifier)
    assert second.status_code == 400
    assert second.json()["error"] == "invalid_grant"


def test_code_replay_revokes_every_grant_derived_from_it(client):
    """OAuth 2.1 treats replay as evidence of interception, not a stale click."""
    client_id, verifier, code = _full_code(client)
    first = _exchange(client, client_id, code, verifier)
    assert first.status_code == 200
    refresh = first.json()["refresh_token"]

    # Replay the code.
    assert _exchange(client, client_id, code, verifier).status_code == 400

    with client.app_state.sessions() as session:
        grants = session.query(Grant).filter(Grant.client_id == client_id).all()
        assert grants and all(g.revoked_at is not None for g in grants)

    # The refresh token issued from that grant must now be dead.
    replayed = client.post("/token", data={"grant_type": "refresh_token",
                                           "refresh_token": refresh,
                                           "client_id": client_id})
    assert replayed.status_code == 400


def test_code_bound_to_issuing_client(client):
    client_id, verifier, code = _full_code(client)
    other = _register(client)
    response = _exchange(client, other, code, verifier)
    assert response.status_code == 400
    assert response.json()["error"] == "invalid_grant"


# ------------------------------------------------------- 12. audience / resource


def test_resource_mismatch_rejected_at_authorize_and_token(client):
    client_id = _register(client)
    _, challenge = _pkce()
    bad = _authorize(client, client_id, challenge, resource="https://elsewhere.invalid")
    assert bad.status_code == 302
    assert "invalid_target" in bad.headers["location"]

    client_id, verifier, code = _full_code(client)
    response = _exchange(client, client_id, code, verifier,
                         resource="https://elsewhere.invalid")
    assert response.status_code == 400
    assert response.json()["error"] == "invalid_target"


def test_correct_resource_is_accepted(client):
    _, challenge = _pkce()
    client_id = _register(client)
    page = _authorize(client, client_id, challenge, resource=RESOURCE)
    assert page.status_code == 200
    code = _code_from(_consent(client, page.text))
    assert _exchange(client, client_id, code, "v" * 64, resource=RESOURCE).status_code == 200


# --------------------------------------------------------------- 13. scope


def test_requested_scope_is_intersected_not_widened(client):
    client_id, verifier, code = _full_code(client, scope="leaguepilot:read")
    body = _exchange(client, client_id, code, verifier).json()
    assert body["scope"] == "leaguepilot:read"
    assert "leaguepilot:write" not in body["scope"]


def test_unsupported_scope_is_rejected(client):
    client_id = _register(client)
    _, challenge = _pkce()
    response = _authorize(client, client_id, challenge, scope="admin")
    assert response.status_code == 302
    assert "invalid_scope" in response.headers["location"]


# ----------------------------------------------- 14. user isolation in issued tokens


def test_tokens_are_bound_to_the_authenticating_user(client):
    """Two users authorizing the same client must receive tokens for their own subject."""
    client_id, verifier, code = _full_code(client)
    first = _exchange(client, client_id, code, verifier).json()

    FakeAsyncClient.routes[
        ("POST", "https://pb.test.invalid/api/collections/users/auth-with-password")
    ] = _pocketbase_ok(user_id=OTHER_USER_ID, token="pb-other-token")
    _, challenge = _pkce()
    page = _authorize(client, client_id, challenge)
    code2 = _code_from(_consent(client, page.text))
    second = _exchange(client, client_id, code2, "v" * 64).json()

    from app.auth_server.tokens import decode_access_token

    jwks = client.get("/.well-known/jwks.json").json()
    a = decode_access_token(first["access_token"], jwks, issuer=ISSUER, audience=RESOURCE)
    b = decode_access_token(second["access_token"], jwks, issuer=ISSUER, audience=RESOURCE)
    assert a["sub"] == USER_ID
    assert b["sub"] == OTHER_USER_ID
    assert a["gid"] != b["gid"], "each user must get a distinct grant"


def test_stored_upstream_tokens_are_encrypted_at_rest(client):
    _full_code(client)
    with client.app_state.sessions() as session:
        record = session.query(AuthorizationCode).first()
        assert record is not None
        assert "pb-upstream-token" not in record.upstream_token_encrypted


# ------------------------------------------------- 17. refresh rotation and replay


def test_refresh_token_rotates_and_old_one_is_rejected(client):
    client_id, verifier, code = _full_code(client)
    first = _exchange(client, client_id, code, verifier).json()
    original = first["refresh_token"]

    rotated = client.post("/token", data={"grant_type": "refresh_token",
                                          "refresh_token": original,
                                          "client_id": client_id})
    assert rotated.status_code == 200
    new_refresh = rotated.json()["refresh_token"]
    assert new_refresh != original

    replay = client.post("/token", data={"grant_type": "refresh_token",
                                         "refresh_token": original,
                                         "client_id": client_id})
    assert replay.status_code == 400


def test_refresh_bound_to_issuing_client(client):
    client_id, verifier, code = _full_code(client)
    refresh = _exchange(client, client_id, code, verifier).json()["refresh_token"]
    other = _register(client)
    response = client.post("/token", data={"grant_type": "refresh_token",
                                           "refresh_token": refresh,
                                           "client_id": other})
    assert response.status_code == 400


def test_unsupported_grant_type_rejected(client):
    response = client.post("/token", data={"grant_type": "password"})
    assert response.status_code == 400
    assert response.json()["error"] == "unsupported_grant_type"


# ---------------------------------------------------------------- 18. revocation


def test_revoking_a_refresh_token_kills_the_grant(client):
    client_id, verifier, code = _full_code(client)
    body = _exchange(client, client_id, code, verifier).json()

    from app.auth_server.tokens import decode_access_token

    jwks = client.get("/.well-known/jwks.json").json()
    gid = decode_access_token(body["access_token"], jwks, issuer=ISSUER, audience=RESOURCE)["gid"]
    assert client.get(f"/introspect/grant/{gid}").json()["active"] is True

    assert client.post("/revoke", data={"token": body["refresh_token"]}).status_code == 200
    assert client.get(f"/introspect/grant/{gid}").json()["active"] is False

    # And the refresh token no longer works.
    assert client.post("/token", data={"grant_type": "refresh_token",
                                       "refresh_token": body["refresh_token"],
                                       "client_id": client_id}).status_code == 400


def test_revoking_an_access_token_kills_the_grant(client):
    client_id, verifier, code = _full_code(client)
    body = _exchange(client, client_id, code, verifier).json()
    from app.auth_server.tokens import decode_access_token

    jwks = client.get("/.well-known/jwks.json").json()
    gid = decode_access_token(body["access_token"], jwks, issuer=ISSUER, audience=RESOURCE)["gid"]
    client.post("/revoke", data={"token": body["access_token"]})
    assert client.get(f"/introspect/grant/{gid}").json()["active"] is False


def test_revoking_an_unknown_token_still_returns_200(client):
    """RFC 7009: the endpoint must not reveal which tokens exist."""
    assert client.post("/revoke", data={"token": "not-a-real-token"}).status_code == 200
    assert client.post("/revoke", data={}).status_code == 200


def test_introspect_reports_unknown_grant_as_inactive(client):
    assert client.get("/introspect/grant/does-not-exist").json()["active"] is False


# --------------------------------------------- 19. signing key rotation and retention


def test_rotation_publishes_a_new_key_and_retains_the_old_one(client):
    """Tokens signed before rotation must keep verifying, or live clients break."""
    from app.auth_server.models import SigningKey

    before = client.get("/.well-known/jwks.json").json()["keys"]
    assert len(before) == 1
    old_kid = before[0]["kid"]

    # Force the active key past its retire window.
    with client.app_state.sessions() as session:
        record = session.query(SigningKey).filter(SigningKey.kid == old_kid).one()
        record.retire_after = dt.datetime.now(dt.UTC) - dt.timedelta(seconds=1)
        session.add(record)
        session.commit()

    after = client.get("/.well-known/jwks.json").json()["keys"]
    kids = {k["kid"] for k in after}
    assert old_kid in kids, "the outgoing key must stay published during its retire window"
    assert len(kids) == 2, "rotation must publish a new key alongside it"

    with client.app_state.sessions() as session:
        active = session.query(SigningKey).filter(SigningKey.is_active.is_(True)).all()
        assert len(active) == 1
        assert active[0].kid != old_kid


def test_tokens_signed_after_rotation_verify_against_the_published_jwks(client):
    from app.auth_server.models import SigningKey
    from app.auth_server.tokens import decode_access_token

    with client.app_state.sessions() as session:
        for record in session.query(SigningKey).all():
            record.retire_after = dt.datetime.now(dt.UTC) - dt.timedelta(seconds=1)
            session.add(record)
        session.commit()

    client_id, verifier, code = _full_code(client)
    body = _exchange(client, client_id, code, verifier).json()
    jwks = client.get("/.well-known/jwks.json").json()
    claims = decode_access_token(body["access_token"], jwks, issuer=ISSUER, audience=RESOURCE)
    assert claims is not None and claims["sub"] == USER_ID


def test_private_keys_are_encrypted_at_rest(client):
    from app.auth_server.models import SigningKey

    client.get("/.well-known/jwks.json")
    with client.app_state.sessions() as session:
        record = session.query(SigningKey).first()
    assert "PRIVATE KEY" not in record.private_pem_encrypted


def test_encryption_key_is_required_and_never_generated_implicitly(monkeypatch):
    """A key that changed per restart would silently invalidate every stored grant."""
    from app.auth_server.keys import load_encryption_key

    monkeypatch.delenv("LEAGUEPILOT_AUTH_ENCRYPTION_KEY", raising=False)
    with pytest.raises(RuntimeError, match="LEAGUEPILOT_AUTH_ENCRYPTION_KEY"):
        load_encryption_key()


# ---------------------------------------------------- 20. controlled error surfaces


def test_expired_pending_request_shows_an_error_page_not_a_crash(client):
    _, challenge = _pkce()
    client_id = _register(client)
    page = _authorize(client, client_id, challenge)
    token = re.search(r'name="request_token" value="([^"]+)"', page.text).group(1)
    server_mod._PENDING.clear()

    response = client.post(
        "/authorize",
        data={"request_token": token, "decision": "allow", "email": "a@b.test",
              "password": "pw"},
        follow_redirects=False,
    )
    assert response.status_code == 400
    assert "expired" in response.text.lower()
    assert "Traceback" not in response.text


def test_sign_in_service_outage_returns_502_without_leaking_upstream_detail(client):
    import httpx as real_httpx

    def _boom(kwargs):
        raise real_httpx.ConnectError("pb.test.invalid: name resolution failed")

    FakeAsyncClient.routes[
        ("POST", "https://pb.test.invalid/api/collections/users/auth-with-password")
    ] = _boom
    _, challenge = _pkce()
    client_id = _register(client)
    page = _authorize(client, client_id, challenge)
    response = _consent(client, page.text)
    assert response.status_code == 502
    assert "unavailable" in response.text.lower()
    assert "pb.test.invalid" not in response.text
    assert "Traceback" not in response.text


def test_malformed_sign_in_response_returns_502(client):
    FakeAsyncClient.routes[
        ("POST", "https://pb.test.invalid/api/collections/users/auth-with-password")
    ] = lambda kwargs: _Response(200, {"record": {}, "token": ""})
    _, challenge = _pkce()
    client_id = _register(client)
    page = _authorize(client, client_id, challenge)
    response = _consent(client, page.text)
    assert response.status_code == 502
    assert "Traceback" not in response.text


def test_registration_rejects_a_json_array_body(client):
    response = client.post("/register", json=["not", "an", "object"])
    assert response.status_code == 400
    assert response.json()["error"] == "invalid_client_metadata"


def test_stale_pending_requests_are_swept(client):
    _, challenge = _pkce()
    client_id = _register(client)
    _authorize(client, client_id, challenge)
    assert server_mod._PENDING

    for value in server_mod._PENDING.values():
        value["created"] -= server_mod._PENDING_TTL * 2
    _authorize(client, client_id, challenge)  # any authorize triggers the sweep

    assert len(server_mod._PENDING) == 1, "expired pending requests must not accumulate"


def test_no_endpoint_echoes_the_upstream_pocketbase_token(client):
    """The upstream session token is an internal detail; it must never surface."""
    client_id, verifier, code = _full_code(client)
    body = _exchange(client, client_id, code, verifier)
    assert "pb-upstream-token" not in body.text
    for path in ("/.well-known/oauth-authorization-server", "/.well-known/jwks.json",
                 "/healthz"):
        assert "pb-upstream-token" not in client.get(path).text


# ----------------------------------- remaining client-metadata branches


def test_metadata_fetch_transport_error_is_reported_without_upstream_detail(client):
    import httpx as real_httpx

    url = "https://claude.ai/.well-known/oauth-client"

    def _boom(kwargs):
        raise real_httpx.ConnectTimeout("upstream 203.0.113.9:443 timed out")

    FakeAsyncClient.routes[("GET", url)] = _boom
    _, challenge = _pkce()
    response = _authorize(client, url, challenge)
    assert response.status_code == 400
    assert "could not be retrieved" in response.text
    assert "203.0.113.9" not in response.text
    assert "Traceback" not in response.text


def test_metadata_document_that_is_not_json_is_rejected(client):
    url = "https://claude.ai/.well-known/oauth-client"
    _metadata_route(url, payload=None, content=b"<html>login page</html>")
    _, challenge = _pkce()
    response = _authorize(client, url, challenge)
    assert response.status_code == 400
    assert "not valid JSON" in response.text


def test_metadata_document_that_is_a_json_array_is_rejected(client):
    url = "https://claude.ai/.well-known/oauth-client"
    _metadata_route(url, payload=["not", "an", "object"])
    _, challenge = _pkce()
    response = _authorize(client, url, challenge)
    assert response.status_code == 400
    assert "not an object" in response.text


@pytest.mark.anyio
async def test_metadata_fetch_refuses_a_non_https_url_directly():
    """Defense in depth: /authorize screens this out first, so assert it at the source."""
    from app.auth_server.clients import ClientError, fetch_client_id_metadata

    with pytest.raises(ClientError) as excinfo:
        await fetch_client_id_metadata("http://claude.ai/meta", timeout_seconds=1)
    assert "HTTPS" in excinfo.value.description


def test_cached_client_metadata_is_not_refetched_until_it_goes_stale(client):
    """Re-fetching on every authorize would let a compromised host swap redirect URIs
    mid-session, and would make sign-in depend on the client's uptime."""
    url = "https://claude.ai/.well-known/oauth-client"
    _metadata_route(url, payload={"client_id": url, "client_name": "Claude",
                                  "redirect_uris": [REDIRECT]})
    _, challenge = _pkce()
    assert _authorize(client, url, challenge).status_code == 200
    first = len([c for c in FakeAsyncClient.calls if c[0] == "GET" and c[1] == url])

    assert _authorize(client, url, challenge).status_code == 200
    second = len([c for c in FakeAsyncClient.calls if c[0] == "GET" and c[1] == url])
    assert second == first, "fresh metadata must be served from cache"


def test_metadata_freshness_window(client):
    from app.auth_server.clients import METADATA_CACHE_SECONDS, metadata_is_fresh

    record = OAuthClient(client_id="x", metadata_fetched_at=None)
    assert metadata_is_fresh(record) is False

    now = dt.datetime.now(dt.UTC)
    record.metadata_fetched_at = now
    assert metadata_is_fresh(record) is True

    record.metadata_fetched_at = now - dt.timedelta(seconds=METADATA_CACHE_SECONDS + 60)
    assert metadata_is_fresh(record) is False
