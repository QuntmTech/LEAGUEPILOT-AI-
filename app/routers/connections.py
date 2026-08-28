from __future__ import annotations

import json
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings
from app.dependencies import get_db, get_principal, require_workspace
from app.models import AuditEvent, EspnConnection, Workspace
from app.schemas import ConnectionView, EspnConnectionUpsert
from app.security import Principal, SecretBox
from app.services.espn import EspnGateway, EspnGatewayError
from app.services.store import save_snapshot

router = APIRouter(prefix="/api/workspaces/{workspace_id}/connections", tags=["connections"])


def _view(connection: EspnConnection) -> ConnectionView:
    return ConnectionView(
        id=connection.id,
        league_id=connection.league_id,
        team_id=connection.team_id,
        season=connection.season,
        is_public=connection.is_public,
        league_name=connection.league_name,
        status=connection.status,
        last_error=connection.last_error,
        last_synced_at=connection.last_synced_at,
    )


@router.get("/espn", response_model=list[ConnectionView])
def list_connections(
    _: Workspace = Depends(require_workspace),
    db: Session = Depends(get_db),
) -> list[ConnectionView]:
    records = db.scalars(
        select(EspnConnection)
        .where(EspnConnection.workspace_id == _.id)
        .order_by(EspnConnection.created_at)
    ).all()
    return [_view(record) for record in records]


@router.put("/espn", response_model=ConnectionView)
def upsert_connection(
    payload: EspnConnectionUpsert,
    request: Request,
    workspace: Workspace = Depends(require_workspace),
    principal: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
) -> ConnectionView:
    settings: Settings = request.app.state.settings
    connection = db.scalar(
        select(EspnConnection).where(
            EspnConnection.workspace_id == workspace.id,
            EspnConnection.league_id == payload.league_id,
            EspnConnection.season == payload.season,
        )
    )
    if connection is None:
        connection = db.scalar(
            select(EspnConnection)
            .where(EspnConnection.workspace_id == workspace.id)
            .order_by(EspnConnection.created_at)
            .limit(1)
        )
    if bool(payload.espn_s2) != bool(payload.swid):
        raise HTTPException(status_code=422, detail="Provide both espn_s2 and SWID together")
    has_new_credentials = bool(payload.espn_s2 and payload.swid)
    has_saved_credentials = bool(connection and connection.credentials_ciphertext)
    if not payload.is_public and not has_new_credentials and not has_saved_credentials:
        raise HTTPException(status_code=422, detail="Private ESPN leagues require espn_s2 and SWID")
    if settings.encryption_key is None and not payload.is_public:
        raise HTTPException(status_code=503, detail="Credential encryption is not configured")
    if connection is None:
        connection = EspnConnection(
            workspace_id=workspace.id,
            league_id=payload.league_id,
            team_id=payload.team_id,
            season=payload.season,
        )
        db.add(connection)
        db.flush()

    connection.league_id = payload.league_id
    connection.team_id = payload.team_id
    connection.season = payload.season
    connection.is_public = payload.is_public
    connection.status = "pending"
    connection.last_error = None
    if payload.is_public:
        connection.credentials_ciphertext = None
    elif has_new_credentials:
        secret_box = SecretBox(settings.encryption_key.get_secret_value())  # type: ignore[union-attr]
        connection.credentials_ciphertext = secret_box.seal_json(
            {"espn_s2": payload.espn_s2, "swid": payload.swid},
            context=f"espn:{workspace.id}:{connection.id}",
        )
    db.add(
        AuditEvent(
            workspace_id=workspace.id,
            actor_user_id=principal.user.id,
            action="connection.espn.saved",
            target_type="espn_connection",
            target_id=connection.id,
            details_json=json.dumps(
                {"league_id": connection.league_id, "season": connection.season}
            ),
        )
    )
    db.commit()
    return _view(connection)


@router.post("/espn/{connection_id}/sync")
def sync_connection(
    connection_id: str,
    request: Request,
    workspace: Workspace = Depends(require_workspace),
    principal: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    connection = db.scalar(
        select(EspnConnection).where(
            EspnConnection.id == connection_id,
            EspnConnection.workspace_id == workspace.id,
        )
    )
    if connection is None:
        raise HTTPException(status_code=404, detail="ESPN connection not found")
    settings: Settings = request.app.state.settings
    credentials: dict[str, object] = {}
    if connection.credentials_ciphertext:
        if settings.encryption_key is None:
            raise HTTPException(status_code=503, detail="Credential encryption is not configured")
        credentials = SecretBox(settings.encryption_key.get_secret_value()).open_json(
            connection.credentials_ciphertext,
            context=f"espn:{workspace.id}:{connection.id}",
        )
    gateway = EspnGateway(settings.espn_timeout_seconds)
    try:
        snapshot = gateway.fetch_snapshot(
            league_id=connection.league_id,
            team_id=connection.team_id,
            season=connection.season,
            espn_s2=str(credentials.get("espn_s2") or "") or None,
            swid=str(credentials.get("swid") or "") or None,
        )
        record = save_snapshot(
            db,
            workspace_id=workspace.id,
            connection_id=connection.id,
            snapshot=snapshot,
        )
        connection.league_name = snapshot.league_name
        connection.status = "connected"
        connection.last_error = None
        connection.last_synced_at = datetime.now(UTC)
        db.add(
            AuditEvent(
                workspace_id=workspace.id,
                actor_user_id=principal.user.id,
                action="connection.espn.synced",
                target_type="league_snapshot",
                target_id=record.id,
                details_json=json.dumps({"week": snapshot.week}),
            )
        )
        db.commit()
        return {
            "connected": True,
            "snapshot_id": record.id,
            "league_name": snapshot.league_name,
            "week": snapshot.week,
        }
    except EspnGatewayError as exc:
        connection.status = "error"
        connection.last_error = str(exc)[:500]
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=connection.last_error,
        ) from exc
