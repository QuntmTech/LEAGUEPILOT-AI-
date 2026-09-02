from __future__ import annotations

import datetime as dt

from authlib.jose import JsonWebToken

# JWT signing and verification are delegated entirely to authlib. This module only builds
# and checks the claim set required by the MCP specification.
_JWT = JsonWebToken(["RS256"])


def issue_access_token(
    *, private_pem: str, kid: str, issuer: str, subject: str, audience: str,
    client_id: str, scope: str, grant_id: str, ttl_seconds: int,
) -> str:
    """Mint an audience-bound access token.

    `aud` is the MCP resource, not the client. A token minted for this resource is
    therefore useless at any other server that validates audience, which is what the
    MCP resource-parameter requirement is protecting against.
    """
    now = dt.datetime.now(dt.UTC)
    claims = {
        "iss": issuer,
        "sub": subject,
        "aud": audience,
        "client_id": client_id,
        "scope": scope,
        "gid": grant_id,
        "iat": int(now.timestamp()),
        "exp": int((now + dt.timedelta(seconds=ttl_seconds)).timestamp()),
    }
    header = {"alg": "RS256", "kid": kid, "typ": "at+jwt"}
    return _JWT.encode(header, claims, private_pem).decode("ascii")


def decode_access_token(token: str, jwks: dict, *, issuer: str, audience: str) -> dict | None:
    """Validate signature, issuer, audience and expiry. Returns None on any failure.

    Returning None rather than raising keeps failure modes indistinguishable to a caller,
    so an attacker cannot use error shape to learn why a token was rejected.
    """
    try:
        claims = _JWT.decode(
            token,
            jwks,
            claims_options={
                "iss": {"essential": True, "value": issuer},
                "aud": {"essential": True, "value": audience},
                "exp": {"essential": True},
                "sub": {"essential": True},
            },
        )
        claims.validate()
        return dict(claims)
    except Exception:
        return None
