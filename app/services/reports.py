from __future__ import annotations

import httpx

from app.config import Settings
from app.schemas import LeagueSnapshot
from app.services.ai import Narrator, RulesNarrator, build_narrator
from app.services.analysis import power_rankings


def build_weekly_report(
    snapshot: LeagueSnapshot, narrator: Narrator
) -> tuple[str, dict[str, object]]:
    facts = build_report_facts(snapshot)
    return narrator.create_weekly_narrative(facts), facts


def build_weekly_report_resilient(
    snapshot: LeagueSnapshot, narrator: Narrator
) -> tuple[str, dict[str, object], str]:
    facts = build_report_facts(snapshot)
    mode = narrator.__class__.__name__.removesuffix("Narrator").lower() or "rules"
    try:
        body = narrator.create_weekly_narrative(facts).strip()
        if not body:
            raise ValueError("Narrator returned an empty report")
        return body, facts, mode
    except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError):
        facts["narration_fallback"] = True
        return RulesNarrator().create_weekly_narrative(facts), facts, "rules-fallback"


def build_configured_weekly_report(
    snapshot: LeagueSnapshot,
    settings: Settings,
) -> tuple[str, dict[str, object], str]:
    try:
        narrator = build_narrator(settings)
    except ValueError:
        facts = build_report_facts(snapshot)
        facts["narration_fallback"] = True
        return RulesNarrator().create_weekly_narrative(facts), facts, "rules-fallback"
    return build_weekly_report_resilient(snapshot, narrator)


def build_report_facts(snapshot: LeagueSnapshot) -> dict[str, object]:
    rankings = power_rankings(snapshot)
    leader = rankings[0]["team"] if rankings else "No leader yet"
    closest_game = "No completed matchup data yet"
    completed = [
        matchup for matchup in snapshot.matchups if matchup.home_score or matchup.away_score
    ]
    if completed:
        closest = min(completed, key=lambda game: abs(game.home_score - game.away_score))
        home = _team_name(snapshot, closest.home_team_id)
        away = _team_name(snapshot, closest.away_team_id)
        closest_game = (
            f"{home} and {away} are separated by "
            f"{abs(closest.home_score - closest.away_score):.1f} points"
        )
    return {
        "week": snapshot.week,
        "leader": leader,
        "closest_game": closest_game,
        "efficiency_note": _efficiency_note(snapshot),
        "power_rankings": rankings,
        "matchups": [matchup.model_dump(mode="json") for matchup in snapshot.matchups],
    }


def _team_name(snapshot: LeagueSnapshot, team_id: int) -> str:
    for team in snapshot.teams:
        if team.id == team_id:
            return team.name
    return f"Team {team_id}"


def _efficiency_note(snapshot: LeagueSnapshot) -> str:
    team = snapshot.my_team
    bench_points = sum(
        player.projected_points for player in team.roster if player.current_slot == "BE"
    )
    starter_points = sum(
        player.projected_points for player in team.roster if player.current_slot not in {"BE", "IR"}
    )
    if not starter_points:
        return "No starter projections are available yet"
    return f"{team.name} has {bench_points:.1f} projected points on its bench"
