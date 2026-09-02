from __future__ import annotations

import httpx
from mcp.server.auth.provider import AccessToken, TokenVerifier

from app.auth_server import tokens as jwt_tokens
from app.mcp_gateway.auth import PocketBaseTokenVerifier


class CompositeTokenVerifier(TokenVerifier):
    """Accept both OAuth access tokens and existing PocketBase bearer tokens.

    Order matters. OAuth tokens are checked first because they are cheap to validate
    locally and carry explicit scopes. Anything that is not a valid OAuth token falls
    through to PocketBase, which is what keeps the already-working Claude Code static
    bearer connection alive through the migration — that path is unchanged.

    Migration safety: if the OAuth issuer is unreachable, JWKS fetching fails closed for
    OAuth tokens only. PocketBase bearers keep working, so an authorization-server outage
    degrades new browser sign-ins rather than breaking the existing connection.
    """

    def __init__(
        self,
        *,
        cloudpod_url: str,
        issuer_url: str,
        resource_url: str,
        internal_auth_url: str | None = None,
        introspection_secret: str | None = None,
        timeout_seconds: float = 20.0,
    ) -> None:
        self._fallback = PocketBaseTokenVerifier(cloudpod_url, timeout_seconds=timeout_seconds)
        # `_issuer` is the public identity we validate the `iss` claim against and must
        # not change. `_internal` is where we actually send JWKS and introspection
        # requests, so those stay on the private network and never depend on public DNS.
        self._issuer = issuer_url.rstrip("/")
        self._internal = (internal_auth_url or issuer_url).rstrip("/")
        self._resource = resource_url.rstrip("/")
        self._introspection_secret = introspection_secret
        self._timeout = timeout_seconds
        self._jwks: dict | None = None

    async def _load_jwks(self) -> dict | None:
        if self._jwks is not None:
            return self._jwks
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as http:
                response = await http.get(f"{self._internal}/.well-known/jwks.json")
            if response.status_code != 200:
                return None
            self._jwks = response.json()
            return self._jwks
        except Exception:
            return None

    async def _grant_is_active(self, grant_id: str) -> bool:
        """Revocation must take effect before the access token's own expiry.

        Fails closed at every step. A missing service credential, a rejected one, an
        unreachable authorization server or a malformed reply all mean the grant cannot
        be confirmed live, and an unconfirmable grant is treated as revoked. That
        deliberately makes an introspection outage deny OAuth tokens rather than admit
        revoked ones; PocketBase bearers are unaffected and keep working.
        """
        if not grant_id or not self._introspection_secret:
            return False
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as http:
                response = await http.get(
                    f"{self._internal}/introspect/grant/{grant_id}",
                    headers={"Authorization": f"Bearer {self._introspection_secret}"},
                )
            if response.status_code != 200:
                return False
            return bool(response.json().get("active"))
        except Exception:
            # Never let the reason surface: it could name an internal host or credential.
            return False

    async def verify_token(self, token: str) -> AccessToken | None:
        if not token or len(token) > 4096:
            return None

        jwks = await self._load_jwks()
        if jwks:
            claims = jwt_tokens.decode_access_token(
                token, jwks, issuer=self._issuer, audience=self._resource
            )
            if claims:
                if not await self._grant_is_active(str(claims.get("gid") or "")):
                    return None
                scopes = [s for s in str(claims.get("scope") or "").split() if s]
                return AccessToken(
                    token=token,
                    client_id=str(claims.get("client_id") or "leaguepilot-oauth"),
                    scopes=scopes,
                    subject=str(claims.get("sub") or ""),
                    claims={"sub": claims.get("sub"), "gid": claims.get("gid")},
                )

        # Not an OAuth token — preserve the existing static-bearer behaviour unchanged.
        return await self._fallback.verify_token(token)
