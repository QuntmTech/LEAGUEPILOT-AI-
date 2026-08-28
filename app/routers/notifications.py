from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings
from app.dependencies import get_db, get_principal, require_workspace
from app.models import AuditEvent, NotificationChannel, Workspace
from app.schemas import NotificationChannelUpsert, NotificationChannelView
from app.security import Principal, SecretBox
from app.services.notifications import NotificationError, deliver

router = APIRouter(prefix="/api/workspaces/{workspace_id}/notifications", tags=["notifications"])


@router.get("", response_model=list[NotificationChannelView])
def list_channels(
    workspace: Workspace = Depends(require_workspace),
    db: Session = Depends(get_db),
) -> list[NotificationChannelView]:
    channels = db.scalars(
        select(NotificationChannel)
        .where(NotificationChannel.workspace_id == workspace.id)
        .order_by(NotificationChannel.created_at)
    ).all()
    return [
        NotificationChannelView(
            id=channel.id,
            kind=channel.kind,
            label=channel.label,
            is_active=channel.is_active,
            created_at=channel.created_at,
        )
        for channel in channels
    ]


@router.post("", response_model=NotificationChannelView)
def add_channel(
    payload: NotificationChannelUpsert,
    request: Request,
    workspace: Workspace = Depends(require_workspace),
    principal: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
) -> NotificationChannelView:
    settings: Settings = request.app.state.settings
    if settings.encryption_key is None:
        raise HTTPException(status_code=503, detail="Credential encryption is not configured")
    channel = NotificationChannel(
        workspace_id=workspace.id,
        kind=payload.kind,
        label=payload.label,
        target_ciphertext="pending",
    )
    db.add(channel)
    db.flush()
    channel.target_ciphertext = SecretBox(settings.encryption_key.get_secret_value()).seal_json(
        {"target": payload.target},
        context=f"notification:{workspace.id}:{channel.id}",
    )
    db.add(
        AuditEvent(
            workspace_id=workspace.id,
            actor_user_id=principal.user.id,
            action="notification.channel.created",
            target_type="notification_channel",
            target_id=channel.id,
            details_json=json.dumps({"kind": channel.kind, "label": channel.label}),
        )
    )
    db.commit()
    return NotificationChannelView(
        id=channel.id,
        kind=channel.kind,
        label=channel.label,
        is_active=channel.is_active,
        created_at=channel.created_at,
    )


@router.post("/{channel_id}/test")
def test_channel(
    channel_id: str,
    request: Request,
    workspace: Workspace = Depends(require_workspace),
    principal: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
) -> dict[str, bool]:
    channel = db.scalar(
        select(NotificationChannel).where(
            NotificationChannel.id == channel_id,
            NotificationChannel.workspace_id == workspace.id,
        )
    )
    if channel is None:
        raise HTTPException(status_code=404, detail="Notification channel not found")
    if not channel.is_active or channel.target_ciphertext == "disabled":
        raise HTTPException(status_code=409, detail="Notification channel is disabled")
    settings: Settings = request.app.state.settings
    if settings.encryption_key is None:
        raise HTTPException(status_code=503, detail="Credential encryption is not configured")
    secret = SecretBox(settings.encryption_key.get_secret_value()).open_json(
        channel.target_ciphertext,
        context=f"notification:{workspace.id}:{channel.id}",
    )
    try:
        deliver(
            channel.kind,
            str(secret["target"]),
            "LEAGUEPILOT AI is connected. Your league intelligence is ready. 🏈",
        )
    except NotificationError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    db.add(
        AuditEvent(
            workspace_id=workspace.id,
            actor_user_id=principal.user.id,
            action="notification.channel.tested",
            target_type="notification_channel",
            target_id=channel.id,
            details_json="{}",
        )
    )
    db.commit()
    return {"delivered": True}


@router.delete("/{channel_id}")
def disable_channel(
    channel_id: str,
    workspace: Workspace = Depends(require_workspace),
    principal: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
) -> dict[str, bool]:
    channel = db.scalar(
        select(NotificationChannel).where(
            NotificationChannel.id == channel_id,
            NotificationChannel.workspace_id == workspace.id,
        )
    )
    if channel is None:
        raise HTTPException(status_code=404, detail="Notification channel not found")
    channel.is_active = False
    channel.target_ciphertext = "disabled"
    db.add(
        AuditEvent(
            workspace_id=workspace.id,
            actor_user_id=principal.user.id,
            action="notification.channel.disabled",
            target_type="notification_channel",
            target_id=channel.id,
            details_json=json.dumps({"kind": channel.kind, "label": channel.label}),
        )
    )
    db.commit()
    return {"disabled": True}
