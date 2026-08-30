from __future__ import annotations

import uuid
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from typing import Any, Literal

from app.mcp_gateway.client import CloudPodClient, validate_record_id
from app.mcp_gateway.errors import McpInputError
from app.mcp_gateway.models import ToolEnvelope

ClientFactory = Callable[[str], CloudPodClient]
AnalysisKind = Literal["lineup", "waivers", "trades", "weekly-report", "inactive-sweep", "full"]
RecommendationKind = Literal["lineup", "waiver", "trade", "availability-alert"]


def _correlation_id() -> str:
    return uuid.uuid4().hex


def _filter(field: str, value: str) -> str:
    # All values passed here are either strict record IDs or fixed enums.
    return f'{field} = "{value}"'


def _warnings_from_snapshot(snapshot: Mapping[str, Any]) -> list[str]:
    payload = snapshot.get("payload")
    if not isinstance(payload, Mapping):
        return ["The snapshot payload is missing or invalid."]
    warnings = payload.get("data_quality_warnings")
    if not isinstance(warnings, list):
        return []
    return [str(item)[:300] for item in warnings if isinstance(item, str)]


def _snapshot_quality(snapshot: Mapping[str, Any]) -> Literal["live", "cached", "stale", "missing"]:
    expires_at = snapshot.get("expires_at")
    if not isinstance(expires_at, str) or not expires_at:
        return "cached"
    try:
        expiry = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
    except ValueError:
        return "stale"
    return "stale" if expiry <= datetime.now(UTC) else "cached"


class LeaguePilotMcpService:
    def __init__(self, client_factory: ClientFactory) -> None:
        self._client_factory = client_factory

    def _client(self, token: str) -> CloudPodClient:
        return self._client_factory(token)

    async def health(self, token: str) -> ToolEnvelope:
        data = await self._client(token).health()
        return ToolEnvelope(status="ok", data=data, correlation_id=_correlation_id())

    async def list_leagues(self, token: str) -> ToolEnvelope:
        client = self._client(token)
        bootstrap = await client.bootstrap()
        connections = await client.list_records(
            "espn_connections", sort="-last_synced_at", limit=50
        )
        return ToolEnvelope(
            status="ok",
            data={
                "profile": bootstrap.get("profile"),
                "workspace": bootstrap.get("workspace"),
                "connections": connections.items,
            },
            correlation_id=_correlation_id(),
            warnings=[
                "A connection marked expired may reflect a processing failure, not necessarily "
                "an ESPN login failure."
            ]
            if any(item.get("status") == "expired" for item in connections.items)
            else [],
        )

    async def latest_snapshot(
        self, token: str, workspace_id: str, connection_id: str | None = None
    ) -> ToolEnvelope:
        validate_record_id(workspace_id, "Workspace ID")
        filters = [_filter("workspace", workspace_id)]
        if connection_id:
            filters.append(
                _filter("connection", validate_record_id(connection_id, "Connection ID"))
            )
        page = await self._client(token).list_records(
            "league_snapshots", filters=filters, sort="-fetched_at", limit=1
        )
        if not page.items:
            return ToolEnvelope(
                status="unavailable",
                data=None,
                data_quality="missing",
                warnings=["No completed league snapshot exists for this scope."],
                missing_fields=["league_snapshot"],
                next_actions=["Call sync_league, then poll get_job_status."],
                correlation_id=_correlation_id(),
            )
        snapshot = page.items[0]
        return ToolEnvelope(
            status="ok",
            data=snapshot,
            as_of=str(snapshot.get("fetched_at") or ""),
            data_quality=_snapshot_quality(snapshot),
            warnings=_warnings_from_snapshot(snapshot),
            correlation_id=_correlation_id(),
        )

    async def roster(
        self,
        token: str,
        workspace_id: str,
        connection_id: str | None = None,
        team_id: int | None = None,
    ) -> ToolEnvelope:
        envelope = await self.latest_snapshot(token, workspace_id, connection_id)
        if envelope.status != "ok" or not isinstance(envelope.data, Mapping):
            return envelope
        payload = envelope.data.get("payload")
        if not isinstance(payload, Mapping):
            envelope.status = "unavailable"
            envelope.data_quality = "missing"
            envelope.missing_fields.append("snapshot.payload")
            return envelope
        selected_team = team_id if team_id is not None else payload.get("my_team_id")
        teams = payload.get("teams")
        if not isinstance(teams, list):
            envelope.status = "unavailable"
            envelope.data_quality = "missing"
            envelope.missing_fields.append("snapshot.payload.teams")
            return envelope
        team = next(
            (
                item
                for item in teams
                if isinstance(item, Mapping) and item.get("id") == selected_team
            ),
            None,
        )
        if not isinstance(team, Mapping):
            raise McpInputError("That team is not present in the latest league snapshot.")
        envelope.data = {
            "snapshot_id": envelope.data.get("id"),
            "league_id": payload.get("league_id"),
            "league_name": payload.get("league_name"),
            "season": payload.get("season"),
            "week": payload.get("week"),
            "team": dict(team),
            "roster_slots": payload.get("roster_slots", []),
        }
        return envelope

    async def matchup(
        self,
        token: str,
        workspace_id: str,
        connection_id: str | None = None,
        week: int | None = None,
    ) -> ToolEnvelope:
        envelope = await self.latest_snapshot(token, workspace_id, connection_id)
        if envelope.status != "ok" or not isinstance(envelope.data, Mapping):
            return envelope
        payload = envelope.data.get("payload")
        if not isinstance(payload, Mapping):
            envelope.status = "unavailable"
            envelope.data_quality = "missing"
            envelope.missing_fields.append("snapshot.payload")
            return envelope
        selected_week = week if week is not None else payload.get("week")
        my_team_id = payload.get("my_team_id")
        matchups = payload.get("matchups")
        if not isinstance(matchups, list):
            matchups = []
        scoped = [
            dict(item)
            for item in matchups
            if isinstance(item, Mapping)
            and item.get("week") == selected_week
            and my_team_id in {item.get("home_team_id"), item.get("away_team_id")}
        ]
        envelope.data = {
            "snapshot_id": envelope.data.get("id"),
            "league_id": payload.get("league_id"),
            "week": selected_week,
            "my_team_id": my_team_id,
            "matchups": scoped,
        }
        if not scoped:
            envelope.warnings.append(
                "No matchup for the configured team was present for that week."
            )
            envelope.missing_fields.append("matchup")
        return envelope

    async def draft_context(
        self, token: str, workspace_id: str, connection_id: str | None = None
    ) -> ToolEnvelope:
        envelope = await self.latest_snapshot(token, workspace_id, connection_id)
        if envelope.status != "ok" or not isinstance(envelope.data, Mapping):
            return envelope
        payload = envelope.data.get("payload")
        if not isinstance(payload, Mapping):
            envelope.status = "unavailable"
            envelope.data_quality = "missing"
            envelope.missing_fields.append("snapshot.payload")
            return envelope
        teams = payload.get("teams")
        my_team_id = payload.get("my_team_id")
        my_team = None
        if isinstance(teams, list):
            my_team = next(
                (
                    dict(item)
                    for item in teams
                    if isinstance(item, Mapping) and item.get("id") == my_team_id
                ),
                None,
            )
        envelope.data = {
            "snapshot_id": envelope.data.get("id"),
            "league_id": payload.get("league_id"),
            "league_name": payload.get("league_name"),
            "season": payload.get("season"),
            "roster_slots": payload.get("roster_slots", []),
            "my_team": my_team,
            "candidate_players": payload.get("free_agents", []),
        }
        envelope.warnings.insert(
            0,
            "This is snapshot-based decision support, not a live ESPN draft-room feed. "
            "Re-sync before relying on player availability.",
        )
        return envelope

    async def recommendations(
        self,
        token: str,
        workspace_id: str,
        *,
        status: str,
        kind: str | None,
        limit: int,
    ) -> ToolEnvelope:
        validate_record_id(workspace_id, "Workspace ID")
        filters = [_filter("workspace", workspace_id), _filter("status", status)]
        if kind:
            filters.append(_filter("kind", kind))
        page = await self._client(token).list_records(
            "recommendations", filters=filters, sort="-confidence", limit=limit
        )
        return ToolEnvelope(
            status="ok",
            data=page.items,
            data_quality="cached",
            warnings=[] if page.items else ["No matching recommendations are currently available."],
            correlation_id=_correlation_id(),
        )

    async def weekly_report(
        self, token: str, workspace_id: str, week: int | None = None
    ) -> ToolEnvelope:
        validate_record_id(workspace_id, "Workspace ID")
        filters = [_filter("workspace", workspace_id)]
        if week is not None:
            filters.append(f"week = {week}")
        page = await self._client(token).list_records(
            "reports", filters=filters, sort="-published_at", limit=1
        )
        if not page.items:
            return ToolEnvelope(
                status="unavailable",
                data=None,
                data_quality="missing",
                warnings=["No weekly report exists for that scope."],
                missing_fields=["weekly_report"],
                next_actions=["Call run_analysis with kind weekly-report or full."],
                correlation_id=_correlation_id(),
            )
        report = page.items[0]
        return ToolEnvelope(
            status="ok",
            data=report,
            as_of=str(report.get("published_at") or ""),
            data_quality="cached",
            correlation_id=_correlation_id(),
        )

    async def job_status(self, token: str, job_id: str) -> ToolEnvelope:
        record = await self._client(token).get_record(
            "job_runs", validate_record_id(job_id, "Job ID")
        )
        status = record.get("status")
        next_actions: list[str] = []
        if status in {"queued", "running"}:
            next_actions.append("Poll get_job_status until the job reaches a terminal state.")
        elif status == "succeeded":
            next_actions.append("Read the latest snapshot, recommendations, or report.")
        elif status in {"failed", "dead-letter"}:
            next_actions.append(
                "Inspect the safe last_error and retry only after the cause is resolved."
            )
        return ToolEnvelope(
            status="ok",
            data=record,
            data_quality="live",
            next_actions=next_actions,
            correlation_id=_correlation_id(),
        )

    async def sync(self, token: str, connection_id: str, confirmed: bool) -> ToolEnvelope:
        if not confirmed:
            raise McpInputError("Sync was not queued because confirmed must be true.")
        result = await self._client(token).sync(connection_id)
        return ToolEnvelope(
            status="queued",
            data=result,
            next_actions=[
                f"Poll get_job_status for job {result.get('job_id', 'returned by the backend')}."
            ],
            correlation_id=_correlation_id(),
        )

    async def analyze(
        self,
        token: str,
        workspace_id: str,
        *,
        kind: AnalysisKind,
        connection_id: str | None,
        notify: bool,
        confirmed: bool,
    ) -> ToolEnvelope:
        if not confirmed:
            raise McpInputError("Analysis was not queued because confirmed must be true.")
        result = await self._client(token).analyze(
            workspace_id, kind=kind, connection_id=connection_id, notify=notify
        )
        return ToolEnvelope(
            status="queued",
            data=result,
            next_actions=[
                f"Poll get_job_status for job {result.get('job_id', 'returned by the backend')}."
            ],
            correlation_id=_correlation_id(),
        )

    async def review(
        self,
        token: str,
        recommendation_id: str,
        decision: Literal["approved", "dismissed"],
        confirmed: bool,
    ) -> ToolEnvelope:
        if not confirmed:
            raise McpInputError(
                "The recommendation was not reviewed because confirmed must be true."
            )
        result = await self._client(token).review(recommendation_id, decision)
        warnings = []
        if result.get("espn_action_executed") is not False:
            warnings.append("The backend did not explicitly confirm the ESPN read-only boundary.")
        return ToolEnvelope(
            status="ok",
            data=result,
            warnings=warnings,
            next_actions=["No ESPN transaction was executed; this records the decision only."],
            correlation_id=_correlation_id(),
        )
