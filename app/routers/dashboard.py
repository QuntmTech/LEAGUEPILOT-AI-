from __future__ import annotations

import json
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Request
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.dependencies import get_db, require_workspace
from app.models import EspnConnection, Recommendation, Workspace
from app.services.analysis import power_rankings
from app.services.store import latest_snapshot_record, recommendation_view

router = APIRouter(prefix="/api/workspaces/{workspace_id}", tags=["dashboard"])


@router.get("/dashboard")
def dashboard(
    request: Request,
    workspace: Workspace = Depends(require_workspace),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    connection = db.scalar(
        select(EspnConnection)
        .where(EspnConnection.workspace_id == workspace.id)
        .order_by(desc(EspnConnection.updated_at))
        .limit(1)
    )
    snapshot_record = latest_snapshot_record(db, workspace.id)
    recommendations = db.scalars(
        select(Recommendation)
        .where(
            Recommendation.workspace_id == workspace.id,
            Recommendation.status == "proposed",
        )
        .order_by(desc(Recommendation.created_at))
        .limit(12)
    ).all()
    payload: dict[str, object] = {
        "workspace": {"id": workspace.id, "name": workspace.name, "plan": workspace.plan},
        "demo": request.app.state.settings.demo_mode,
        "intelligence_mode": request.app.state.settings.ai_provider,
        "connected": connection is not None and connection.status == "connected",
        "connection": None
        if connection is None
        else {
            "id": connection.id,
            "league_id": connection.league_id,
            "league_name": connection.league_name,
            "season": connection.season,
            "status": connection.status,
            "last_error": connection.last_error,
            "last_synced_at": connection.last_synced_at,
        },
        "recommendations": [
            recommendation_view(record).model_dump(mode="json") for record in recommendations
        ],
        "league": None,
        "power_rankings": [],
        "data_quality": {
            "status": "not_connected",
            "projection_coverage_percent": 0,
            "snapshot_age_seconds": None,
            "free_agent_count": 0,
        },
    }
    if snapshot_record is not None:
        from app.schemas import LeagueSnapshot

        snapshot = LeagueSnapshot.model_validate_json(snapshot_record.payload_json)
        my_team = snapshot.my_team
        matchup = next(
            (
                game
                for game in snapshot.matchups
                if my_team.id in {game.home_team_id, game.away_team_id}
            ),
            None,
        )
        payload["league"] = {
            "name": snapshot.league_name,
            "week": snapshot.week,
            "season": snapshot.season,
            "team": my_team.model_dump(mode="json"),
            "matchup": None if matchup is None else matchup.model_dump(mode="json"),
            "fetched_at": snapshot.fetched_at,
        }
        payload["power_rankings"] = power_rankings(snapshot)
        roster = my_team.roster
        projected = sum(1 for player in roster if player.projected_points > 0)
        age_seconds = max(0, int((datetime.now(UTC) - snapshot.fetched_at).total_seconds()))
        stale_after = request.app.state.settings.snapshot_cache_minutes * 60 * 3
        payload["data_quality"] = {
            "status": (
                "demo"
                if request.app.state.settings.demo_mode and connection is None
                else "stale"
                if age_seconds > stale_after
                else "fresh"
            ),
            "projection_coverage_percent": round(projected / len(roster) * 100) if roster else 0,
            "snapshot_age_seconds": age_seconds,
            "free_agent_count": len(snapshot.free_agents),
        }
    return json.loads(json.dumps(payload, default=str))
