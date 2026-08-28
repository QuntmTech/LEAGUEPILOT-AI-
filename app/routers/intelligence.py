from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.dependencies import get_db, get_principal, require_workspace
from app.models import AuditEvent, Recommendation, Workspace
from app.schemas import RecommendationDecision, RecommendationView
from app.security import Principal
from app.services.analysis import analyze_lineup, analyze_trades, analyze_waivers
from app.services.store import (
    load_latest_snapshot,
    recommendation_view,
    replace_recommendations,
)

router = APIRouter(prefix="/api/workspaces/{workspace_id}", tags=["intelligence"])
AnalysisKind = Literal["lineup", "waivers", "trades"]


@router.post("/analyses/{kind}", response_model=list[RecommendationView])
def run_analysis(
    kind: AnalysisKind,
    workspace: Workspace = Depends(require_workspace),
    principal: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
) -> list[RecommendationView]:
    try:
        snapshot_record, snapshot = load_latest_snapshot(db, workspace.id)
    except LookupError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    analyzers = {
        "lineup": analyze_lineup,
        "waivers": analyze_waivers,
        "trades": analyze_trades,
    }
    results = analyzers[kind](snapshot)
    records = replace_recommendations(
        db,
        workspace_id=workspace.id,
        snapshot_id=snapshot_record.id,
        kind=kind,
        results=results,
    )
    db.add(
        AuditEvent(
            workspace_id=workspace.id,
            actor_user_id=principal.user.id,
            action=f"analysis.{kind}.completed",
            target_type="league_snapshot",
            target_id=snapshot_record.id,
            details_json=json.dumps({"recommendation_count": len(records)}),
        )
    )
    db.commit()
    return [recommendation_view(record) for record in records]


@router.get("/recommendations", response_model=list[RecommendationView])
def list_recommendations(
    kind: str | None = None,
    workspace: Workspace = Depends(require_workspace),
    db: Session = Depends(get_db),
) -> list[RecommendationView]:
    query = select(Recommendation).where(Recommendation.workspace_id == workspace.id)
    if kind:
        query = query.where(Recommendation.kind == kind)
    records = db.scalars(query.order_by(desc(Recommendation.created_at)).limit(100)).all()
    return [recommendation_view(record) for record in records]


@router.post("/recommendations/{recommendation_id}/decision", response_model=RecommendationView)
def decide_recommendation(
    recommendation_id: str,
    payload: RecommendationDecision,
    workspace: Workspace = Depends(require_workspace),
    principal: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
) -> RecommendationView:
    recommendation = db.scalar(
        select(Recommendation).where(
            Recommendation.id == recommendation_id,
            Recommendation.workspace_id == workspace.id,
        )
    )
    if recommendation is None:
        raise HTTPException(status_code=404, detail="Recommendation not found")
    if recommendation.status != "proposed":
        raise HTTPException(status_code=409, detail="Recommendation was already reviewed")
    recommendation.status = payload.decision
    recommendation.reviewed_at = datetime.now(UTC)
    db.add(
        AuditEvent(
            workspace_id=workspace.id,
            actor_user_id=principal.user.id,
            action=f"recommendation.{payload.decision}",
            target_type="recommendation",
            target_id=recommendation.id,
            details_json=json.dumps({"execution_performed": False}),
        )
    )
    db.commit()
    return recommendation_view(recommendation)
