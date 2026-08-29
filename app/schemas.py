from __future__ import annotations

import re
from datetime import datetime
from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, Field, field_validator, model_validator


class AvailabilitySignal(BaseModel):
    """Provider-neutral availability evidence attached to a normalized player."""

    source: str = Field(min_length=1, max_length=40)
    week: int = Field(ge=0, le=30)
    practice_status: str | None = Field(default=None, max_length=80)
    game_status: str | None = Field(default=None, max_length=40)
    primary_injury: str | None = Field(default=None, max_length=120)
    confirmed_inactive: bool | None = None

    @field_validator("source", "practice_status", "game_status", "primary_injury")
    @classmethod
    def clean_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = " ".join(value.replace("\x00", "").split())
        return cleaned or None


class Player(BaseModel):
    id: str
    name: str
    position: str
    pro_team: str = "FA"
    projected_points: float = 0.0
    season_points: float = 0.0
    average_points: float = 0.0
    injury_status: str = "ACTIVE"
    current_slot: str = "BE"
    eligible_slots: list[str] = Field(default_factory=list)
    opponent: str = ""
    percent_owned: float = 0.0
    availability: AvailabilitySignal | None = None

    @field_validator("name", "position", "pro_team", "injury_status", "current_slot")
    @classmethod
    def bound_text(cls, value: str) -> str:
        return " ".join(value.replace("\x00", "").split())[:120]


class Team(BaseModel):
    id: int
    name: str
    owner: str = ""
    wins: int = 0
    losses: int = 0
    ties: int = 0
    points_for: float = 0.0
    projected_total: float = 0.0
    roster: list[Player] = Field(default_factory=list)

    @field_validator("name", "owner")
    @classmethod
    def bound_text(cls, value: str) -> str:
        return " ".join(value.replace("\x00", "").split())[:160]


class Matchup(BaseModel):
    week: int
    home_team_id: int
    away_team_id: int
    home_score: float = 0.0
    away_score: float = 0.0
    home_projected: float = 0.0
    away_projected: float = 0.0


class LeagueSnapshot(BaseModel):
    league_id: int
    league_name: str
    season: int
    week: int
    scoring_format: str = "Custom"
    my_team_id: int
    roster_slots: list[str]
    teams: list[Team]
    free_agents: list[Player] = Field(default_factory=list)
    matchups: list[Matchup] = Field(default_factory=list)
    data_quality_warnings: list[str] = Field(default_factory=list)
    fetched_at: datetime

    @property
    def my_team(self) -> Team:
        for team in self.teams:
            if team.id == self.my_team_id:
                return team
        raise ValueError("Configured team is missing from the league snapshot")


class SessionCreate(BaseModel):
    token: str = Field(min_length=16, max_length=512)


class WorkspaceSummary(BaseModel):
    id: str
    name: str
    slug: str
    plan: str


class MeResponse(BaseModel):
    user_id: str
    display_name: str
    email: str
    workspaces: list[WorkspaceSummary]


class EspnConnectionUpsert(BaseModel):
    league_id: int = Field(gt=0)
    team_id: int = Field(gt=0)
    season: int = Field(default=2026, ge=2019, le=2100)
    is_public: bool = False
    espn_s2: str | None = Field(default=None, max_length=4096)
    swid: str | None = Field(default=None, max_length=200)

    @field_validator("swid")
    @classmethod
    def normalize_swid(cls, value: str | None) -> str | None:
        if value is None:
            return value
        value = value.strip()
        if not value:
            return None
        return value if value.startswith("{") else f"{{{value}}}"


class ConnectionView(BaseModel):
    id: str
    league_id: int
    team_id: int
    season: int
    is_public: bool
    league_name: str | None
    status: str
    last_error: str | None
    last_synced_at: datetime | None


class RecommendationView(BaseModel):
    id: str
    kind: str
    title: str
    summary: str
    confidence: int
    impact_points: float
    payload: dict[str, object]
    status: str
    created_at: datetime


class RecommendationDecision(BaseModel):
    decision: Literal["approved", "dismissed"]


class NotificationChannelUpsert(BaseModel):
    kind: Literal["discord", "groupme"]
    label: str = Field(min_length=1, max_length=80)
    target: str = Field(min_length=10, max_length=2048)

    @model_validator(mode="after")
    def validate_target(self) -> NotificationChannelUpsert:
        self.target = self.target.strip()
        if self.kind == "discord":
            parsed = urlsplit(self.target)
            allowed_hosts = {"discord.com", "www.discord.com", "discordapp.com"}
            if (
                parsed.scheme != "https"
                or parsed.hostname not in allowed_hosts
                or not parsed.path.startswith("/api/webhooks/")
                or parsed.username
                or parsed.password
            ):
                raise ValueError("Discord target must be an official HTTPS webhook URL")
        elif not re.fullmatch(r"[A-Za-z0-9_-]{10,100}", self.target):
            raise ValueError("GroupMe target must be a valid bot ID")
        return self


class NotificationChannelView(BaseModel):
    id: str
    kind: str
    label: str
    is_active: bool
    created_at: datetime


class ActivityEventView(BaseModel):
    id: str
    action: str
    target_type: str
    target_id: str | None
    created_at: datetime


class JobRunRequest(BaseModel):
    kind: Literal[
        "lineup", "waivers", "trades", "weekly-report", "inactive-sweep", "full"
    ]
    notify: bool = True
