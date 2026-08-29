from __future__ import annotations

from datetime import UTC, datetime

import httpx

from app.schemas import AvailabilitySignal, LeagueSnapshot, Player, Team
from app.services.availability import NflverseAvailabilityGateway, enrich_snapshot


def _snapshot() -> LeagueSnapshot:
    return LeagueSnapshot(
        league_id=1,
        league_name="Availability Test",
        season=2025,
        week=1,
        my_team_id=1,
        roster_slots=["RB"],
        teams=[
            Team(
                id=1,
                name="Test Team",
                roster=[
                    Player(
                        id="4242",
                        name="Example Runner",
                        position="RB",
                        current_slot="RB",
                        eligible_slots=["RB", "FLEX"],
                    )
                ],
            )
        ],
        fetched_at=datetime.now(UTC),
    )


def test_nflverse_adapter_maps_espn_ids_and_normalizes_practice_status() -> None:
    players = "gsis_id,espn_id\n00-0004242,4242\n"
    injuries = (
        "season,week,gsis_id,report_status,practice_status,"
        "report_primary_injury,practice_primary_injury\n"
        "2025,1,00-0004242,Questionable,Limited Participation in Practice,Knee,\n"
    )

    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        content = players if request.url.path.endswith("players.csv") else injuries
        return httpx.Response(200, text=content, request=request)

    gateway = NflverseAvailabilityGateway(transport=httpx.MockTransport(handler))
    signals = gateway.fetch_signals(season=2025, week=1)
    assert gateway.fetch_signals(season=2025, week=1) == signals

    assert signals["4242"] == AvailabilitySignal(
        source="nflverse",
        week=1,
        practice_status="LP",
        game_status="QUESTIONABLE",
        primary_injury="Knee",
        confirmed_inactive=None,
    )
    assert calls == 2


def test_enrichment_attaches_signal_without_leaking_raw_provider_rows() -> None:
    class FakeGateway:
        def fetch_signals(self, *, season: int, week: int):
            assert (season, week) == (2025, 1)
            return {
                "4242": AvailabilitySignal(
                    source="nflverse",
                    week=1,
                    practice_status="DNP",
                    game_status="OUT",
                    primary_injury="Hamstring",
                )
            }

    enriched = enrich_snapshot(_snapshot(), FakeGateway())
    signal = enriched.my_team.roster[0].availability

    assert signal is not None
    assert signal.game_status == "OUT"
    assert set(signal.model_dump()) == {
        "source",
        "week",
        "practice_status",
        "game_status",
        "primary_injury",
        "confirmed_inactive",
    }
    assert enriched.data_quality_warnings == []


def test_enrichment_degrades_to_a_visible_warning_when_feed_is_unavailable() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("players.csv"):
            return httpx.Response(200, text="gsis_id,espn_id\n00-1,1\n", request=request)
        return httpx.Response(404, request=request)

    gateway = NflverseAvailabilityGateway(transport=httpx.MockTransport(handler))
    enriched = enrich_snapshot(_snapshot(), gateway)

    assert enriched.my_team.roster[0].availability is None
    assert enriched.data_quality_warnings == [
        "nflverse has not published injury data for season 2025"
    ]
