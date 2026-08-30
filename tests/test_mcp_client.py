from __future__ import annotations

import json

import httpx
import pytest

from app.mcp_gateway.client import CloudPodClient
from app.mcp_gateway.errors import McpBackendError, McpInputError


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.mark.anyio
async def test_authentication_validates_with_pocketbase_without_exposing_token() -> None:
    secret = "header.payload.signature"

    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/api/collections/users/auth-refresh"
        assert request.headers["Authorization"] == f"Bearer {secret}"
        assert request.headers["User-Agent"] == "LeaguePilot-MCP/0.5.0"
        return httpx.Response(200, json={"record": {"id": "abc123abc123abc", "email": "a@b.test"}})

    client = CloudPodClient("https://cloudpod.test", secret, transport=httpx.MockTransport(handler))
    user = await client.authenticate()
    assert user.id == "abc123abc123abc"
    assert secret not in repr(user)


@pytest.mark.anyio
async def test_collection_read_uses_fixed_safe_fields_and_scope() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/collections/league_snapshots/records"
        assert request.url.params["fields"] == (
            "id,workspace,connection,week,payload,schema_version,fetched_at,expires_at"
        )
        assert request.url.params["filter"] == (
            'workspace = "abc123abc123abc" && connection = "def456def456def"'
        )
        assert request.url.params["sort"] == "-fetched_at"
        return httpx.Response(
            200,
            json={"items": [{"id": "ghi789ghi789ghi", "payload": {}}], "totalItems": 1},
        )

    client = CloudPodClient(
        "https://cloudpod.test", "token", transport=httpx.MockTransport(handler)
    )
    page = await client.list_records(
        "league_snapshots",
        filters=[
            'workspace = "abc123abc123abc"',
            'connection = "def456def456def"',
        ],
        sort="-fetched_at",
        limit=1,
    )
    assert page.total_items == 1
    assert page.items[0]["id"] == "ghi789ghi789ghi"


@pytest.mark.anyio
async def test_backend_error_is_redacted() -> None:
    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            500,
            content=json.dumps(
                {
                    "debug": "credential_material=redacted-example",
                    "stack": "private",
                    "message": "Safe failure",
                }
            ).encode(),
        )

    client = CloudPodClient(
        "https://cloudpod.test", "token", transport=httpx.MockTransport(handler)
    )
    with pytest.raises(McpBackendError, match="could not complete") as exc_info:
        await client.health()
    assert "credential_material" not in str(exc_info.value)
    assert "stack" not in str(exc_info.value)


@pytest.mark.anyio
async def test_authentication_error_never_forwards_backend_body() -> None:
    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"message": "raw account detail"})

    client = CloudPodClient(
        "https://cloudpod.test", "token", transport=httpx.MockTransport(handler)
    )
    with pytest.raises(McpBackendError) as exc_info:
        await client.authenticate()
    assert "raw account detail" not in str(exc_info.value)


@pytest.mark.anyio
async def test_unknown_collection_and_invalid_record_id_are_rejected_locally() -> None:
    client = CloudPodClient("https://cloudpod.test", "token")
    with pytest.raises(McpInputError, match="not available"):
        await client.list_records("users")
    with pytest.raises(McpInputError, match="15-character"):
        await client.get_record("job_runs", "../admin")
