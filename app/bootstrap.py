from __future__ import annotations

import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings
from app.demo import demo_snapshot
from app.models import ApiKey, AuditEvent, LeagueSnapshotRecord, Membership, User, Workspace
from app.security import digest_token


def bootstrap_founder_workspace(db: Session, settings: Settings) -> None:
    """Create the first local owner and API key without ever storing the raw token."""
    if settings.admin_token is None:
        return

    user = db.scalar(select(User).where(User.email == "founder@local.invalid"))
    if user is None:
        user = User(email="founder@local.invalid", display_name="Founder")
        db.add(user)
        db.flush()

    workspace = db.scalar(select(Workspace).where(Workspace.slug == "founder-league"))
    if workspace is None:
        workspace = Workspace(name="LeaguePilot League", slug="founder-league")
        db.add(workspace)
        db.flush()

    membership = db.scalar(
        select(Membership).where(
            Membership.user_id == user.id,
            Membership.workspace_id == workspace.id,
        )
    )
    if membership is None:
        db.add(Membership(user_id=user.id, workspace_id=workspace.id, role="owner"))

    token_digest = digest_token(settings.admin_token.get_secret_value())
    api_key = db.scalar(select(ApiKey).where(ApiKey.token_digest == token_digest))
    if api_key is None:
        db.add(ApiKey(user_id=user.id, token_digest=token_digest, name="Founder bootstrap"))
        db.add(
            AuditEvent(
                workspace_id=workspace.id,
                actor_user_id=user.id,
                action="bootstrap.completed",
                target_type="workspace",
                target_id=workspace.id,
                details_json=json.dumps({"environment": settings.environment}),
            )
        )
    demo_record = db.scalar(
        select(LeagueSnapshotRecord)
        .where(LeagueSnapshotRecord.workspace_id == workspace.id)
        .limit(1)
    )
    if settings.demo_mode and demo_record is None:
        snapshot = demo_snapshot(settings.default_season)
        db.add(
            LeagueSnapshotRecord(
                workspace_id=workspace.id,
                connection_id=None,
                week=snapshot.week,
                payload_json=snapshot.model_dump_json(),
                fetched_at=snapshot.fetched_at,
            )
        )
        db.add(
            AuditEvent(
                workspace_id=workspace.id,
                actor_user_id=user.id,
                action="demo.seeded",
                target_type="league_snapshot",
                target_id=str(snapshot.league_id),
                details_json=json.dumps({"fictional": True, "season": snapshot.season}),
            )
        )
    db.commit()
