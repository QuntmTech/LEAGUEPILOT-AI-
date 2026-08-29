from __future__ import annotations

import csv
import time
from collections.abc import Mapping
from io import StringIO
from typing import Protocol
from urllib.parse import urlsplit

import httpx

from app.meta import VERSION
from app.schemas import AvailabilitySignal, LeagueSnapshot, Player

NFLVERSE_PLAYERS_URL = (
    "https://github.com/nflverse/nflverse-data/releases/download/players/players.csv"
)
NFLVERSE_INJURIES_URL = (
    "https://github.com/nflverse/nflverse-data/releases/download/injuries/"
    "injuries_{season}.csv"
)
MAX_PLAYERS_BYTES = 20 * 1024 * 1024
MAX_INJURIES_BYTES = 12 * 1024 * 1024


class AvailabilityGatewayError(RuntimeError):
    pass


class AvailabilityGateway(Protocol):
    def fetch_signals(self, *, season: int, week: int) -> Mapping[str, AvailabilitySignal]: ...


class NflverseAvailabilityGateway:
    """Zero-cost beta adapter for nflverse practice and weekly game-status reports."""

    def __init__(
        self,
        timeout_seconds: float = 20.0,
        cache_ttl_seconds: float = 900.0,
        *,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.timeout_seconds = timeout_seconds
        self.cache_ttl_seconds = max(0.0, cache_ttl_seconds)
        self.transport = transport
        self._espn_to_gsis: dict[str, str] | None = None
        self._signal_cache: dict[
            tuple[int, int], tuple[float, dict[str, AvailabilitySignal]]
        ] = {}

    def fetch_signals(self, *, season: int, week: int) -> Mapping[str, AvailabilitySignal]:
        cache_key = (season, week)
        cached = self._signal_cache.get(cache_key)
        if cached is not None and time.monotonic() - cached[0] < self.cache_ttl_seconds:
            return cached[1]
        try:
            with httpx.Client(
                timeout=httpx.Timeout(self.timeout_seconds),
                trust_env=False,
                follow_redirects=True,
                headers={"User-Agent": f"LeaguePilotAI/{VERSION} (+read-only)"},
                event_hooks={"response": [_validate_redirect]},
                transport=self.transport,
            ) as client:
                if self._espn_to_gsis is None:
                    players_csv = self._download_csv(
                        client, NFLVERSE_PLAYERS_URL, MAX_PLAYERS_BYTES
                    )
                    self._espn_to_gsis = self._build_id_map(players_csv)
                injuries_csv = self._download_csv(
                    client,
                    NFLVERSE_INJURIES_URL.format(season=season),
                    MAX_INJURIES_BYTES,
                )
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            if status == 404:
                detail = f"nflverse has not published injury data for season {season}"
            else:
                detail = f"nflverse returned HTTP {status}"
            raise AvailabilityGatewayError(detail) from exc
        except (httpx.HTTPError, csv.Error, UnicodeError, ValueError) as exc:
            raise AvailabilityGatewayError(
                "The independent availability feed could not be read"
            ) from exc

        gsis_signals = self._parse_injuries(injuries_csv, season=season, week=week)
        result = {
            espn_id: gsis_signals[gsis_id]
            for espn_id, gsis_id in (self._espn_to_gsis or {}).items()
            if gsis_id in gsis_signals
        }
        self._signal_cache[cache_key] = (time.monotonic(), result)
        return result

    @staticmethod
    def _download_csv(client: httpx.Client, url: str, max_bytes: int) -> str:
        with client.stream("GET", url) as response:
            response.raise_for_status()
            declared = int(response.headers.get("content-length", "0") or 0)
            if declared > max_bytes:
                raise AvailabilityGatewayError("Independent availability response was too large")
            body = bytearray()
            for chunk in response.iter_bytes():
                body.extend(chunk)
                if len(body) > max_bytes:
                    raise AvailabilityGatewayError(
                        "Independent availability response was too large"
                    )
        return body.decode("utf-8-sig")

    @staticmethod
    def _build_id_map(content: str) -> dict[str, str]:
        result: dict[str, str] = {}
        for row in csv.DictReader(StringIO(content)):
            espn_id = str(row.get("espn_id") or "").strip()
            gsis_id = str(row.get("gsis_id") or "").strip()
            if espn_id and gsis_id:
                result[espn_id] = gsis_id
        if not result:
            raise AvailabilityGatewayError("nflverse player ID mapping was empty")
        return result

    @staticmethod
    def _parse_injuries(
        content: str, *, season: int, week: int
    ) -> dict[str, AvailabilitySignal]:
        result: dict[str, AvailabilitySignal] = {}
        for row in csv.DictReader(StringIO(content)):
            if _integer(row.get("season")) != season or _integer(row.get("week")) != week:
                continue
            gsis_id = str(row.get("gsis_id") or "").strip()
            if not gsis_id:
                continue
            practice_status = _practice_status(row.get("practice_status"))
            game_status = _game_status(row.get("report_status"))
            primary_injury = _optional_text(
                row.get("report_primary_injury") or row.get("practice_primary_injury")
            )
            if not any((practice_status, game_status, primary_injury)):
                continue
            signal = AvailabilitySignal(
                source="nflverse",
                week=week,
                practice_status=practice_status,
                game_status=game_status,
                primary_injury=primary_injury,
                # nflverse's weekly injury report is not the official 90-minute inactive list.
                confirmed_inactive=None,
            )
            current = result.get(gsis_id)
            if current is None or _signal_completeness(signal) >= _signal_completeness(current):
                result[gsis_id] = signal
        return result


def enrich_snapshot(
    snapshot: LeagueSnapshot, gateway: AvailabilityGateway
) -> LeagueSnapshot:
    warnings = list(snapshot.data_quality_warnings)
    try:
        signals = gateway.fetch_signals(season=snapshot.season, week=snapshot.week)
    except AvailabilityGatewayError as exc:
        warnings.append(str(exc)[:240])
        return snapshot.model_copy(update={"data_quality_warnings": warnings})

    matched = 0

    def attach(player: Player) -> Player:
        nonlocal matched
        signal = signals.get(player.id)
        if signal is None:
            return player
        matched += 1
        return player.model_copy(update={"availability": signal})

    teams = [
        team.model_copy(update={"roster": [attach(player) for player in team.roster]})
        for team in snapshot.teams
    ]
    free_agents = [attach(player) for player in snapshot.free_agents]
    if not signals:
        warnings.append(
            f"nflverse has no practice or weekly game-status rows for week {snapshot.week}"
        )
    elif matched == 0:
        warnings.append("Independent availability rows could not be matched to ESPN player IDs")
    return snapshot.model_copy(
        update={
            "teams": teams,
            "free_agents": free_agents,
            "data_quality_warnings": warnings,
        }
    )


def _practice_status(value: object) -> str | None:
    normalized = " ".join(str(value or "").split()).lower()
    mapping = {
        "did not participate in practice": "DNP",
        "limited participation in practice": "LP",
        "full participation in practice": "FP",
        "did not participate": "DNP",
        "limited": "LP",
        "full": "FP",
    }
    return mapping.get(normalized) or (_optional_text(value).upper() if normalized else None)


def _game_status(value: object) -> str | None:
    result = _optional_text(value)
    return result.upper().replace(" ", "_") if result else None


def _optional_text(value: object) -> str | None:
    result = " ".join(str(value or "").replace("\x00", "").split())[:120]
    return result or None


def _integer(value: object) -> int:
    try:
        return int(str(value or "0"))
    except ValueError:
        return 0


def _signal_completeness(signal: AvailabilitySignal) -> int:
    return sum(
        item is not None
        for item in (signal.practice_status, signal.game_status, signal.primary_injury)
    )


def _validate_redirect(response: httpx.Response) -> None:
    if not response.is_redirect:
        return
    location = response.headers.get("location", "")
    parsed = urlsplit(location)
    if parsed.scheme and (
        parsed.scheme != "https"
        or parsed.hostname not in {"github.com", "release-assets.githubusercontent.com"}
        or parsed.username
        or parsed.password
    ):
        raise AvailabilityGatewayError("Independent availability redirect was rejected")
