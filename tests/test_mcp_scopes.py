"""Per-tool scope enforcement in the MCP gateway.

The gateway previously demanded both leaguepilot:read and leaguepilot:write at the
transport, so a read-only grant could not authenticate at all and the read scope was
effectively decorative. Scope is now enforced per tool. These tests drive the real
ASGI app over HTTP with tokens carrying each combination of scopes.

Authentication is never treated as confirmation: a write-scoped token still has to pass
confirmed=true, which is asserted here rather than assumed.
"""

from __future__ import annotations

import json

import httpx
import pytest
from fastapi.testclient import TestClient
from mcp.server.auth.provider import AccessToken

from app.mcp_gateway.client import CloudPodClient
from app.mcp_gateway.server import build_http_app, create_mcp_server
from app.mcp_gateway.settings import McpSettings

READ = "leaguepilot:read"
WRITE = "leaguepilot:write"
WORKSPACE = "wksp00000000001"
CONNECTION = "conn00000000001"

TOKENS = {
    "read-only": [READ],
    "write-only": [WRITE],
    "both": [READ, WRITE],
    "none": [],
}


class ScopedVerifier:
    """Maps a bearer to the scopes named by TOKENS."""

    async def verify_token(self, token: str) -> AccessToken | None:
        if token not in TOKENS:
            return None
        return AccessToken(
            token=token,
            client_id="scope-test",
            scopes=list(TOKENS[token]),
            subject="abc123abc123abc",
        )


def _settings() -> McpSettings:
    return McpSettings(
        cloudpod_url="https://cloudpod.test",
        public_url="https://mcp.test",
        issuer_url="https://auth.test",
        documentation_url="https://docs.test/mcp",
    )


def _backend(request: httpx.Request) -> httpx.Response:
    """A permissive CloudPod stand-in, so any denial we see comes from scope alone."""
    path = request.url.path
    if path.endswith("/auth-refresh"):
        return httpx.Response(200, json={"record": {"id": "abc123abc123abc",
                                                    "email": "owner@example.com"}})
    if "/collections/workspaces/records" in path:
        return httpx.Response(200, json={"items": [{"id": WORKSPACE, "name": "W"}],
                                         "page": 1, "perPage": 1, "totalItems": 1})
    if "/records" in path:
        return httpx.Response(200, json={"items": [], "page": 1, "perPage": 0,
                                         "totalItems": 0})
    return httpx.Response(200, json={"ok": True, "id": "job00000000001x"})


@pytest.fixture
def client():
    transport = httpx.MockTransport(_backend)

    def factory(token: str) -> CloudPodClient:
        return CloudPodClient("https://cloudpod.test", token,
                              transport=transport, timeout_seconds=5)

    server = create_mcp_server(_settings(), token_verifier=ScopedVerifier(),
                               client_factory=factory)
    with TestClient(build_http_app(server, _settings())) as test_client:
        yield test_client


HEADERS = {"Accept": "application/json, text/event-stream",
           "Host": "mcp.test",
           "Content-Type": "application/json"}


def _call(client, token, tool, arguments=None):
    """Invoke one tool over Streamable HTTP and return (http_status, payload)."""
    response = client.post(
        "/mcp",
        json={"jsonrpc": "2.0", "id": 1, "method": "tools/call",
              "params": {"name": tool, "arguments": arguments or {}}},
        headers={**HEADERS, "Authorization": f"Bearer {token}"},
    )
    if response.status_code != 200:
        return response.status_code, response.json()
    return 200, response.json()


def _is_error(payload) -> bool:
    result = payload.get("result") or {}
    return bool(result.get("isError")) or "error" in payload


def _text(payload) -> str:
    return json.dumps(payload)


READ_TOOLS = [
    ("leaguepilot_health", {}),
    ("list_leagues", {}),
    ("get_league_snapshot", {"workspace_id": WORKSPACE, "connection_id": CONNECTION}),
    ("list_recommendations", {"workspace_id": WORKSPACE}),
    ("get_weekly_report", {"workspace_id": WORKSPACE}),
    ("get_job_status", {"job_id": "job00000000001x"}),
]

WRITE_TOOLS = [
    ("sync_league", {"connection_id": CONNECTION, "confirmed": True}),
    ("run_analysis", {"workspace_id": WORKSPACE, "connection_id": CONNECTION,
                      "kind": "weekly-report", "confirmed": True}),
    ("review_recommendation", {"recommendation_id": "rec00000000001x",
                               "decision": "approved", "confirmed": True}),
]


# ------------------------------------------------ a read-only grant is usable


def test_read_only_token_can_authenticate_at_all(client):
    """The original defect: the transport demanded write, so this returned 403."""
    status, payload = _call(client, "read-only", "leaguepilot_health")
    assert status == 200
    assert not _is_error(payload), _text(payload)


@pytest.mark.parametrize("tool,args", READ_TOOLS)
def test_read_only_token_may_use_every_read_tool(client, tool, args):
    status, payload = _call(client, "read-only", tool, args)
    assert status == 200
    assert "insufficient_scope" not in _text(payload), f"{tool} denied a read-scoped token"


@pytest.mark.parametrize("tool,args", READ_TOOLS)
def test_combined_token_may_use_every_read_tool(client, tool, args):
    status, payload = _call(client, "both", tool, args)
    assert status == 200
    assert "insufficient_scope" not in _text(payload)


# --------------------------------------- read-only is refused on write tools


@pytest.mark.parametrize("tool,args", WRITE_TOOLS)
def test_read_only_token_is_refused_on_write_tools(client, tool, args):
    status, payload = _call(client, "read-only", tool, args)
    assert status == 200, "the denial must be a controlled tool error, not a transport failure"
    body = _text(payload)
    assert _is_error(payload), f"{tool} accepted a read-only token"
    assert "insufficient_scope" in body
    assert "403" in body
    assert "leaguepilot:write" in body
    assert "Traceback" not in body


@pytest.mark.parametrize("tool,args", WRITE_TOOLS)
def test_write_scoped_token_is_accepted_by_write_tools(client, tool, args):
    status, payload = _call(client, "write-only", tool, args)
    assert status == 200
    assert "insufficient_scope" not in _text(payload), f"{tool} refused a write-scoped token"


def test_write_only_token_is_refused_on_read_tools(client):
    """Scopes are enforced in both directions, not just against read-only clients."""
    status, payload = _call(client, "write-only", "list_leagues")
    assert status == 200
    body = _text(payload)
    assert _is_error(payload)
    assert "insufficient_scope" in body
    assert "leaguepilot:read" in body


# ------------------------------------------------- no scopes, and no token


@pytest.mark.parametrize("tool,args", READ_TOOLS + WRITE_TOOLS)
def test_token_with_no_scopes_can_use_nothing(client, tool, args):
    status, payload = _call(client, "none", tool, args)
    assert status == 200
    assert _is_error(payload), f"{tool} served a token with no scopes"
    assert "insufficient_scope" in _text(payload)


def test_unauthenticated_request_is_rejected_at_the_transport(client):
    response = client.post(
        "/mcp",
        json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
        headers=HEADERS,
    )
    assert response.status_code == 401


def test_invalid_bearer_is_rejected(client):
    response = client.post(
        "/mcp",
        json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
        headers={**HEADERS, "Authorization": "Bearer not-a-real-token"},
    )
    assert response.status_code == 401


# -------------------------------- authentication is not confirmation


@pytest.mark.parametrize("tool,args", [
    ("sync_league", {"connection_id": CONNECTION, "confirmed": False}),
    ("run_analysis", {"workspace_id": WORKSPACE, "connection_id": CONNECTION,
                      "kind": "weekly-report", "confirmed": False}),
    ("review_recommendation", {"recommendation_id": "rec00000000001x",
                               "decision": "approved", "confirmed": False}),
])
def test_write_scope_alone_does_not_confirm_a_write(client, tool, args):
    """Holding leaguepilot:write must not stand in for the user's explicit confirmation."""
    status, payload = _call(client, "both", tool, args)
    assert status == 200
    body = _text(payload)
    assert _is_error(payload), f"{tool} acted without confirmed=true"
    assert "confirmed" in body


# ------------------------------------------------------------ advertisement


def test_metadata_advertises_both_scopes_even_though_neither_is_enforced(client):
    """Enforcement is per tool, but clients still need to learn which scopes exist."""
    metadata = client.get("/.well-known/oauth-protected-resource",
                          headers={"Host": "mcp.test"}).json()
    assert metadata["scopes_supported"] == ["leaguepilot:read", "leaguepilot:write"]
    assert metadata["authorization_servers"] == ["https://auth.test/"]
