from __future__ import annotations

import json
from datetime import UTC, datetime

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.models import LeagueSnapshotRecord, Recommendation
from app.schemas import LeagueSnapshot, RecommendationView
from app.services.analysis import AnalysisResult


def save_snapshot(
    db: Session,
    *,
    workspace_id: str,
    connection_id: str | None,
    snapshot: LeagueSnapshot,
) -> LeagueSnapshotRecord:
    record = LeagueSnapshotRecord(
        workspace_id=workspace_id,
        connection_id=connection_id,
        week=snapshot.week,
        payload_json=snapshot.model_dump_json(),
        fetched_at=datetime.now(UTC),
    )
    db.add(record)
    db.commit()
    return record


def latest_snapshot_record(db: Session, workspace_id: str) -> LeagueSnapshotRecord | None:
    return db.scalar(
        select(LeagueSnapshotRecord)
        .where(LeagueSnapshotRecord.workspace_id == workspace_id)
        .order_by(desc(LeagueSnapshotRecord.fetched_at))
        .limit(1)
    )


def load_latest_snapshot(
    db: Session, workspace_id: str
) -> tuple[LeagueSnapshotRecord, LeagueSnapshot]:
    record = latest_snapshot_record(db, workspace_id)
    if record is None:
        raise LookupError("No league snapshot is available; connect and synchronize ESPN first")
    return record, LeagueSnapshot.model_validate_json(record.payload_json)


def replace_recommendations(
    db: Session,
    *,
    workspace_id: str,
    snapshot_id: str,
    kind: str,
    results: list[AnalysisResult],
) -> list[Recommendation]:
    existing = db.scalars(
        select(Recommendation).where(
            Recommendation.workspace_id == workspace_id,
            Recommendation.kind == kind,
            Recommendation.status == "proposed",
        )
    ).all()
    for recommendation in existing:
        recommendation.status = "superseded"
        recommendation.reviewed_at = datetime.now(UTC)

    records: list[Recommendation] = []
    for result in results:
        record = Recommendation(
            workspace_id=workspace_id,
            snapshot_id=snapshot_id,
            kind=result.kind,
            title=result.title,
            summary=result.summary,
            confidence=result.confidence,
            impact_points=str(result.impact_points),
            payload_json=json.dumps(result.payload, separators=(",", ":")),
        )
        db.add(record)
        records.append(record)
    db.commit()
    return records


def recommendation_view(record: Recommendation) -> RecommendationView:
    return RecommendationView(
        id=record.id,
        kind=record.kind,
        title=record.title,
        summary=record.summary,
        confidence=record.confidence,
        impact_points=float(record.impact_points),
        payload=json.loads(record.payload_json),
        status=record.status,
        created_at=record.created_at,
    )
