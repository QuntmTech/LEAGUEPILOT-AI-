from __future__ import annotations

import datetime as dt
import ipaddress
from urllib.parse import urlsplit

import httpx

from app.auth_server.models import OAuthClient

# Metadata documents are cached this long before re-fetch. Short enough that a client can
# rotate its redirect URIs, long enough that the authorize endpoint is not a proxy for
# arbitrary outbound requests.
METADATA_CACHE_SECONDS = 3600
MAX_METADATA_BYTES = 64 * 1024


class ClientError(Exception):
    """Raised with an OAuth error code the endpoint maps to a response."""

    def __init__(self, error: str, description: str) -> None:
        super().__init__(description)
        self.error = error
        self.description = description


def _is_https_url(value: str) -> bool:
    parts = urlsplit(value)
    return parts.scheme == "https" and bool(parts.hostname)


def _blocks_ssrf(host: str) -> bool:
    """Reject hosts that resolve to private space by literal inspection.

    The authorize endpoint fetches a client-supplied URL, so it is an SSRF surface. Literal
    IPs and localhost are refused outright; DNS-rebinding is additionally mitigated by the
    hard size cap, the short timeout, and the fact that only JSON is ever parsed from it.
    """
    lowered = host.lower()
    if lowered in {"localhost", "127.0.0.1", "::1"} or lowered.endswith(".localhost"):
        return True
    try:
        ip = ipaddress.ip_address(lowered)
    except ValueError:
        return False
    return ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved


def validate_redirect_uris(uris: list[str]) -> list[str]:
    """Redirect URIs must be absolute and HTTPS, or a loopback URI for native clients.

    Wildcards and bare schemes are refused: exact matching at authorize time is only
    meaningful if what was registered is itself exact.
    """
    cleaned: list[str] = []
    for uri in uris:
        candidate = (uri or "").strip()
        if not candidate or len(candidate) > 2048 or "*" in candidate:
            raise ClientError("invalid_redirect_uri", "Redirect URIs must be exact HTTPS URLs.")
        parts = urlsplit(candidate)
        if parts.fragment:
            raise ClientError("invalid_redirect_uri", "Redirect URIs must not contain a fragment.")
        loopback = parts.scheme == "http" and parts.hostname in {"127.0.0.1", "::1"}
        if not (parts.scheme == "https" or loopback):
            raise ClientError("invalid_redirect_uri", "Redirect URIs must use HTTPS.")
        cleaned.append(candidate)
    if not cleaned:
        raise ClientError("invalid_redirect_uri", "At least one redirect URI is required.")
    return cleaned


def normalize_scope(requested: str | None, allowed: set[str]) -> str:
    """Intersect the requested scope with what this server issues.

    Unknown scopes are dropped rather than rejected, and the result is never wider than
    what was asked for — a client cannot be granted more than it requested.
    """
    wanted = [s for s in (requested or "").split() if s]
    if not wanted:
        return "leaguepilot:read"
    granted = [s for s in wanted if s in allowed]
    if not granted:
        raise ClientError("invalid_scope", "No supported scope was requested.")
    return " ".join(dict.fromkeys(granted))


async def fetch_client_id_metadata(client_id: str, timeout_seconds: float) -> dict:
    """Resolve an HTTPS Client ID Metadata Document.

    This is the mechanism behind Claude's "Use Anthropic's hosted client metadata": the
    client_id *is* an HTTPS URL serving its own registration metadata. The document's own
    `client_id` must equal the URL it was fetched from, which is what stops one client
    claiming another's identity.
    """
    if not _is_https_url(client_id):
        raise ClientError("invalid_client", "Client ID metadata URL must be HTTPS.")
    host = urlsplit(client_id).hostname or ""
    if _blocks_ssrf(host):
        raise ClientError("invalid_client", "Client ID metadata URL is not reachable.")

    try:
        async with httpx.AsyncClient(timeout=timeout_seconds, follow_redirects=False) as http:
            response = await http.get(client_id, headers={"Accept": "application/json"})
    except httpx.HTTPError:
        raise ClientError("invalid_client", "Client ID metadata document could not be retrieved.")

    if response.status_code != 200:
        raise ClientError("invalid_client", "Client ID metadata document could not be retrieved.")
    if len(response.content) > MAX_METADATA_BYTES:
        raise ClientError("invalid_client", "Client ID metadata document is too large.")
    try:
        document = response.json()
    except ValueError:
        raise ClientError("invalid_client", "Client ID metadata document is not valid JSON.")
    if not isinstance(document, dict):
        raise ClientError("invalid_client", "Client ID metadata document is not an object.")

    declared = str(document.get("client_id") or "")
    if declared != client_id:
        raise ClientError(
            "invalid_client",
            "Client ID metadata document does not identify itself as this client.",
        )
    return document


def upsert_url_client(session, client_id: str, document: dict, allowed_scopes: set[str]) -> OAuthClient:
    """Cache a metadata-document client. Never given a secret: it is a public client."""
    redirects = validate_redirect_uris(list(document.get("redirect_uris") or []))
    scope = normalize_scope(document.get("scope"), allowed_scopes)
    now = dt.datetime.now(dt.timezone.utc)

    client = session.get(OAuthClient, client_id)
    if client is None:
        client = OAuthClient(client_id=client_id)
    client.client_name = str(document.get("client_name") or "")[:255]
    client.redirect_uris = "\n".join(redirects)
    client.scope = scope
    client.token_endpoint_auth_method = "none"
    client.is_url_client = True
    client.client_secret_hash = None
    client.metadata_fetched_at = now
    session.add(client)
    return client


def metadata_is_fresh(client: OAuthClient) -> bool:
    if not client.metadata_fetched_at:
        return False
    age = dt.datetime.now(dt.timezone.utc) - client.metadata_fetched_at
    return age.total_seconds() < METADATA_CACHE_SECONDS
