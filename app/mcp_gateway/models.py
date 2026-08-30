from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class ToolEnvelope(BaseModel):
    status: Literal["ok", "queued", "unavailable"]
    data: dict[str, Any] | list[dict[str, Any]] | None = None
    as_of: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    source: str = "LEAGUEPILOT CloudPod"
    data_quality: Literal["live", "cached", "stale", "missing"] = "live"
    warnings: list[str] = Field(default_factory=list)
    missing_fields: list[str] = Field(default_factory=list)
    next_actions: list[str] = Field(default_factory=list)
    correlation_id: str


class AuthenticatedUser(BaseModel):
    id: str
    email: str | None = None


class CollectionPage(BaseModel):
    items: list[dict[str, Any]] = Field(default_factory=list)
    page: int = 1
    per_page: int = 0
    total_items: int = 0
