from __future__ import annotations

from datetime import UTC, datetime

from app.schemas import LeagueSnapshot, Matchup, Player, Team
from app.services.analysis import (
    analyze_lineup,
    analyze_trades,
    analyze_waivers,
    optimal_lineup,
    power_rankings,
)


def player(
    player_id: str,
    name: str,
    position: str,
    projection: float,
    slot: str = "BE",
    injury: str = "ACTIVE",
) -> Player:
    eligible = [position]
    if position in {"RB", "WR", "TE"}:
        eligible.append("FLEX")
    if position in {"QB", "RB", "WR", "TE"}:
        eligible.append("OP")
    return Player(
        id=player_id,
        name=name,
        position=position,
        projected_points=projection,
        current_slot=slot,
        injury_status=injury,
        eligible_slots=eligible,
    )


def snapshot() -> LeagueSnapshot:
    my_roster = [
        player("qb1", "Starter QB", "QB", 20, "QB"),
        player("rb1", "Lead RB", "RB", 18, "RB"),
        player("rb2", "Risky RB", "RB", 6, "RB", "OUT"),
        player("wr1", "Lead WR", "WR", 17, "WR"),
        player("wr2", "Second WR", "WR", 13, "WR"),
        player("te1", "Tight End", "TE", 10, "TE"),
        player("fx1", "Current Flex", "WR", 8, "FLEX"),
        player("dst1", "Defense", "D/ST", 7, "D/ST"),
        player("k1", "Kicker", "K", 8, "K"),
        player("rb3", "Healthy Bench RB", "RB", 14, "BE"),
        player("wr3", "Bench WR", "WR", 11, "BE"),
    ]
    other_roster = [
        player("oq1", "Other QB", "QB", 16, "QB"),
        player("or1", "Other RB", "RB", 14, "RB"),
        player("or2", "Other RB Two", "RB", 13, "RB"),
        player("ow1", "Other Star WR", "WR", 18, "WR"),
        player("ow2", "Other WR Two", "WR", 12, "WR"),
        player("ot1", "Other TE", "TE", 5, "TE"),
    ]
    return LeagueSnapshot(
        league_id=1,
        league_name="Test League",
        season=2026,
        week=1,
        my_team_id=1,
        roster_slots=["QB", "RB", "RB", "WR", "WR", "TE", "FLEX", "D/ST", "K"],
        teams=[
            Team(
                id=1, name="My Team", wins=1, points_for=120, projected_total=125, roster=my_roster
            ),
            Team(
                id=2,
                name="Other Team",
                wins=0,
                losses=1,
                points_for=105,
                projected_total=112,
                roster=other_roster,
            ),
        ],
        free_agents=[
            player("fa1", "Waiver RB", "RB", 16, "FA"),
            player("fa2", "Bad Waiver WR", "WR", 4, "FA"),
        ],
        matchups=[
            Matchup(week=1, home_team_id=1, away_team_id=2, home_projected=125, away_projected=112)
        ],
        fetched_at=datetime.now(UTC),
    )


def test_optimizer_benches_out_player() -> None:
    league = snapshot()
    lineup = optimal_lineup(league.my_team.roster, league.roster_slots)
    starters = {selected.id for _, selected in lineup if selected is not None}

    assert "rb3" in starters
    assert "rb2" not in starters


def test_lineup_analysis_reports_positive_change() -> None:
    results = analyze_lineup(snapshot())

    assert results[0].kind == "lineup"
    assert results[0].impact_points > 0
    assert results[0].payload["execution_capability"] == "approval-only"
    assert results[0].payload["evidence_source"] == "espn_weekly_projection"
    assert "matchup" not in results[0].summary.lower()


def test_waiver_analysis_compares_real_roster_replacement() -> None:
    results = analyze_waivers(snapshot())

    assert results
    assert results[0].payload["add_player"] == "Waiver RB"
    assert 1 <= int(results[0].payload["suggested_faab_percent"]) <= 35
    assert results[0].payload["risk_flags"] == []


def test_trade_analysis_and_power_rankings_are_deterministic() -> None:
    league = snapshot()
    trades = analyze_trades(league)
    rankings = power_rankings(league)

    assert isinstance(trades, list)
    assert rankings[0]["team"] == "My Team"
    assert rankings[0]["score"] > rankings[1]["score"]
    assert set(rankings[0]) >= {"record_score", "points_score", "projection_score"}
    assert rankings[0]["projected_total"] == 125
