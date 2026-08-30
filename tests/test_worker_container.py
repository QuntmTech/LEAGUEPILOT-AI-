"""Deployment contract for the persistent worker container.

These assert the properties that make it safe to run alongside the GitHub Actions
fallback: no inbound exposure, no committed secret, a health check that does not reuse
the web API probe, and liveness driven by the drain loop itself.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def worker_dockerfile() -> str:
    return (ROOT / "Dockerfile.worker").read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def compose() -> str:
    return (ROOT / "docker-compose.yml").read_text(encoding="utf-8")


def test_worker_image_runs_the_worker_command(worker_dockerfile: str) -> None:
    assert 'CMD ["leaguepilot-ai", "worker"]' in worker_dockerfile


def test_worker_image_does_not_reuse_the_web_api_health_check(worker_dockerfile: str) -> None:
    """The main image probes :8765/api/health. This image serves no HTTP."""
    healthcheck = re.search(r"HEALTHCHECK[\s\S]*?CMD .*", worker_dockerfile)
    assert healthcheck, "worker image must define its own health check"
    body = healthcheck.group(0)
    assert "8765" not in body, "must not probe the web API port"
    assert "/api/health" not in body
    assert "heartbeat" in body, "liveness must come from the drain-loop heartbeat file"


def test_worker_image_exposes_no_port(worker_dockerfile: str) -> None:
    """Check for an EXPOSE *directive*, not the substring — prose may mention it."""
    directives = [
        line.strip()
        for line in worker_dockerfile.splitlines()
        if line.strip().upper().startswith("EXPOSE")
    ]
    assert directives == [], f"the worker is outbound-only, found: {directives}"


def test_worker_runs_as_a_non_root_user(worker_dockerfile: str) -> None:
    assert "USER app" in worker_dockerfile


def test_compose_worker_has_no_published_ports(compose: str) -> None:
    block = compose.split("leaguepilot-worker:", 1)[1].split("\nvolumes:", 1)[0]
    assert "ports:" not in block, "the worker must not publish a port"


def test_compose_worker_restarts_unless_stopped(compose: str) -> None:
    block = compose.split("leaguepilot-worker:", 1)[1].split("\nvolumes:", 1)[0]
    assert "restart: unless-stopped" in block


def test_compose_worker_never_inlines_the_worker_key(compose: str) -> None:
    """The key must come from the secret store, never from a committed file."""
    block = compose.split("leaguepilot-worker:", 1)[1].split("\nvolumes:", 1)[0]
    assignment = re.search(r"FCC_CLOUDPOD_WORKER_KEY\s*:\s*(\S+)", block)
    assert assignment is None, "worker key must not be assigned a value in compose"


def test_compose_worker_sets_required_configuration(compose: str) -> None:
    block = compose.split("leaguepilot-worker:", 1)[1].split("\nvolumes:", 1)[0]
    assert "https://leaguepilot-ai.cloudpod.pro" in block
    assert "FCC_CLOUDPOD_WORKER_ID" in block
    assert 'FCC_WORKER_POLL_SECONDS: "3"' in block


def test_poll_seconds_of_three_is_within_the_validated_range() -> None:
    from app.cloud_worker import CloudWorkerSettings

    field = CloudWorkerSettings.model_fields["worker_poll_seconds"]
    bounds = {type(m).__name__: getattr(m, "ge", getattr(m, "le", None)) for m in field.metadata}
    assert bounds.get("Ge", 0) <= 3.0
    assert bounds.get("Le", 60) >= 3.0


def test_worker_key_is_a_secret_type_so_it_cannot_leak_via_repr() -> None:
    from pydantic import SecretStr

    from app.cloud_worker import CloudWorkerSettings

    annotation = CloudWorkerSettings.model_fields["cloudpod_worker_key"].annotation
    assert SecretStr in getattr(annotation, "__args__", (annotation,))


def test_liveness_file_is_written_and_failures_are_swallowed(tmp_path) -> None:
    from app.cloud_worker import _touch_liveness

    target = tmp_path / "beat"
    _touch_liveness(str(target))
    assert target.exists(), "liveness file must be written"

    # An unwritable path must not raise: a bad temp dir cannot take down a healthy worker.
    _touch_liveness(str(tmp_path / "missing-dir" / "beat"))


def test_espn_errors_are_scrubbed_of_session_values() -> None:
    """Regression guard: ESPN failures must never carry credentials into logs."""
    source = (ROOT / "app" / "services" / "espn.py").read_text(encoding="utf-8")
    assert "[REDACTED]" in source
    assert "safe_message" in source
