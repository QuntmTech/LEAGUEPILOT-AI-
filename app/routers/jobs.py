from __future__ import annotations

import hmac
import json
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings
from app.dependencies import get_db
from app.models import (
    AuditEvent,
    EspnConnection,
    NotificationChannel,
    Report,
)
from app.schemas import JobRunRequest
from app.security import SecretBox
from app.services.analysis import analyze_lineup, analyze_trades, analyze_waivers
from app.services.espn import EspnGateway, EspnGatewayError
from app.services.notifications import NotificationError, deliver
from app.services.reports import build_configured_weekly_report
from app.services.store import replace_recommendations, save_snapshot

router = APIRouter(prefix="/api/internal/jobs", tags=["jobs"])


@router.post("/run")
def run_job(
    payload: JobRunRequest,
    request: Request,
    x_job_token: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    settings: Settings = request.app.state.settings
    configured_token = settings.job_token.get_secret_value() if settings.job_token else None
    if not configured_token:
        raise HTTPException(status_code=503, detail="Scheduled jobs are not configured")
    if not x_job_token or not hmac.compare_digest(x_job_token, configured_token):
        raise HTTPException(status_code=401, detail="Invalid job token")

    connections = db.scalars(
        select(EspnConnection).where(EspnConnection.status.in_(["connected", "pending", "error"]))
    ).all()
    outcomes: list[dict[str, object]] = []
    for connection in connections:
        try:
            outcomes.append(_run_for_connection(db, settings, connection, payload))
        except Exception as exc:
            connection.status = "error"
            connection.last_error = str(exc)[:500]
            db.add(
                AuditEvent(
                    workspace_id=connection.workspace_id,
                    actor_user_id=None,
                    action="job.failed",
                    target_type="espn_connection",
                    target_id=connection.id,
                    details_json=json.dumps({"kind": payload.kind, "error": str(exc)[:300]}),
                )
            )
            db.commit()
            outcomes.append(
                {
                    "workspace_id": connection.workspace_id,
                    "status": "failed",
                    "error": str(exc)[:300],
                }
            )
    return {
        "kind": payload.kind,
        "workspace_count": len(outcomes),
        "outcomes": outcomes,
    }


def _run_for_connection(
    db: Session,
    settings: Settings,
    connection: EspnConnection,
    request: JobRunRequest,
) -> dict[str, object]:
    credentials: dict[str, object] = {}
    if connection.credentials_ciphertext:
        if settings.encryption_key is None:
            raise RuntimeError("Credential encryption is not configured")
        credentials = SecretBox(settings.encryption_key.get_secret_value()).open_json(
            connection.credentials_ciphertext,
            context=f"espn:{connection.workspace_id}:{connection.id}",
        )
    try:
        snapshot = EspnGateway(settings.espn_timeout_seconds).fetch_snapshot(
            league_id=connection.league_id,
            team_id=connection.team_id,
            season=connection.season,
            espn_s2=str(credentials.get("espn_s2") or "") or None,
            swid=str(credentials.get("swid") or "") or None,
        )
    except EspnGatewayError:
        raise

    snapshot_record = save_snapshot(
        db,
        workspace_id=connection.workspace_id,
        connection_id=connection.id,
        snapshot=snapshot,
    )
    connection.status = "connected"
    connection.league_name = snapshot.league_name
    connection.last_error = None
    connection.last_synced_at = datetime.now(UTC)

    analyzers = {
        "lineup": analyze_lineup,
        "waivers": analyze_waivers,
        "trades": analyze_trades,
    }
    selected = list(analyzers) if request.kind == "full" else [request.kind]
    summaries: list[str] = []
    recommendation_count = 0
    for kind in selected:
        if kind not in analyzers:
            continue
        results = analyzers[kind](snapshot)
        replace_recommendations(
            db,
            workspace_id=connection.workspace_id,
            snapshot_id=snapshot_record.id,
            kind=kind,
            results=results,
        )
        recommendation_count += len(results)
        summaries.extend(result.title for result in results[:3])

    if request.kind in {"weekly-report", "full"}:
        body, facts, narration_mode = build_configured_weekly_report(snapshot, settings)
        report = Report(
            workspace_id=connection.workspace_id,
            week=snapshot.week,
            title=f"Week {snapshot.week} League Pulse",
            body_markdown=body,
            metrics_json=json.dumps(facts, separators=(",", ":")),
        )
        db.add(report)
        summaries.append(report.title)
        summaries.append(f"Narration: {narration_mode}")

    delivery_results: list[dict[str, str]] = []
    if request.notify:
        delivery_results = _notify_channels(db, settings, connection.workspace_id, summaries)

    db.add(
        AuditEvent(
            workspace_id=connection.workspace_id,
            actor_user_id=None,
            action="job.completed",
            target_type="league_snapshot",
            target_id=snapshot_record.id,
            details_json=json.dumps(
                {
                    "kind": request.kind,
                    "recommendation_count": recommendation_count,
                    "deliveries": delivery_results,
                }
            ),
        )
    )
    db.commit()
    return {
        "workspace_id": connection.workspace_id,
        "status": "completed",
        "week": snapshot.week,
        "recommendation_count": recommendation_count,
        "deliveries": delivery_results,
    }


def _notify_channels(
    db: Session,
    settings: Settings,
    workspace_id: str,
    summaries: list[str],
) -> list[dict[str, str]]:
    if not summaries or settings.encryption_key is None:
        return []
    channels = db.scalars(
        select(NotificationChannel).where(
            NotificationChannel.workspace_id == workspace_id,
            NotificationChannel.is_active.is_(True),
        )
    ).all()
    output: list[dict[str, str]] = []
    message = "LEAGUEPILOT AI update\n\n" + "\n".join(f"• {item}" for item in summaries[:8])
    for channel in channels:
        secret = SecretBox(settings.encryption_key.get_secret_value()).open_json(
            channel.target_ciphertext,
            context=f"notification:{workspace_id}:{channel.id}",
        )
        try:
            deliver(channel.kind, str(secret["target"]), message)
            output.append({"channel_id": channel.id, "status": "delivered"})
        except NotificationError as exc:
            output.append({"channel_id": channel.id, "status": f"failed: {str(exc)[:120]}"})
    return output
