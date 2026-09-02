from __future__ import annotations

from collections.abc import Callable
from typing import Literal
from urllib.parse import urlsplit

from mcp.server.auth.middleware.auth_context import get_access_token
from mcp.server.auth.provider import TokenVerifier
from mcp.server.auth.settings import AuthSettings
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from mcp.types import ToolAnnotations
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.mcp_gateway.client import CloudPodClient
from app.mcp_gateway.composite_auth import CompositeTokenVerifier
from app.mcp_gateway.errors import McpAuthenticationError, McpScopeError
from app.mcp_gateway.models import ToolEnvelope
from app.mcp_gateway.service import AnalysisKind, LeaguePilotMcpService
from app.mcp_gateway.settings import McpSettings
from app.meta import VERSION

SERVER_INSTRUCTIONS = (
    "FΛNTΛSY WΛRROOM provides authenticated, tenant-scoped access to LEAGUEPILOT fantasy "
    "leagues, normalized ESPN snapshots, jobs, recommendations, and reports. Treat timestamps, "
    "missing fields, and warnings as authoritative. Never request or expose ESPN cookies, bearer "
    "tokens, ciphertext, or worker secrets. Read tools may run directly. Queue/review tools "
    "require "
    "explicit user intent and confirmed=true. Reviewing a recommendation records intent only; it "
    "never executes an ESPN action. Draft context is snapshot-based, not a live draft-room feed."
)


# Advertised to clients as available to request. Enforcement is per tool, below.
SUPPORTED_SCOPES = {"leaguepilot:read", "leaguepilot:write"}


def _current_token(required_scope: str = "leaguepilot:read") -> str:
    """Resolve the caller's token, enforcing this tool's scope.

    Scope is enforced per tool, not at the transport. Requiring write merely to open a
    connection would mean a read-only grant could not authenticate at all, which makes
    the read scope meaningless and forces every client to ask for write it may not need.
    """
    access = get_access_token()
    if access is None or not access.token:
        raise McpAuthenticationError()
    if required_scope not in access.scopes:
        raise McpScopeError(required_scope, granted=tuple(access.scopes or ()))
    return access.token


def _annotations(
    *, read_only: bool, idempotent: bool = False, open_world: bool = False
) -> ToolAnnotations:
    return ToolAnnotations(
        readOnlyHint=read_only,
        destructiveHint=False,
        idempotentHint=idempotent,
        openWorldHint=open_world,
    )


def create_mcp_server(
    settings: McpSettings | None = None,
    *,
    token_verifier: TokenVerifier | None = None,
    client_factory: Callable[[str], CloudPodClient] | None = None,
) -> FastMCP:
    resolved = settings or McpSettings()
    # Accepts OAuth access tokens from the authorization server AND existing PocketBase
    # bearers, so the working Claude Code connection survives the migration untouched.
    verifier = token_verifier or CompositeTokenVerifier(
        cloudpod_url=resolved.backend_url,
        issuer_url=str(resolved.issuer_url),
        resource_url=resolved.resource_url,
        internal_auth_url=resolved.internal_auth_origin,
        introspection_secret=resolved.introspection_token,
        timeout_seconds=resolved.request_timeout_seconds,
    )
    factory = client_factory or (
        lambda token: CloudPodClient(
            resolved.backend_url,
            token,
            timeout_seconds=resolved.request_timeout_seconds,
        )
    )
    service = LeaguePilotMcpService(factory)
    public_url = urlsplit(resolved.resource_url)
    allowed_hosts = [public_url.netloc, f"{resolved.host}:*", "127.0.0.1:*", "localhost:*"]
    allowed_origins = [f"{public_url.scheme}://{public_url.netloc}"]
    server = FastMCP(
        name="fantasy-warroom",
        instructions=SERVER_INSTRUCTIONS,
        website_url=str(resolved.documentation_url),
        token_verifier=verifier,
        auth=AuthSettings(
            issuer_url=resolved.issuer_url,
            resource_server_url=resolved.public_url,
            service_documentation_url=resolved.documentation_url,
            # Deliberately empty: authenticating must not require write. The transport
            # can only apply one scope list to every request, so a write requirement
            # here would reject a read-only grant before any tool is named. Each tool
            # enforces its own scope via _current_token().
            required_scopes=[],
        ),
        host=resolved.host,
        port=resolved.port,
        streamable_http_path="/mcp",
        json_response=True,
        stateless_http=True,
        log_level=resolved.log_level.upper(),
        transport_security=TransportSecuritySettings(
            enable_dns_rebinding_protection=True,
            allowed_hosts=sorted(set(allowed_hosts)),
            allowed_origins=sorted(set(allowed_origins)),
        ),
    )

    @server.tool(
        title="Check LEAGUEPILOT health",
        description="Check whether the LEAGUEPILOT control plane and job queue are reachable.",
        annotations=_annotations(read_only=True, idempotent=True),
    )
    async def leaguepilot_health() -> ToolEnvelope:
        return await service.health(_current_token())

    @server.tool(
        title="List fantasy leagues",
        description=(
            "List the authenticated user's LEAGUEPILOT workspace and safe ESPN league connection "
            "metadata. Use this first to obtain workspace and connection IDs."
        ),
        annotations=_annotations(read_only=True, idempotent=True),
    )
    async def list_leagues() -> ToolEnvelope:
        return await service.list_leagues(_current_token())

    @server.tool(
        title="Get latest league snapshot",
        description=(
            "Get the latest normalized, provider-neutral league snapshot for a workspace and "
            "optional ESPN connection. Missing or stale data is reported explicitly."
        ),
        annotations=_annotations(read_only=True, idempotent=True),
    )
    async def get_league_snapshot(
        workspace_id: str, connection_id: str | None = None
    ) -> ToolEnvelope:
        return await service.latest_snapshot(_current_token(), workspace_id, connection_id)

    @server.tool(
        title="Get fantasy roster",
        description=(
            "Get the configured user's roster, or another league team by numeric team_id, from "
            "the latest normalized snapshot."
        ),
        annotations=_annotations(read_only=True, idempotent=True),
    )
    async def get_roster(
        workspace_id: str,
        connection_id: str | None = None,
        team_id: int | None = None,
    ) -> ToolEnvelope:
        return await service.roster(
            _current_token(), workspace_id, connection_id=connection_id, team_id=team_id
        )

    @server.tool(
        title="Get fantasy matchup",
        description=(
            "Get the configured team's matchup for a week from the latest normalized snapshot."
        ),
        annotations=_annotations(read_only=True, idempotent=True),
    )
    async def get_matchup(
        workspace_id: str,
        connection_id: str | None = None,
        week: int | None = None,
    ) -> ToolEnvelope:
        return await service.matchup(
            _current_token(), workspace_id, connection_id=connection_id, week=week
        )

    @server.tool(
        title="Get draft decision context",
        description=(
            "Get snapshot-based roster needs and candidate players for draft decision support. "
            "This is not a live ESPN draft-room feed and never makes a pick."
        ),
        annotations=_annotations(read_only=True, idempotent=True),
    )
    async def get_draft_context(
        workspace_id: str, connection_id: str | None = None
    ) -> ToolEnvelope:
        return await service.draft_context(_current_token(), workspace_id, connection_id)

    @server.tool(
        title="List recommendations",
        description=(
            "List safe lineup, waiver, trade, or availability recommendations for a workspace."
        ),
        annotations=_annotations(read_only=True, idempotent=True),
    )
    async def list_recommendations(
        workspace_id: str,
        status: Literal["proposed", "approved", "dismissed", "superseded", "expired"] = "proposed",
        kind: Literal["lineup", "waiver", "trade", "availability-alert"] | None = None,
        limit: int = 50,
    ) -> ToolEnvelope:
        return await service.recommendations(
            _current_token(), workspace_id, status=status, kind=kind, limit=limit
        )

    @server.tool(
        title="Get weekly report",
        description="Get the latest weekly report, or the report for a specific week.",
        annotations=_annotations(read_only=True, idempotent=True),
    )
    async def get_weekly_report(workspace_id: str, week: int | None = None) -> ToolEnvelope:
        return await service.weekly_report(_current_token(), workspace_id, week)

    @server.tool(
        title="Get job status",
        description=(
            "Get the safe status of a sync or analysis job. Poll this after a queueing tool."
        ),
        annotations=_annotations(read_only=True, idempotent=True),
    )
    async def get_job_status(job_id: str) -> ToolEnvelope:
        return await service.job_status(_current_token(), job_id)

    @server.tool(
        title="Queue league synchronization",
        description=(
            "Queue a read-only ESPN synchronization for an existing connection. Call only after "
            "the user clearly asks to sync and pass confirmed=true."
        ),
        annotations=_annotations(read_only=False, idempotent=False, open_world=True),
    )
    async def sync_league(connection_id: str, confirmed: bool) -> ToolEnvelope:
        return await service.sync(_current_token("leaguepilot:write"), connection_id, confirmed)

    @server.tool(
        title="Queue fantasy analysis",
        description=(
            "Queue deterministic fantasy analysis for a workspace. Call only after the user asks "
            "for analysis and pass confirmed=true. notify=false unless the user requests delivery."
        ),
        annotations=_annotations(read_only=False, idempotent=False, open_world=False),
    )
    async def run_analysis(
        workspace_id: str,
        kind: AnalysisKind = "full",
        connection_id: str | None = None,
        notify: bool = False,
        confirmed: bool = False,
    ) -> ToolEnvelope:
        return await service.analyze(
            _current_token("leaguepilot:write"),
            workspace_id,
            kind=kind,
            connection_id=connection_id,
            notify=notify,
            confirmed=confirmed,
        )

    @server.tool(
        title="Review a recommendation",
        description=(
            "Record an approved or dismissed decision after explicit user confirmation. This "
            "never changes a lineup, submits a waiver, proposes a trade, or writes to ESPN."
        ),
        annotations=_annotations(read_only=False, idempotent=False, open_world=False),
    )
    async def review_recommendation(
        recommendation_id: str,
        decision: Literal["approved", "dismissed"],
        confirmed: bool,
    ) -> ToolEnvelope:
        return await service.review(
            _current_token("leaguepilot:write"), recommendation_id, decision, confirmed
        )

    @server.custom_route("/healthz", methods=["GET"])
    async def healthz(_: Request) -> JSONResponse:
        return JSONResponse({"status": "ok", "service": "fantasy-warroom-mcp", "version": VERSION})

    return server


def build_http_app(server: FastMCP, settings: McpSettings | None = None):
    """Build the ASGI app, separating advertised scopes from enforced ones.

    FastMCP passes `AuthSettings.required_scopes` to two different places: the transport
    middleware that rejects requests, and the RFC 9728 `scopes_supported` field that tells
    clients which scopes exist. Those are not the same thing. We enforce nothing at the
    transport (each tool checks its own scope) but must still advertise both scopes, or a
    client has no way to learn that `leaguepilot:write` is available to request.
    """
    from mcp.server.auth.routes import create_protected_resource_routes

    resolved = settings or McpSettings()
    http_app = server.streamable_http_app()

    replacement = create_protected_resource_routes(
        resource_url=resolved.public_url,
        authorization_servers=[resolved.issuer_url],
        scopes_supported=sorted(SUPPORTED_SCOPES),
        resource_name="FΛNTΛSY WΛRROOM",
        resource_documentation=resolved.documentation_url,
    )
    wanted = {route.path for route in replacement}
    http_app.router.routes = [
        route for route in http_app.router.routes
        if getattr(route, "path", None) not in wanted
    ] + replacement
    return http_app


mcp = create_mcp_server()
app = build_http_app(mcp)
