from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from app.cloud_worker import CloudWorkerSettings, build_completion
from app.demo import demo_snapshot
from app.services.cloudpod import CloudPodBackend, CloudPodBackendError

WORKER_KEY = "test-cloudpod-worker-key-with-more-than-32-characters"


def test_cloudpod_client_authenticates_worker_and_claims_job() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["X-LeaguePilot-Worker-Key"] == WORKER_KEY
        assert request.url.path == "/api/leaguepilot/internal/jobs/claim"
        assert json.loads(request.content) == {"worker_id": "worker-1"}
        return httpx.Response(200, json={"job": {"id": "abc123def456ghi"}})

    with CloudPodBackend(
        base_url="https://leaguepilot-ai.cloudpod.pro",
        worker_key=WORKER_KEY,
        transport=httpx.MockTransport(handler),
    ) as backend:
        assert backend.claim(worker_id="worker-1") == {"id": "abc123def456ghi"}


def test_cloudpod_client_never_echoes_error_response_body() -> None:
    secret = "private-cookie-that-must-not-escape"

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": secret})

    with CloudPodBackend(
        base_url="https://leaguepilot-ai.cloudpod.pro",
        worker_key=WORKER_KEY,
        transport=httpx.MockTransport(handler),
    ) as backend:
        with pytest.raises(CloudPodBackendError) as caught:
            backend.claim(worker_id="worker-1")
    assert secret not in str(caught.value)
    assert "HTTP 500" in str(caught.value)


def test_worker_builds_bounded_full_completion_without_credentials() -> None:
    snapshot = demo_snapshot(2026)

    class FakeGateway:
        def fetch_snapshot(self, **_: object):
            return snapshot

    settings = CloudWorkerSettings(
        _env_file=None,
        cloudpod_url="https://leaguepilot-ai.cloudpod.pro",
        cloudpod_worker_key=WORKER_KEY,
        cloudpod_worker_id="worker-1",
    )
    job = {
        "id": "abc123def456ghi",
        "kind": "full",
        "lease_token": "lease-token",
        "connection": {
            "league_id": 123,
            "team_id": snapshot.my_team_id,
            "season": 2026,
            "credentials": {"espn_s2": "private-cookie", "swid": "{private-swid}"},
        },
    }

    completion = build_completion(job, gateway=FakeGateway(), settings=settings)  # type: ignore[arg-type]

    serialized = json.dumps(completion)
    assert "private-cookie" not in serialized
    assert "private-swid" not in serialized
    assert len(completion["snapshot"]["content_hash"]) == 64
    assert completion["recommendations"]
    assert completion["report"]["narration_mode"] == "rules"
    assert all(
        item["payload"]["execution_capability"] == "approval-only"
        for item in completion["recommendations"]
    )


def test_worker_settings_reject_insecure_cloudpod_url() -> None:
    with pytest.raises(ValueError, match="HTTPS"):
        CloudWorkerSettings(
            _env_file=None,
            cloudpod_url="http://leaguepilot-ai.cloudpod.pro",
            cloudpod_worker_key=WORKER_KEY,
        )


def test_cloudpod_hook_requires_explicit_connection_for_multi_league_analysis() -> None:
    source = Path("cloudpod/pb_hooks/leaguepilot.pb.js").read_text()

    assert "connection_id is required when a workspace has multiple leagues" in source
    assert '"inactive-sweep"' in source
    assert 'kind: "notification"' in source


def test_cloudpod_schema_allows_availability_jobs_and_alerts() -> None:
    schema = json.loads(Path("cloudpod/schema/collections.json").read_text())
    values_by_collection_and_field = {
        (collection["name"], field["name"]): field.get("values", [])
        for collection in schema["collections"]
        for field in collection.get("fields", [])
    }

    assert "inactive-sweep" in values_by_collection_and_field[("job_runs", "kind")]
    assert "availability-alert" in values_by_collection_and_field[("recommendations", "kind")]
