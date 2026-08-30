from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any
from urllib.parse import urlsplit

import httpx

from app.mcp_gateway.errors import McpBackendError, McpInputError
from app.mcp_gateway.models import AuthenticatedUser, CollectionPage
from app.meta import VERSION

RECORD_ID = re.compile(r"^[a-z0-9]{15}$")

SAFE_FIELDS: dict[str, str] = {
    "workspaces": "id,name,slug,plan,status,timezone",
    "espn_connections": (
        "id,workspace,league_id,team_id,season,is_public,league_name,status,last_error,"
        "last_synced_at,next_sync_at,sync_failures"
    ),
    "league_snapshots": (
        "id,workspace,connection,week,payload,schema_version,fetched_at,expires_at"
    ),
    "recommendations": (
        "id,workspace,snapshot,kind,title,summary,confidence,impact_points,payload,status,"
        "expires_at,reviewed_at"
    ),
    "reports": (
        "id,workspace,snapshot,week,title,body_markdown,metrics,narration_mode,published_at"
    ),
    "job_runs": (
        "id,workspace,connection,kind,status,attempts,max_attempts,scheduled_for,started_at,"
        "completed_at,last_error"
    ),
}


def validate_record_id(value: str, label: str) -> str:
    if not RECORD_ID.fullmatch(value):
        raise McpInputError(f"{label} must be a 15-character LEAGUEPILOT record ID.")
    return value


def _safe_message(payload: Any, fallback: str) -> str:
    if isinstance(payload, Mapping):
        message = payload.get("message") or payload.get("detail")
        if isinstance(message, str) and message.strip():
            return " ".join(message.replace("\x00", "").split())[:300]
    return fallback


class CloudPodClient:
    """Tenant-scoped client. PocketBase remains the authorization authority."""

    def __init__(
        self,
        base_url: str,
        token: str,
        *,
        timeout_seconds: float = 20.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        parsed = urlsplit(base_url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ValueError("CloudPod URL must be an absolute HTTP(S) URL")
        self._base_url = base_url.rstrip("/")
        self._token = token
        self._timeout = timeout_seconds
        self._transport = transport

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: Mapping[str, str] | None = None,
        json: Mapping[str, Any] | None = None,
    ) -> Any:
        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {self._token}",
            "User-Agent": f"LeaguePilot-MCP/{VERSION}",
        }
        try:
            async with httpx.AsyncClient(
                timeout=self._timeout,
                transport=self._transport,
                follow_redirects=False,
            ) as client:
                response = await client.request(
                    method,
                    f"{self._base_url}{path}",
                    headers=headers,
                    params=params,
                    json=json,
                )
        except httpx.TimeoutException as exc:
            raise McpBackendError(
                "LEAGUEPILOT timed out. Try again shortly.", status_code=504
            ) from exc
        except httpx.HTTPError as exc:
            raise McpBackendError("LEAGUEPILOT is temporarily unreachable.") from exc

        payload: Any = None
        if response.content:
            try:
                payload = response.json()
            except ValueError:
                payload = None
        if response.is_success:
            return payload
        if response.status_code in {401, 403}:
            raise McpBackendError(
                "Your LEAGUEPILOT session is invalid or expired. Reconnect the MCP account.",
                status_code=response.status_code,
            )
        if response.status_code == 404:
            raise McpBackendError(
                "The requested LEAGUEPILOT record was not found.", status_code=404
            )
        if response.status_code == 429:
            raise McpBackendError(
                "LEAGUEPILOT is rate-limiting requests. Try again shortly.", status_code=429
            )
        if response.status_code in {400, 409, 422}:
            raise McpBackendError(
                _safe_message(payload, "LEAGUEPILOT rejected the request."),
                status_code=response.status_code,
            )
        raise McpBackendError(
            "LEAGUEPILOT could not complete the request.",
            status_code=response.status_code,
        )

    async def authenticate(self) -> AuthenticatedUser:
        payload = await self._request("POST", "/api/collections/users/auth-refresh", json={})
        record = payload.get("record") if isinstance(payload, Mapping) else None
        if not isinstance(record, Mapping) or not isinstance(record.get("id"), str):
            raise McpBackendError("LEAGUEPILOT returned an invalid authentication response.")
        email = record.get("email")
        return AuthenticatedUser(id=record["id"], email=email if isinstance(email, str) else None)

    async def health(self) -> dict[str, Any]:
        payload = await self._request("GET", "/api/leaguepilot/health")
        return dict(payload) if isinstance(payload, Mapping) else {"status": "unavailable"}

    async def bootstrap(self) -> dict[str, Any]:
        payload = await self._request("POST", "/api/leaguepilot/bootstrap", json={})
        if not isinstance(payload, Mapping):
            raise McpBackendError("LEAGUEPILOT returned an invalid bootstrap response.")
        return dict(payload)

    async def list_records(
        self,
        collection: str,
        *,
        filters: list[str] | None = None,
        sort: str = "",
        limit: int = 50,
    ) -> CollectionPage:
        if collection not in SAFE_FIELDS:
            raise McpInputError("That collection is not available through the MCP.")
        bounded_limit = max(1, min(limit, 200))
        params = {"page": "1", "perPage": str(bounded_limit), "fields": SAFE_FIELDS[collection]}
        if filters:
            params["filter"] = " && ".join(filters)
        if sort:
            params["sort"] = sort
        payload = await self._request(
            "GET", f"/api/collections/{collection}/records", params=params
        )
        if not isinstance(payload, Mapping):
            raise McpBackendError("LEAGUEPILOT returned an invalid collection response.")
        items = payload.get("items")
        safe_items = (
            [dict(item) for item in items if isinstance(item, Mapping)]
            if isinstance(items, list)
            else []
        )
        return CollectionPage(
            items=safe_items,
            page=int(payload.get("page") or 1),
            per_page=int(payload.get("perPage") or bounded_limit),
            total_items=int(payload.get("totalItems") or len(safe_items)),
        )

    async def get_record(self, collection: str, record_id: str) -> dict[str, Any]:
        validate_record_id(record_id, "Record ID")
        if collection not in SAFE_FIELDS:
            raise McpInputError("That collection is not available through the MCP.")
        payload = await self._request(
            "GET",
            f"/api/collections/{collection}/records/{record_id}",
            params={"fields": SAFE_FIELDS[collection]},
        )
        if not isinstance(payload, Mapping):
            raise McpBackendError("LEAGUEPILOT returned an invalid record response.")
        return dict(payload)

    async def sync(self, connection_id: str) -> dict[str, Any]:
        validate_record_id(connection_id, "Connection ID")
        payload = await self._request(
            "POST", f"/api/leaguepilot/connections/{connection_id}/sync", json={}
        )
        return dict(payload) if isinstance(payload, Mapping) else {}

    async def analyze(
        self,
        workspace_id: str,
        *,
        kind: str,
        connection_id: str | None,
        notify: bool,
    ) -> dict[str, Any]:
        validate_record_id(workspace_id, "Workspace ID")
        body: dict[str, Any] = {"kind": kind, "notify": notify}
        if connection_id:
            body["connection_id"] = validate_record_id(connection_id, "Connection ID")
        payload = await self._request(
            "POST", f"/api/leaguepilot/workspaces/{workspace_id}/analysis", json=body
        )
        return dict(payload) if isinstance(payload, Mapping) else {}

    async def review(self, recommendation_id: str, decision: str) -> dict[str, Any]:
        validate_record_id(recommendation_id, "Recommendation ID")
        payload = await self._request(
            "POST",
            f"/api/leaguepilot/recommendations/{recommendation_id}/review",
            json={"decision": decision},
        )
        return dict(payload) if isinstance(payload, Mapping) else {}
