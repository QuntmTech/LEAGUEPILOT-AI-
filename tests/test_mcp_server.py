from __future__ import annotations

from datetime import timedelta

import httpx
import pytest
from fastapi.testclient import TestClient
from mcp.server.auth.provider import AccessToken
from mcp.shared.memory import create_connected_server_and_client_session

from app.mcp_gateway.client import CloudPodClient
from app.mcp_gateway.server import SERVER_INSTRUCTIONS, create_mcp_server
from app.mcp_gateway.settings import McpSettings


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


class StaticVerifier:
    async def verify_token(self, token: str) -> AccessToken | None:
        if token != "valid-test-token":
            return None
        return AccessToken(
            token=token,
            client_id="test-client",
            scopes=["leaguepilot:read", "leaguepilot:write"],
            subject="abc123abc123abc",
        )


def settings() -> McpSettings:
    return McpSettings(
        cloudpod_url="https://cloudpod.test",
        public_url="https://mcp.test",
        issuer_url="https://auth.test",
        documentation_url="https://docs.test/mcp",
    )


@pytest.mark.anyio
async def test_server_advertises_focused_tools_and_safety_metadata() -> None:
    server = create_mcp_server(settings(), token_verifier=StaticVerifier())
    async with create_connected_server_and_client_session(
        server, read_timeout_seconds=timedelta(seconds=2)
    ) as session:
        result = await session.list_tools()

    tools = {tool.name: tool for tool in result.tools}
    assert set(tools) == {
        "leaguepilot_health",
        "list_leagues",
        "get_league_snapshot",
        "get_roster",
        "get_matchup",
        "get_draft_context",
        "list_recommendations",
        "get_weekly_report",
        "get_job_status",
        "sync_league",
        "run_analysis",
        "review_recommendation",
    }
    assert tools["get_roster"].annotations.readOnlyHint is True
    assert tools["sync_league"].annotations.readOnlyHint is False
    assert tools["sync_league"].annotations.openWorldHint is True
    assert tools["review_recommendation"].annotations.destructiveHint is False
    assert "confirmed" in tools["review_recommendation"].inputSchema["required"]
    assert "never executes an ESPN action" in SERVER_INSTRUCTIONS


def test_streamable_http_rejects_missing_token_and_publishes_resource_metadata() -> None:
    server = create_mcp_server(settings(), token_verifier=StaticVerifier())
    app = server.streamable_http_app()
    request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2025-06-18",
            "capabilities": {},
            "clientInfo": {"name": "test", "version": "1.0"},
        },
    }
    headers = {"Accept": "application/json, text/event-stream", "Host": "mcp.test"}
    with TestClient(app) as client:
        process_health = client.get("/healthz", headers={"Host": "mcp.test"})
        assert process_health.json() == {
            "status": "ok",
            "service": "fantasy-warroom-mcp",
            "version": "0.5.0",
        }

        unauthorized = client.post("/mcp", json=request, headers=headers)
        assert unauthorized.status_code == 401
        assert "resource_metadata=" in unauthorized.headers["WWW-Authenticate"]

        invalid = client.post(
            "/mcp",
            json=request,
            headers={**headers, "Authorization": "Bearer invalid"},
        )
        assert invalid.status_code == 401

        valid = client.post(
            "/mcp",
            json=request,
            headers={**headers, "Authorization": "Bearer valid-test-token"},
        )
        assert valid.status_code == 200
        assert valid.json()["result"]["serverInfo"]["name"] == "fantasy-warroom"

        metadata = client.get("/.well-known/oauth-protected-resource")
        assert metadata.status_code == 200
        assert metadata.json()["resource"] == "https://mcp.test/"
        assert metadata.json()["authorization_servers"] == ["https://auth.test/"]
        assert metadata.json()["scopes_supported"] == [
            "leaguepilot:read",
            "leaguepilot:write",
        ]


def test_authenticated_streamable_http_tool_call_reaches_safe_backend_client() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.path == "/api/leaguepilot/health"
        assert request.headers["Authorization"] == "Bearer valid-test-token"
        return httpx.Response(200, json={"status": "ok", "queue": "available"})

    transport = httpx.MockTransport(handler)
    server = create_mcp_server(
        settings(),
        token_verifier=StaticVerifier(),
        client_factory=lambda token: CloudPodClient(
            "https://cloudpod.test", token, transport=transport
        ),
    )
    headers = {
        "Accept": "application/json, text/event-stream",
        "Authorization": "Bearer valid-test-token",
        "Host": "mcp.test",
    }
    initialize = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2025-06-18",
            "capabilities": {},
            "clientInfo": {"name": "test", "version": "1.0"},
        },
    }
    call = {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/call",
        "params": {"name": "leaguepilot_health", "arguments": {}},
    }
    with TestClient(server.streamable_http_app()) as client:
        assert client.post("/mcp", json=initialize, headers=headers).status_code == 200
        response = client.post("/mcp", json=call, headers=headers)

    assert response.status_code == 200
    result = response.json()["result"]
    assert result["structuredContent"]["data"] == {
        "status": "ok",
        "queue": "available",
    }
