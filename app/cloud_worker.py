from __future__ import annotations

import hashlib
import json
import logging
import re
import socket
import time
from dataclasses import asdict
from datetime import UTC, timedelta
from typing import Any, Literal
from urllib.parse import urlsplit

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.services.ai import RulesNarrator, build_narrator
from app.services.analysis import analyze_lineup, analyze_trades, analyze_waivers
from app.services.cloudpod import CloudPodBackend
from app.services.espn import EspnGateway, EspnGatewayError
from app.services.reports import build_weekly_report_resilient

logger = logging.getLogger(__name__)


class CloudWorkerSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", ".env.local"),
        env_prefix="FCC_",
        extra="ignore",
    )

    cloudpod_url: str = ""
    cloudpod_worker_key: SecretStr | None = None
    cloudpod_worker_id: str = Field(default_factory=lambda: socket.gethostname()[:80])
    worker_poll_seconds: float = Field(default=3.0, ge=0.25, le=60.0)
    worker_request_timeout_seconds: float = Field(default=30.0, ge=5.0, le=120.0)
    espn_timeout_seconds: float = Field(default=20.0, ge=5.0, le=60.0)
    ai_provider: Literal["rules", "gemini", "openai-compatible"] = "rules"
    ai_model: str = ""
    ai_api_key: SecretStr | None = None
    ai_base_url: str = ""
    ai_timeout_seconds: float = Field(default=18.0, ge=3.0, le=60.0)
    max_ai_input_chars: int = Field(default=18_000, ge=2_000, le=50_000)

    @model_validator(mode="after")
    def validate_worker(self) -> CloudWorkerSettings:
        parsed = urlsplit(self.cloudpod_url)
        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("FCC_CLOUDPOD_URL must be a credential-free HTTPS origin")
        if (
            self.cloudpod_worker_key is None
            or len(self.cloudpod_worker_key.get_secret_value()) < 32
        ):
            raise ValueError("FCC_CLOUDPOD_WORKER_KEY must contain at least 32 characters")
        if not re.fullmatch(r"[A-Za-z0-9._-]{1,120}", self.cloudpod_worker_id):
            raise ValueError("FCC_CLOUDPOD_WORKER_ID contains unsupported characters")
        return self


class WorkerJobError(RuntimeError):
    def __init__(self, message: str, *, retryable: bool) -> None:
        super().__init__(message)
        self.retryable = retryable


def build_completion(
    job: dict[str, Any],
    *,
    gateway: EspnGateway,
    settings: CloudWorkerSettings,
) -> dict[str, Any]:
    connection = job.get("connection")
    if not isinstance(connection, dict):
        raise WorkerJobError("Job is missing an ESPN connection", retryable=False)
    credentials = connection.get("credentials")
    if credentials is not None and not isinstance(credentials, dict):
        raise WorkerJobError("Job credentials are malformed", retryable=False)
    credentials = credentials or {}
    try:
        snapshot = gateway.fetch_snapshot(
            league_id=_positive_int(connection.get("league_id"), "league ID"),
            team_id=_positive_int(connection.get("team_id"), "team ID"),
            season=_positive_int(connection.get("season"), "season"),
            espn_s2=_optional_text(credentials.get("espn_s2")),
            swid=_optional_text(credentials.get("swid")),
        )
    except EspnGatewayError as exc:
        message = _safe_error(exc)
        permanent = any(
            marker in message.lower()
            for marker in ("rejected", "did not find", "team id was not present")
        )
        raise WorkerJobError(message, retryable=not permanent) from exc

    kind = str(job.get("kind") or "")
    recommendations = []
    if kind in {"lineup", "full"}:
        recommendations.extend(analyze_lineup(snapshot))
    if kind in {"waivers", "full"}:
        recommendations.extend(analyze_waivers(snapshot))
    if kind in {"trades", "full"}:
        recommendations.extend(analyze_trades(snapshot))
    if kind not in {"sync", "lineup", "waivers", "trades", "weekly-report", "full"}:
        raise WorkerJobError("Unsupported job kind", retryable=False)

    report = None
    if kind in {"weekly-report", "full"}:
        try:
            narrator = build_narrator(settings)  # CloudWorkerSettings intentionally duck-types.
        except ValueError:
            narrator = RulesNarrator()
        body, metrics, narration_mode = build_weekly_report_resilient(snapshot, narrator)
        report = {
            "week": snapshot.week,
            "title": f"Week {snapshot.week}: {snapshot.league_name} Intelligence Brief",
            "body_markdown": body,
            "metrics": metrics,
            "narration_mode": narration_mode,
        }

    snapshot_payload = snapshot.model_dump(mode="json")
    canonical = json.dumps(snapshot_payload, sort_keys=True, separators=(",", ":"))
    fetched_at = snapshot.fetched_at.astimezone(UTC)
    return {
        "lease_token": _required_text(job.get("lease_token"), "lease token"),
        "snapshot": {
            "week": snapshot.week,
            "payload": snapshot_payload,
            "content_hash": hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
            "schema_version": 1,
            "fetched_at": fetched_at.isoformat(),
            "expires_at": (fetched_at + timedelta(minutes=15)).isoformat(),
        },
        "recommendations": [asdict(item) for item in recommendations],
        "report": report,
        "league_name": snapshot.league_name,
        "connection_status": "connected",
        "result": {
            "kind": kind,
            "recommendation_count": len(recommendations),
            "report_created": report is not None,
        },
    }


def run_worker(settings: CloudWorkerSettings, *, once: bool = False) -> int:
    worker_key = settings.cloudpod_worker_key
    if worker_key is None:  # Kept as a defensive guard for non-Pydantic construction.
        raise ValueError("FCC_CLOUDPOD_WORKER_KEY is required")
    gateway = EspnGateway(timeout_seconds=settings.espn_timeout_seconds)
    next_heartbeat = 0.0
    with CloudPodBackend(
        base_url=settings.cloudpod_url,
        worker_key=worker_key.get_secret_value(),
        timeout_seconds=settings.worker_request_timeout_seconds,
    ) as backend:
        while True:
            if time.monotonic() >= next_heartbeat:
                backend.heartbeat(worker_id=settings.cloudpod_worker_id)
                next_heartbeat = time.monotonic() + 30.0
            job = backend.claim(worker_id=settings.cloudpod_worker_id)
            if job is None:
                if once:
                    return 0
                time.sleep(settings.worker_poll_seconds)
                continue
            job_id = _required_text(job.get("id"), "job ID")
            lease_token = _required_text(job.get("lease_token"), "lease token")
            try:
                completion = build_completion(job, gateway=gateway, settings=settings)
                backend.complete(job_id=job_id, payload=completion)
            except WorkerJobError as exc:
                backend.fail(
                    job_id=job_id,
                    lease_token=lease_token,
                    error=_safe_error(exc),
                    retryable=exc.retryable,
                )
                if once:
                    return 1
            except Exception as exc:
                logger.exception("Cloud worker job failed", extra={"job_id": job_id})
                backend.fail(
                    job_id=job_id,
                    lease_token=lease_token,
                    error=_safe_error(exc),
                    retryable=True,
                )
                if once:
                    return 1
            else:
                if once:
                    return 0


def _positive_int(value: object, label: str) -> int:
    if isinstance(value, bool):
        raise WorkerJobError(f"Invalid {label}", retryable=False)
    try:
        result = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError) as exc:
        raise WorkerJobError(f"Invalid {label}", retryable=False) from exc
    if result <= 0:
        raise WorkerJobError(f"Invalid {label}", retryable=False)
    return result


def _required_text(value: object, label: str) -> str:
    result = str(value or "").strip()
    if not result:
        raise WorkerJobError(f"Missing {label}", retryable=False)
    return result


def _optional_text(value: object) -> str | None:
    result = str(value or "").strip()
    return result or None


def _safe_error(exc: Exception) -> str:
    message = " ".join(str(exc).replace("\x00", "").split())
    return (message or exc.__class__.__name__)[:500]
