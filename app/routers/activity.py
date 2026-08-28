from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.dependencies import get_db, require_workspace
from app.models import AuditEvent, Workspace
from app.schemas import ActivityEventView

router = APIRouter(prefix="/api/workspaces/{workspace_id}/activity", tags=["activity"])


@router.get("", response_model=list[ActivityEventView])
def list_activity(
    limit: int = 30,
    workspace: Workspace = Depends(require_workspace),
    db: Session = Depends(get_db),
) -> list[ActivityEventView]:
    bounded_limit = max(1, min(limit, 100))
    events = db.scalars(
        select(AuditEvent)
        .where(AuditEvent.workspace_id == workspace.id)
        .order_by(desc(AuditEvent.created_at))
        .limit(bounded_limit)
    ).all()
    return [
        ActivityEventView(
            id=event.id,
            action=event.action,
            target_type=event.target_type,
            target_id=event.target_id,
            created_at=event.created_at,
        )
        for event in events
    ]
