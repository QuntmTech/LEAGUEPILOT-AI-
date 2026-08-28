from __future__ import annotations

import re
from types import TracebackType
from typing import Any, Self
from urllib.parse import urlsplit

import httpx

from app.meta import VERSION

_RECORD_ID = re.compile(r"^[a-z0-9]{15}$")


class CloudPodBackendError(RuntimeError):
    """A sanitized control-plane error that never includes response bodies."""


class CloudPodBackend:
    """Worker-only client for LEAGUEPILOT's PocketBase control plane."""

    def __init__(
        self,
        *,
        base_url: str,
        worker_key: str,
        timeout_seconds: float = 30.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        parsed = urlsplit(base_url)
        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("CloudPod URL must be a credential-free HTTPS origin")
        if len(worker_key) < 32:
            raise ValueError("CloudPod worker key must contain at least 32 characters")
        self._client = httpx.Client(
            base_url=base_url.rstrip("/"),
            headers={
                "X-LeaguePilot-Worker-Key": worker_key,
                "User-Agent": f"LeaguePilotAI-Worker/{VERSION}",
            },
            timeout=httpx.Timeout(timeout_seconds),
            follow_redirects=False,
            trust_env=False,
            transport=transport,
        )

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()

    def close(self) -> None:
        self._client.close()

    def heartbeat(
        self,
        *,
        worker_id: str,
        status: str = "online",
        active_jobs: int = 0,
    ) -> None:
        self._post(
            "/api/leaguepilot/internal/workers/heartbeat",
            {
                "worker_id": worker_id,
                "status": status,
                "version": VERSION,
                "active_jobs": max(0, active_jobs),
                "metadata": {"capability": "espn-read-only"},
            },
        )

    def claim(self, *, worker_id: str) -> dict[str, Any] | None:
        response = self._post(
            "/api/leaguepilot/internal/jobs/claim",
            {"worker_id": worker_id},
        )
        job = response.get("job")
        if job is None:
            return None
        if not isinstance(job, dict):
            raise CloudPodBackendError("CloudPod returned an invalid job envelope")
        return job

    def complete(self, *, job_id: str, payload: dict[str, Any]) -> None:
        self._validate_record_id(job_id)
        self._post(f"/api/leaguepilot/internal/jobs/{job_id}/complete", payload)

    def fail(
        self,
        *,
        job_id: str,
        lease_token: str,
        error: str,
        retryable: bool,
    ) -> None:
        self._validate_record_id(job_id)
        self._post(
            f"/api/leaguepilot/internal/jobs/{job_id}/fail",
            {
                "lease_token": lease_token,
                "error": error[:1000],
                "retryable": retryable,
            },
        )

    def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            response = self._client.post(path, json=payload)
            response.raise_for_status()
            data = response.json()
        except httpx.HTTPStatusError as exc:
            raise CloudPodBackendError(
                f"CloudPod request failed with HTTP {exc.response.status_code}"
            ) from exc
        except (httpx.HTTPError, ValueError) as exc:
            raise CloudPodBackendError("CloudPod request failed") from exc
        if not isinstance(data, dict):
            raise CloudPodBackendError("CloudPod returned an invalid response")
        return data

    @staticmethod
    def _validate_record_id(record_id: str) -> None:
        if not _RECORD_ID.fullmatch(record_id):
            raise ValueError("Invalid PocketBase record ID")

