from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import pytest

from app.mcp_gateway.errors import McpInputError
from app.mcp_gateway.models import CollectionPage
from app.mcp_gateway.service import LeaguePilotMcpService

WORKSPACE = "abc123abc123abc"
CONNECTION = "def456def456def"
SNAPSHOT = "ghi789ghi789ghi"
JOB = "job123job123job"
RECOMMENDATION = "rec123rec123rec"


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


class FakeClient:
    def __init__(self, snapshot_items: list[dict[str, Any]] | None = None) -> None:
        self.snapshot_items = snapshot_items or []
        self.calls: list[tuple[str, Any]] = []

    async def health(self) -> dict[str, Any]:
        return {"status": "ok", "queue": "available"}

    async def bootstrap(self) -> dict[str, Any]:
        return {"workspace": {"id": WORKSPACE}, "profile": {"display_name": "Manager"}}

    async def list_records(
        self,
        collection: str,
        *,
        filters: list[str] | None = None,
        sort: str = "",
        limit: int = 50,
    ) -> CollectionPage:
        self.calls.append((collection, {"filters": filters, "sort": sort, "limit": limit}))
        if collection == "league_snapshots":
            return CollectionPage(items=self.snapshot_items, total_items=len(self.snapshot_items))
        if collection == "espn_connections":
            return CollectionPage(
                items=[{"id": CONNECTION, "workspace": WORKSPACE, "status": "connected"}],
                total_items=1,
            )
        return CollectionPage(items=[], total_items=0)

    async def get_record(self, collection: str, record_id: str) -> dict[str, Any]:
        self.calls.append((collection, record_id))
        return {"id": record_id, "status": "succeeded", "kind": "sync"}

    async def sync(self, connection_id: str) -> dict[str, Any]:
        self.calls.append(("sync", connection_id))
        return {"queued": True, "job_id": JOB, "status": "queued"}

    async def analyze(
        self,
        workspace_id: str,
        *,
        kind: str,
        connection_id: str | None,
        notify: bool,
    ) -> dict[str, Any]:
        self.calls.append(("analyze", (workspace_id, kind, connection_id, notify)))
        return {"queued": True, "job_id": JOB, "status": "queued"}

    async def review(self, recommendation_id: str, decision: str) -> dict[str, Any]:
        self.calls.append(("review", (recommendation_id, decision)))
        return {
            "id": recommendation_id,
            "status": decision,
            "espn_action_executed": False,
        }


def make_snapshot() -> dict[str, Any]:
    return {
        "id": SNAPSHOT,
        "workspace": WORKSPACE,
        "connection": CONNECTION,
        "fetched_at": "2026-08-30T18:00:00Z",
        "payload": {
            "league_id": 1758896183,
            "league_name": "180wingz",
            "season": 2026,
            "week": 1,
            "my_team_id": 3,
            "roster_slots": ["QB", "RB", "RB", "WR", "WR", "TE", "FLEX"],
            "teams": [
                {
                    "id": 3,
                    "name": "MicroPeanKings704",
                    "roster": [{"id": "1", "name": "Christian McCaffrey", "position": "RB"}],
                }
            ],
            "free_agents": [{"id": "2", "name": "Candidate", "position": "WR"}],
            "matchups": [{"week": 1, "home_team_id": 3, "away_team_id": 4, "home_score": 0}],
            "data_quality_warnings": ["Projection source is preseason."],
        },
    }


@pytest.mark.anyio
async def test_missing_snapshot_is_explicit_and_actionable() -> None:
    fake = FakeClient()
    service = LeaguePilotMcpService(lambda _: fake)  # type: ignore[arg-type]
    result = await service.latest_snapshot("token", WORKSPACE, CONNECTION)
    assert result.status == "unavailable"
    assert result.data_quality == "missing"
    assert result.missing_fields == ["league_snapshot"]
    assert "sync_league" in result.next_actions[0]


@pytest.mark.anyio
async def test_roster_and_matchup_derive_only_from_normalized_snapshot() -> None:
    fake = FakeClient([make_snapshot()])
    service = LeaguePilotMcpService(lambda _: fake)  # type: ignore[arg-type]
    roster = await service.roster("token", WORKSPACE, connection_id=CONNECTION)
    matchup = await service.matchup("token", WORKSPACE, connection_id=CONNECTION)
    assert isinstance(roster.data, Mapping)
    assert roster.data["team"]["name"] == "MicroPeanKings704"
    assert isinstance(matchup.data, Mapping)
    assert matchup.data["matchups"][0]["away_team_id"] == 4
    assert roster.warnings == ["Projection source is preseason."]


@pytest.mark.anyio
async def test_draft_context_warns_that_availability_is_not_live() -> None:
    fake = FakeClient([make_snapshot()])
    service = LeaguePilotMcpService(lambda _: fake)  # type: ignore[arg-type]
    result = await service.draft_context("token", WORKSPACE, CONNECTION)
    assert "not a live ESPN draft-room feed" in result.warnings[0]
    assert isinstance(result.data, Mapping)
    assert result.data["candidate_players"][0]["name"] == "Candidate"


@pytest.mark.anyio
async def test_state_changing_tools_require_confirmation() -> None:
    fake = FakeClient([make_snapshot()])
    service = LeaguePilotMcpService(lambda _: fake)  # type: ignore[arg-type]
    with pytest.raises(McpInputError, match="confirmed"):
        await service.sync("token", CONNECTION, False)
    with pytest.raises(McpInputError, match="confirmed"):
        await service.analyze(
            "token",
            WORKSPACE,
            kind="full",
            connection_id=CONNECTION,
            notify=False,
            confirmed=False,
        )
    with pytest.raises(McpInputError, match="confirmed"):
        await service.review("token", RECOMMENDATION, "approved", False)
    assert fake.calls == []


@pytest.mark.anyio
async def test_review_records_decision_without_espn_execution() -> None:
    fake = FakeClient([make_snapshot()])
    service = LeaguePilotMcpService(lambda _: fake)  # type: ignore[arg-type]
    result = await service.review("token", RECOMMENDATION, "approved", True)
    assert isinstance(result.data, Mapping)
    assert result.data["espn_action_executed"] is False
    assert "No ESPN transaction" in result.next_actions[0]
