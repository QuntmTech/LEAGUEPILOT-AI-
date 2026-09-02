from __future__ import annotations

import datetime as dt
import json
import logging
import secrets
from urllib.parse import urlencode, urlsplit

import httpx
from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from app.auth_server import clients as client_lib
from app.auth_server import pages, tokens
from app.auth_server.keys import (
    KeyStore, hash_token, load_encryption_key, new_secret, verify_pkce,
)
from app.auth_server.models import AuthorizationCode, Grant, OAuthClient, build_session_factory
from app.auth_server.settings import AuthServerSettings

logger = logging.getLogger("leaguepilot.auth")

SUPPORTED_SCOPES = {"leaguepilot:read", "leaguepilot:write"}
# Pending authorization requests live server-side between GET and POST /authorize so the
# browser never carries tamperable OAuth parameters through the consent step.
_PENDING: dict[str, dict] = {}
_PENDING_TTL = dt.timedelta(minutes=10)


def _prune_pending() -> None:
    now = dt.datetime.now(dt.timezone.utc)
    for key, value in list(_PENDING.items()):
        if value["created"] + _PENDING_TTL < now:
            _PENDING.pop(key, None)


def _oauth_error(error: str, description: str, status: int = 400) -> JSONResponse:
    # Error bodies carry a code and a human string only — never the offending value, which
    # could echo a token or code back into a log or a browser history entry.
    return JSONResponse({"error": error, "error_description": description}, status_code=status)


def _redirect_error(redirect_uri: str, error: str, description: str, state: str | None) -> RedirectResponse:
    params = {"error": error, "error_description": description}
    if state:
        params["state"] = state
    joiner = "&" if urlsplit(redirect_uri).query else "?"
    return RedirectResponse(f"{redirect_uri}{joiner}{urlencode(params)}", status_code=302)


def create_app(settings: AuthServerSettings | None = None) -> FastAPI:
    resolved = settings or AuthServerSettings()
    sessions = build_session_factory(resolved.database_url)
    keys = KeyStore(sessions, load_encryption_key(), resolved.signing_key_ttl_seconds)
    app = FastAPI(title="LEAGUEPILOT Authorization Server", docs_url=None, redoc_url=None)
    app.state.settings = resolved
    app.state.sessions = sessions
    app.state.keys = keys

    # ---------- discovery ----------

    @app.get("/.well-known/oauth-authorization-server")
    async def authorization_server_metadata() -> JSONResponse:
        """RFC 8414 metadata.

        Every capability advertised here is implemented. Advertising a registration
        mechanism that then fails is exactly the defect this server was built to fix.
        """
        issuer = resolved.issuer
        return JSONResponse(
            {
                "issuer": issuer,
                "authorization_endpoint": f"{issuer}/authorize",
                "token_endpoint": f"{issuer}/token",
                "registration_endpoint": f"{issuer}/register",
                "revocation_endpoint": f"{issuer}/revoke",
                "jwks_uri": f"{issuer}/.well-known/jwks.json",
                "scopes_supported": sorted(SUPPORTED_SCOPES),
                "response_types_supported": ["code"],
                "grant_types_supported": ["authorization_code", "refresh_token"],
                "code_challenge_methods_supported": ["S256"],
                "token_endpoint_auth_methods_supported": ["none"],
                "revocation_endpoint_auth_methods_supported": ["none"],
                # Signals support for HTTPS Client ID Metadata Documents, which is how
                # Anthropic's hosted client metadata registers.
                "client_id_metadata_document_supported": True,
                "resource_indicators_supported": True,
                "authorization_response_iss_parameter_supported": True,
            }
        )

    @app.get("/.well-known/jwks.json")
    async def jwks() -> JSONResponse:
        return JSONResponse(keys.public_jwks())

    @app.get("/healthz")
    async def healthz() -> JSONResponse:
        return JSONResponse({"status": "ok", "service": "leaguepilot-auth", "issuer": resolved.issuer})

    # ---------- dynamic client registration ----------

    @app.post("/register")
    async def register(request: Request) -> JSONResponse:
        """RFC 7591 Dynamic Client Registration for clients without a metadata URL."""
        try:
            body = await request.json()
        except Exception:
            return _oauth_error("invalid_client_metadata", "Request body must be JSON.")
        if not isinstance(body, dict):
            return _oauth_error("invalid_client_metadata", "Request body must be a JSON object.")
        try:
            redirects = client_lib.validate_redirect_uris(list(body.get("redirect_uris") or []))
            scope = client_lib.normalize_scope(body.get("scope"), SUPPORTED_SCOPES)
        except client_lib.ClientError as exc:
            return _oauth_error(exc.error, exc.description)

        client_id = f"lp-{secrets.token_urlsafe(24)}"
        with sessions() as session:
            session.add(
                OAuthClient(
                    client_id=client_id,
                    client_name=str(body.get("client_name") or "")[:255],
                    redirect_uris="\n".join(redirects),
                    scope=scope,
                    token_endpoint_auth_method="none",
                    is_url_client=False,
                )
            )
            session.commit()
        # Public client: no secret is issued, so none can leak.
        return JSONResponse(
            {
                "client_id": client_id,
                "client_id_issued_at": int(dt.datetime.now(dt.timezone.utc).timestamp()),
                "redirect_uris": redirects,
                "scope": scope,
                "token_endpoint_auth_method": "none",
                "grant_types": ["authorization_code", "refresh_token"],
                "response_types": ["code"],
            },
            status_code=201,
        )

    # ---------- authorization ----------

    async def _resolve_client(client_id: str) -> OAuthClient:
        """Resolve either a registered client or an HTTPS Client ID Metadata Document."""
        with sessions() as session:
            existing = session.get(OAuthClient, client_id)
            if existing and (not existing.is_url_client or client_lib.metadata_is_fresh(existing)):
                session.expunge(existing)
                return existing
        if client_id.startswith("https://"):
            document = await client_lib.fetch_client_id_metadata(
                client_id, resolved.request_timeout_seconds
            )
            with sessions() as session:
                client = client_lib.upsert_url_client(session, client_id, document, SUPPORTED_SCOPES)
                session.commit()
                session.refresh(client)
                session.expunge(client)
                return client
        raise client_lib.ClientError("invalid_client", "Unknown client.")

    @app.get("/authorize")
    async def authorize(request: Request) -> HTMLResponse | RedirectResponse | JSONResponse:
        params = request.query_params
        client_id = params.get("client_id", "")
        redirect_uri = params.get("redirect_uri", "")
        state = params.get("state")
        challenge = params.get("code_challenge", "")
        method = params.get("code_challenge_method", "")
        resource = params.get("resource", "")

        if params.get("response_type") != "code":
            return HTMLResponse(pages.error_page("Only the authorization code flow is supported."), 400)
        try:
            client = await _resolve_client(client_id)
        except client_lib.ClientError as exc:
            return HTMLResponse(pages.error_page(exc.description), 400)

        # Exact match. Anything else and we must not redirect, because an attacker-supplied
        # URI is exactly how codes get exfiltrated.
        if redirect_uri not in client.redirect_uri_list():
            return HTMLResponse(pages.error_page("The redirect URI does not match this client's registration."), 400)

        # From here failures can safely redirect, since the URI is proven to be the client's.
        if method != "S256" or not challenge:
            return _redirect_error(redirect_uri, "invalid_request", "PKCE with S256 is required.", state)
        if resource and resource.rstrip("/") != resolved.resource:
            return _redirect_error(redirect_uri, "invalid_target", "Unsupported resource.", state)
        try:
            scope = client_lib.normalize_scope(params.get("scope") or client.scope, SUPPORTED_SCOPES)
        except client_lib.ClientError as exc:
            return _redirect_error(redirect_uri, exc.error, exc.description, state)

        _prune_pending()
        request_token = secrets.token_urlsafe(32)
        _PENDING[request_token] = {
            "client_id": client_id,
            "client_name": client.client_name,
            "redirect_uri": redirect_uri,
            "state": state,
            "scope": scope,
            "challenge": challenge,
            "method": method,
            "resource": resolved.resource,
            "created": dt.datetime.now(dt.timezone.utc),
        }
        return HTMLResponse(
            pages.login_page(
                request_token=request_token,
                client_name=client.client_name,
                scopes=scope.split(),
            )
        )

    @app.post("/authorize")
    async def authorize_submit(
        request_token: str = Form(...),
        decision: str = Form(...),
        email: str = Form(default=""),
        password: str = Form(default=""),
    ) -> HTMLResponse | RedirectResponse:
        _prune_pending()
        pending = _PENDING.get(request_token)
        if not pending:
            return HTMLResponse(pages.error_page("This authorization request expired. Start again."), 400)

        redirect_uri = pending["redirect_uri"]
        state = pending["state"]
        if decision != "allow":
            _PENDING.pop(request_token, None)
            return _redirect_error(redirect_uri, "access_denied", "The user cancelled.", state)

        # Authenticate against the existing LeaguePilot identity. ESPN credentials are
        # never requested or accepted here.
        try:
            async with httpx.AsyncClient(timeout=resolved.request_timeout_seconds) as http:
                response = await http.post(
                    f"{resolved.backend_url}/api/collections/users/auth-with-password",
                    json={"identity": email, "password": password},
                )
        except httpx.HTTPError:
            return HTMLResponse(pages.error_page("The sign-in service is unavailable."), 502)
        if response.status_code != 200:
            # Same message for unknown user and wrong password: no account enumeration.
            return HTMLResponse(
                pages.login_page(
                    request_token=request_token,
                    client_name=pending["client_name"],
                    scopes=pending["scope"].split(),
                    error="That email and password did not match.",
                ),
                401,
            )
        payload = response.json()
        subject = str(payload.get("record", {}).get("id") or "")
        upstream = str(payload.get("token") or "")
        if not subject or not upstream:
            return HTMLResponse(pages.error_page("The sign-in service returned an unexpected response."), 502)

        _PENDING.pop(request_token, None)
        code = new_secret(32)
        now = dt.datetime.now(dt.timezone.utc)
        with sessions() as session:
            session.add(
                AuthorizationCode(
                    code_hash=hash_token(code),
                    client_id=pending["client_id"],
                    subject=subject,
                    redirect_uri=redirect_uri,
                    scope=pending["scope"],
                    resource=pending["resource"],
                    code_challenge=pending["challenge"],
                    code_challenge_method=pending["method"],
                    upstream_token_encrypted=keys.encrypt(upstream),
                    expires_at=now + dt.timedelta(seconds=resolved.authorization_code_ttl_seconds),
                )
            )
            session.commit()

        params = {"code": code, "iss": resolved.issuer}
        if state:
            params["state"] = state
        joiner = "&" if urlsplit(redirect_uri).query else "?"
        return RedirectResponse(f"{redirect_uri}{joiner}{urlencode(params)}", status_code=302)

    # ---------- token ----------

    @app.post("/token")
    async def token(request: Request) -> JSONResponse:
        form = await request.form()
        grant_type = form.get("grant_type")
        if grant_type == "refresh_token":
            return await _refresh(form)
        if grant_type != "authorization_code":
            return _oauth_error("unsupported_grant_type", "Unsupported grant type.")

        code = str(form.get("code") or "")
        verifier = str(form.get("code_verifier") or "")
        client_id = str(form.get("client_id") or "")
        redirect_uri = str(form.get("redirect_uri") or "")
        resource = str(form.get("resource") or "")
        now = dt.datetime.now(dt.timezone.utc)

        with sessions() as session:
            record = session.get(AuthorizationCode, hash_token(code)) if code else None
            if record is None:
                return _oauth_error("invalid_grant", "The authorization code is invalid.")

            # Replay: reject AND revoke every grant already derived from this code.
            if record.used_at is not None:
                for grant in session.query(Grant).filter(Grant.subject == record.subject,
                                                         Grant.client_id == record.client_id,
                                                         Grant.revoked_at.is_(None)).all():
                    grant.revoked_at = now
                    session.add(grant)
                session.commit()
                logger.warning("authorization code replay detected; grants revoked")
                return _oauth_error("invalid_grant", "The authorization code is invalid.")

            if record.expires_at <= now:
                return _oauth_error("invalid_grant", "The authorization code has expired.")
            if record.client_id != client_id:
                return _oauth_error("invalid_grant", "The authorization code was issued to another client.")
            if record.redirect_uri != redirect_uri:
                return _oauth_error("invalid_grant", "The redirect URI does not match the authorization request.")
            if resource and resource.rstrip("/") != record.resource:
                return _oauth_error("invalid_target", "Unsupported resource.")
            if not verify_pkce(verifier, record.code_challenge, record.code_challenge_method):
                return _oauth_error("invalid_grant", "The PKCE verifier is invalid.")

            record.used_at = now
            session.add(record)

            grant_id = secrets.token_urlsafe(16)
            refresh = new_secret(32)
            session.add(
                Grant(
                    id=grant_id,
                    client_id=record.client_id,
                    subject=record.subject,
                    scope=record.scope,
                    resource=record.resource,
                    upstream_token_encrypted=record.upstream_token_encrypted,
                    refresh_token_hash=hash_token(refresh),
                    expires_at=now + dt.timedelta(seconds=resolved.refresh_token_ttl_seconds),
                )
            )
            session.commit()
            scope, subject = record.scope, record.subject

        kid, private_pem = keys.active_key()
        access = tokens.issue_access_token(
            private_pem=private_pem, kid=kid, issuer=resolved.issuer, subject=subject,
            audience=resolved.resource, client_id=client_id, scope=scope,
            grant_id=grant_id, ttl_seconds=resolved.access_token_ttl_seconds,
        )
        return JSONResponse(
            {
                "access_token": access,
                "token_type": "Bearer",
                "expires_in": resolved.access_token_ttl_seconds,
                "refresh_token": refresh,
                "scope": scope,
            },
            headers={"Cache-Control": "no-store", "Pragma": "no-cache"},
        )

    async def _refresh(form) -> JSONResponse:
        presented = str(form.get("refresh_token") or "")
        client_id = str(form.get("client_id") or "")
        now = dt.datetime.now(dt.timezone.utc)
        with sessions() as session:
            grant = (
                session.query(Grant)
                .filter(Grant.refresh_token_hash == hash_token(presented))
                .first()
                if presented else None
            )
            if grant is None or grant.revoked_at is not None or grant.expires_at <= now:
                return _oauth_error("invalid_grant", "The refresh token is invalid.")
            if grant.client_id != client_id:
                return _oauth_error("invalid_grant", "The refresh token was issued to another client.")
            # Rotate on every use so a stolen refresh token is single-use at best.
            rotated = new_secret(32)
            grant.refresh_token_hash = hash_token(rotated)
            session.add(grant)
            session.commit()
            scope, subject, gid = grant.scope, grant.subject, grant.id

        kid, private_pem = keys.active_key()
        access = tokens.issue_access_token(
            private_pem=private_pem, kid=kid, issuer=resolved.issuer, subject=subject,
            audience=resolved.resource, client_id=client_id, scope=scope,
            grant_id=gid, ttl_seconds=resolved.access_token_ttl_seconds,
        )
        return JSONResponse(
            {"access_token": access, "token_type": "Bearer",
             "expires_in": resolved.access_token_ttl_seconds,
             "refresh_token": rotated, "scope": scope},
            headers={"Cache-Control": "no-store", "Pragma": "no-cache"},
        )

    # ---------- revocation ----------

    @app.post("/revoke")
    async def revoke(request: Request) -> JSONResponse:
        """RFC 7009. Always returns 200, even for an unknown token, so the endpoint cannot
        be used to probe which tokens exist."""
        form = await request.form()
        presented = str(form.get("token") or "")
        now = dt.datetime.now(dt.timezone.utc)
        if presented:
            with sessions() as session:
                grant = (
                    session.query(Grant)
                    .filter(Grant.refresh_token_hash == hash_token(presented))
                    .first()
                )
                if grant is None:
                    claims = tokens.decode_access_token(
                        presented, keys.public_jwks(),
                        issuer=resolved.issuer, audience=resolved.resource,
                    )
                    if claims:
                        grant = session.get(Grant, claims.get("gid"))
                if grant is not None and grant.revoked_at is None:
                    grant.revoked_at = now
                    grant.refresh_token_hash = None
                    session.add(grant)
                    session.commit()
        return JSONResponse({}, status_code=200)

    @app.get("/introspect/grant/{grant_id}")
    async def grant_state(grant_id: str) -> JSONResponse:
        """Internal: lets the MCP confirm a token's grant is still live, so revocation
        takes effect before the access token's own expiry."""
        with sessions() as session:
            grant = session.get(Grant, grant_id)
            active = bool(grant and grant.revoked_at is None
                          and grant.expires_at > dt.datetime.now(dt.timezone.utc))
            return JSONResponse({"active": active})

    return app
