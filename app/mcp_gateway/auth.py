from __future__ import annotations

from mcp.server.auth.provider import AccessToken, TokenVerifier

from app.mcp_gateway.client import CloudPodClient


class PocketBaseTokenVerifier(TokenVerifier):
    """Validate bearer tokens against PocketBase and preserve tenant identity."""

    def __init__(self, base_url: str, *, timeout_seconds: float = 20.0) -> None:
        self._base_url = base_url
        self._timeout_seconds = timeout_seconds

    async def verify_token(self, token: str) -> AccessToken | None:
        if not token or len(token) > 4096:
            return None
        try:
            user = await CloudPodClient(
                self._base_url, token, timeout_seconds=self._timeout_seconds
            ).authenticate()
        except Exception:
            # Authentication middleware must never leak backend or token details.
            return None
        return AccessToken(
            token=token,
            client_id="leaguepilot-pocketbase",
            scopes=["leaguepilot:read", "leaguepilot:write"],
            subject=user.id,
            claims={"sub": user.id},
        )
