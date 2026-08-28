from __future__ import annotations

import json
from datetime import UTC, datetime

import httpx

from app.meta import VERSION
from app.schemas import LeagueSnapshot, Matchup, Player, Team

ESPN_BASE_URL = "https://lm-api-reads.fantasy.espn.com/apis/v3/games/ffl"
MAX_RESPONSE_BYTES = 8 * 1024 * 1024
ESPN_SLOT_MAP = {
    0: "QB",
    2: "RB",
    4: "WR",
    6: "TE",
    7: "OP",
    16: "D/ST",
    17: "K",
    20: "BE",
    21: "IR",
    23: "FLEX",
}
ESPN_POSITION_MAP = {1: "QB", 2: "RB", 3: "WR", 4: "TE", 5: "K", 16: "D/ST"}


class EspnGatewayError(RuntimeError):
    pass


class EspnGateway:
    """Small, read-only adapter for ESPN's undocumented fantasy JSON endpoint."""

    def __init__(
        self,
        timeout_seconds: float = 20.0,
        *,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.timeout_seconds = timeout_seconds
        self.transport = transport

    def fetch_snapshot(
        self,
        *,
        league_id: int,
        team_id: int,
        season: int,
        espn_s2: str | None = None,
        swid: str | None = None,
        week: int | None = None,
    ) -> LeagueSnapshot:
        url = f"{ESPN_BASE_URL}/seasons/{season}/segments/0/leagues/{league_id}"
        cookies = {}
        if espn_s2 and swid:
            cookies = {"espn_s2": espn_s2, "SWID": swid}
        try:
            with httpx.Client(
                timeout=httpx.Timeout(self.timeout_seconds),
                transport=self.transport,
                trust_env=False,
                headers={"User-Agent": f"LeaguePilotAI/{VERSION} (+read-only)"},
                cookies=cookies,
            ) as client:
                league_data = self._get_json(
                    client,
                    url,
                    params=[
                        ("view", "mTeam"),
                        ("view", "mRoster"),
                        ("view", "mSettings"),
                        ("view", "mMatchup"),
                    ],
                )
                status_data = self._dict(league_data.get("status"))
                current_week = int(
                    week
                    or self._number(
                        status_data.get("currentScoringPeriod")
                        or status_data.get("currentMatchupPeriod"),
                        1,
                    )
                )
                free_agent_data = self._get_json(
                    client,
                    url,
                    params=[("view", "kona_player_info")],
                    headers={
                        "X-Fantasy-Filter": json.dumps(
                            {
                                "players": {
                                    "filterStatus": {"value": ["FREEAGENT", "WAIVERS"]},
                                    "limit": 80,
                                    "sortPercOwned": {
                                        "sortPriority": 1,
                                        "sortAsc": False,
                                    },
                                }
                            },
                            separators=(",", ":"),
                        )
                    },
                )

            members = {
                str(member.get("id")): str(
                    member.get("displayName")
                    or " ".join(
                        part for part in [member.get("firstName"), member.get("lastName")] if part
                    )
                    or "Unknown owner"
                )
                for member in self._dict_list(league_data.get("members"))
            }
            teams = [
                self._map_team(raw_team, current_week, members)
                for raw_team in self._dict_list(league_data.get("teams"))
            ]
            if not any(team.id == team_id for team in teams):
                raise EspnGatewayError(
                    "The configured team ID was not present in the ESPN league response"
                )
            free_agents = [
                self._map_player(
                    self._dict(raw.get("player")) or raw,
                    current_week,
                    current_slot="FA",
                )
                for raw in self._dict_list(free_agent_data.get("players"))
            ]
            settings = self._dict(league_data.get("settings"))
            return LeagueSnapshot(
                league_id=league_id,
                league_name=str(settings.get("name") or f"ESPN League {league_id}"),
                season=season,
                week=current_week,
                scoring_format=self._scoring_format(settings),
                my_team_id=team_id,
                roster_slots=self._roster_slots(settings, teams),
                teams=teams,
                free_agents=free_agents,
                matchups=self._map_matchups(league_data.get("schedule"), current_week),
                fetched_at=datetime.now(UTC),
            )
        except EspnGatewayError:
            raise
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            if status in {401, 403}:
                detail = "ESPN rejected the league credentials or access permissions"
            elif status == 404:
                detail = "ESPN did not find that league and season"
            else:
                detail = f"ESPN returned HTTP {status}"
            raise EspnGatewayError(f"ESPN sync failed: {detail}") from exc
        except (httpx.HTTPError, ValueError, TypeError, KeyError) as exc:
            safe_message = str(exc)
            for secret in (espn_s2, swid):
                if secret:
                    safe_message = safe_message.replace(secret, "[REDACTED]")
            raise EspnGatewayError(f"ESPN sync failed: {safe_message[:300]}") from exc

    def _get_json(
        self,
        client: httpx.Client,
        url: str,
        *,
        params: list[tuple[str, str]],
        headers: dict[str, str] | None = None,
    ) -> dict[str, object]:
        with client.stream("GET", url, params=params, headers=headers) as response:
            response.raise_for_status()
            declared_length = int(response.headers.get("content-length", "0") or 0)
            if declared_length > MAX_RESPONSE_BYTES:
                raise EspnGatewayError("ESPN response exceeded the safe size limit")
            body = bytearray()
            for chunk in response.iter_bytes():
                body.extend(chunk)
                if len(body) > MAX_RESPONSE_BYTES:
                    raise EspnGatewayError("ESPN response exceeded the safe size limit")
        payload = json.loads(body)
        if not isinstance(payload, dict):
            raise EspnGatewayError("ESPN returned an unexpected response shape")
        return payload

    def _map_team(
        self,
        source: dict[str, object],
        week: int,
        members: dict[str, str],
    ) -> Team:
        entries = self._dict_list(self._dict(source.get("roster")).get("entries"))
        players = [self._map_roster_entry(entry, week) for entry in entries]
        overall = self._dict(self._dict(source.get("record")).get("overall"))
        owner_ids = source.get("owners") if isinstance(source.get("owners"), list) else []
        owner_names = [members.get(str(owner), "Unknown owner") for owner in owner_ids]
        location = str(source.get("location") or "").strip()
        nickname = str(source.get("nickname") or "").strip()
        team_name = " ".join(part for part in (location, nickname) if part)
        return Team(
            id=int(self._number(source.get("id"), 0)),
            name=team_name or str(source.get("abbrev") or "Unknown Team"),
            owner=", ".join(owner_names),
            wins=int(self._number(overall.get("wins"), 0)),
            losses=int(self._number(overall.get("losses"), 0)),
            ties=int(self._number(overall.get("ties"), 0)),
            points_for=self._number(overall.get("pointsFor"), 0.0),
            projected_total=sum(
                self._effective_projection(player)
                for player in players
                if player.current_slot not in {"BE", "IR"}
            ),
            roster=players,
        )

    def _map_roster_entry(self, entry: dict[str, object], week: int) -> Player:
        pool_entry = self._dict(entry.get("playerPoolEntry"))
        raw_player = self._dict(pool_entry.get("player"))
        return self._map_player(
            raw_player,
            week,
            current_slot=self._slot_name(entry.get("lineupSlotId", 20)),
        )

    def _map_player(
        self,
        source: dict[str, object],
        week: int,
        *,
        current_slot: str,
    ) -> Player:
        position_id = int(self._number(source.get("defaultPositionId"), 0))
        position = ESPN_POSITION_MAP.get(position_id, "UNKNOWN")
        raw_eligible = source.get("eligibleSlots")
        eligible = (
            [self._slot_name(slot) for slot in raw_eligible if isinstance(slot, (int, str))]
            if isinstance(raw_eligible, list)
            else []
        )
        if not eligible:
            eligible = [position]
            if position in {"RB", "WR", "TE"}:
                eligible.append("FLEX")
        projected, season_points, average = self._player_stats(source.get("stats"), week)
        ownership = self._dict(source.get("ownership"))
        return Player(
            id=str(source.get("id") or "unknown"),
            name=str(source.get("fullName") or "Unknown Player"),
            position=position,
            pro_team=str(source.get("proTeamId") or "FA"),
            projected_points=projected,
            season_points=season_points,
            average_points=average,
            injury_status=str(source.get("injuryStatus") or "ACTIVE"),
            current_slot=current_slot,
            eligible_slots=sorted(set(eligible)),
            percent_owned=self._number(ownership.get("percentOwned"), 0.0),
        )

    def _player_stats(self, raw_stats: object, week: int) -> tuple[float, float, float]:
        stats = self._dict_list(raw_stats)
        projected = 0.0
        season_points = 0.0
        for stat in stats:
            total = self._number(stat.get("appliedTotal"), 0.0)
            source_id = int(self._number(stat.get("statSourceId"), -1))
            scoring_period = int(self._number(stat.get("scoringPeriodId"), -1))
            split_type = int(self._number(stat.get("statSplitTypeId"), -1))
            if source_id == 1 and scoring_period == week:
                projected = max(projected, total)
            if source_id == 0 and split_type == 0:
                season_points = max(season_points, total)
        completed_weeks = max(1, week - 1)
        return projected, season_points, season_points / completed_weeks

    def _map_matchups(self, raw_schedule: object, week: int) -> list[Matchup]:
        matchups: list[Matchup] = []
        for game in self._dict_list(raw_schedule):
            if int(self._number(game.get("matchupPeriodId"), 0)) != week:
                continue
            home = self._dict(game.get("home"))
            away = self._dict(game.get("away"))
            if not home or not away:
                continue
            matchups.append(
                Matchup(
                    week=week,
                    home_team_id=int(self._number(home.get("teamId"), 0)),
                    away_team_id=int(self._number(away.get("teamId"), 0)),
                    home_score=self._number(home.get("totalPoints"), 0.0),
                    away_score=self._number(away.get("totalPoints"), 0.0),
                    home_projected=self._number(home.get("totalProjectedPointsLive"), 0.0),
                    away_projected=self._number(away.get("totalProjectedPointsLive"), 0.0),
                )
            )
        return matchups

    def _roster_slots(self, settings: object, teams: list[Team]) -> list[str]:
        roster_settings = self._dict(self._dict(settings).get("rosterSettings"))
        counts = self._dict(roster_settings.get("lineupSlotCounts"))
        slots: list[str] = []
        for raw_slot, raw_count in counts.items():
            slot = self._slot_name(raw_slot)
            if slot not in {"BE", "IR"}:
                slots.extend([slot] * int(self._number(raw_count, 0)))
        if slots:
            return slots
        if teams:
            return [
                player.current_slot
                for player in teams[0].roster
                if player.current_slot not in {"BE", "IR"}
            ]
        return ["QB", "RB", "RB", "WR", "WR", "TE", "FLEX", "D/ST", "K"]

    @staticmethod
    def _scoring_format(settings: object) -> str:
        scoring = EspnGateway._dict(EspnGateway._dict(settings).get("scoringSettings"))
        if scoring.get("scoringType"):
            return f"ESPN {str(scoring['scoringType']).replace('_', ' ').title()}"
        return "Custom ESPN scoring"

    @staticmethod
    def _slot_name(value: object) -> str:
        try:
            numeric = int(value)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            text = str(value or "BE").upper()
            aliases = {
                "RB/WR/TE": "FLEX",
                "BENCH": "BE",
                "RESERVE": "IR",
                "DST": "D/ST",
            }
            return aliases.get(text, text)
        return ESPN_SLOT_MAP.get(numeric, str(numeric))

    @staticmethod
    def _number(value: object, default: float) -> float:
        try:
            return float(value)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _dict(value: object) -> dict[str, object]:
        return value if isinstance(value, dict) else {}

    @staticmethod
    def _dict_list(value: object) -> list[dict[str, object]]:
        if not isinstance(value, list):
            return []
        return [item for item in value if isinstance(item, dict)]

    @staticmethod
    def _effective_projection(player: Player) -> float:
        return player.projected_points or player.average_points
