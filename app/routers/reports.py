from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.config import Settings
from app.dependencies import get_db, get_principal, require_workspace
from app.models import AuditEvent, Report, Workspace
from app.security import Principal
from app.services.reports import build_configured_weekly_report
from app.services.store import load_latest_snapshot

router = APIRouter(prefix="/api/workspaces/{workspace_id}/reports", tags=["reports"])


@router.post("/weekly")
def create_weekly_report(
    request: Request,
    workspace: Workspace = Depends(require_workspace),
    principal: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    try:
        _, snapshot = load_latest_snapshot(db, workspace.id)
    except LookupError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    settings: Settings = request.app.state.settings
    body, facts, narration_mode = build_configured_weekly_report(snapshot, settings)
    report = Report(
        workspace_id=workspace.id,
        week=snapshot.week,
        title=f"Week {snapshot.week} League Pulse",
        body_markdown=body,
        metrics_json=json.dumps(facts, separators=(",", ":")),
    )
    db.add(report)
    db.flush()
    db.add(
        AuditEvent(
            workspace_id=workspace.id,
            actor_user_id=principal.user.id,
            action="report.weekly.created",
            target_type="report",
            target_id=report.id,
            details_json=json.dumps(
                {"ai_provider": settings.ai_provider, "narration_mode": narration_mode}
            ),
        )
    )
    db.commit()
    return {
        "id": report.id,
        "title": report.title,
        "week": report.week,
        "body_markdown": report.body_markdown,
        "created_at": report.created_at,
        "narration_mode": narration_mode,
    }


@router.get("")
def list_reports(
    workspace: Workspace = Depends(require_workspace),
    db: Session = Depends(get_db),
) -> list[dict[str, object]]:
    reports = db.scalars(
        select(Report)
        .where(Report.workspace_id == workspace.id)
        .order_by(desc(Report.created_at))
        .limit(30)
    ).all()
    return [
        {
            "id": report.id,
            "title": report.title,
            "week": report.week,
            "body_markdown": report.body_markdown,
            "created_at": report.created_at,
        }
        for report in reports
    ]
