from __future__ import annotations

from dataclasses import dataclass
from functools import cache
from statistics import mean

from app.schemas import LeagueSnapshot, Player, Team

FLEX_POSITIONS = {"FLEX": {"RB", "WR", "TE"}, "OP": {"QB", "RB", "WR", "TE"}}
INACTIVE = {"OUT", "IR", "INJURY_RESERVE", "SUSPENSION"}


@dataclass(frozen=True)
class AnalysisResult:
    kind: str
    title: str
    summary: str
    confidence: int
    impact_points: float
    payload: dict[str, object]


def player_value(player: Player) -> float:
    if player.projected_points > 0 and player.average_points > 0:
        base = player.projected_points * 0.72 + player.average_points * 0.28
    else:
        base = player.projected_points if player.projected_points > 0 else player.average_points
    status = _effective_game_status(player)
    if status in INACTIVE:
        return -1000.0
    if status == "DOUBTFUL":
        return base * 0.65
    if status == "QUESTIONABLE":
        return base * 0.9
    return base


def analyze_availability_alerts(snapshot: LeagueSnapshot) -> list[AnalysisResult]:
    """Create urgent, evidence-backed alerts only for independently reported OUT players."""

    team = snapshot.my_team
    bench = [
        player
        for player in team.roster
        if player.current_slot == "BE" and _effective_game_status(player) not in INACTIVE
    ]
    results: list[AnalysisResult] = []
    for starter in team.roster:
        signal = starter.availability
        if starter.current_slot in {"BE", "IR"} or signal is None:
            continue
        independently_out = signal.confirmed_inactive is True or signal.game_status == "OUT"
        if not independently_out:
            continue
        replacements = [player for player in bench if eligible(player, starter.current_slot)]
        replacement = max(replacements, key=player_value) if replacements else None
        source_label = _source_label(signal.source)
        if replacement is None:
            title = f"{starter.name} is out; no eligible bench replacement was found"
            summary = (
                f"{source_label} lists {starter.name} as OUT for week {snapshot.week}. "
                "Review waivers or another roster slot before lock."
            )
            impact = 0.0
        else:
            title = f"{starter.name} is out — swap in {replacement.name}"
            summary = (
                f"{source_label} lists {starter.name} as OUT for week {snapshot.week}. "
                f"{replacement.name} is the highest-valued eligible bench replacement."
            )
            impact = max(0.0, player_value(replacement))
        results.append(
            AnalysisResult(
                kind="availability-alert",
                title=title,
                summary=summary,
                confidence=96 if signal.confirmed_inactive is True else 90,
                impact_points=round(impact, 2),
                payload={
                    "out_player_id": starter.id,
                    "out_player": starter.name,
                    "replacement_player_id": replacement.id if replacement else None,
                    "replacement_player": replacement.name if replacement else None,
                    "practice_status": signal.practice_status,
                    "game_status": signal.game_status,
                    "confirmed_inactive": signal.confirmed_inactive,
                    "evidence_source": signal.source,
                    "urgent": True,
                    "execution_capability": "approval-only",
                },
            )
        )
    return results


def eligible(player: Player, slot: str) -> bool:
    slot = slot.upper()
    if slot in player.eligible_slots or slot == player.position:
        return True
    return player.position in FLEX_POSITIONS.get(slot, set())


def optimal_lineup(players: list[Player], slots: list[str]) -> list[tuple[str, Player | None]]:
    ordered_slots = sorted(
        slots, key=lambda slot: sum(eligible(player, slot) for player in players)
    )

    @cache
    def solve(slot_index: int, used_mask: int) -> tuple[float, tuple[int, ...]]:
        if slot_index >= len(ordered_slots):
            return 0.0, ()
        slot = ordered_slots[slot_index]
        best_score = -10_000.0
        best_indices: tuple[int, ...] = (-1,)
        for player_index, player in enumerate(players):
            if used_mask & (1 << player_index) or not eligible(player, slot):
                continue
            rest_score, rest_indices = solve(slot_index + 1, used_mask | (1 << player_index))
            score = player_value(player) + rest_score
            if score > best_score:
                best_score = score
                best_indices = (player_index, *rest_indices)
        if best_score == -10_000.0:
            rest_score, rest_indices = solve(slot_index + 1, used_mask)
            return rest_score - 1000.0, (-1, *rest_indices)
        return best_score, best_indices

    _, selected = solve(0, 0)
    assignment = [
        (slot, players[index] if index >= 0 else None)
        for slot, index in zip(ordered_slots, selected, strict=True)
    ]
    return assignment


def analyze_lineup(snapshot: LeagueSnapshot) -> list[AnalysisResult]:
    team = snapshot.my_team
    optimized = optimal_lineup(team.roster, snapshot.roster_slots)
    optimal_starters = {player.id for _, player in optimized if player is not None}
    current_starters = {
        player.id for player in team.roster if player.current_slot not in {"BE", "IR"}
    }
    incoming = sorted(
        [player for player in team.roster if player.id in optimal_starters - current_starters],
        key=player_value,
        reverse=True,
    )
    outgoing = sorted(
        [player for player in team.roster if player.id in current_starters - optimal_starters],
        key=player_value,
    )
    results: list[AnalysisResult] = []
    for start, sit in zip(incoming, outgoing, strict=False):
        impact = max(0.0, player_value(start) - player_value(sit))
        results.append(
            AnalysisResult(
                kind="lineup",
                title=f"Start {start.name} over {sit.name}",
                summary=(
                    f"{start.name} carries a {impact:.1f}-point edge over {sit.name} "
                    f"using {_evidence_description(start, sit)}."
                ),
                confidence=_confidence(start, sit),
                impact_points=round(impact, 2),
                payload={
                    "start_player_id": start.id,
                    "start_player": start.name,
                    "sit_player_id": sit.id,
                    "sit_player": sit.name,
                    "start_value": round(player_value(start), 2),
                    "sit_value": round(player_value(sit), 2),
                    "evidence_source": _evidence_source(start, sit),
                    "risk_flags": _risk_flags(start, sit),
                    "execution_capability": "approval-only",
                },
            )
        )
    if not results:
        results.append(
            AnalysisResult(
                kind="lineup",
                title="Your strongest projected starters are already active",
                summary="No positive lineup swap was identified from the latest ESPN snapshot.",
                confidence=82,
                impact_points=0.0,
                payload={"execution_capability": "approval-only"},
            )
        )
    return results


def analyze_waivers(snapshot: LeagueSnapshot, limit: int = 8) -> list[AnalysisResult]:
    roster = snapshot.my_team.roster
    candidates: list[tuple[float, Player, Player]] = []
    for free_agent in snapshot.free_agents:
        comparable = [
            player
            for player in roster
            if player.position == free_agent.position
            and player.current_slot == "BE"
            and player.injury_status.upper() not in INACTIVE
        ]
        if not comparable:
            comparable = [
                player
                for player in roster
                if player.position == free_agent.position and player.current_slot != "IR"
            ]
        if not comparable:
            continue
        drop = min(comparable, key=player_value)
        delta = player_value(free_agent) - max(0.0, player_value(drop))
        if delta > 0.25:
            candidates.append((delta, free_agent, drop))

    results: list[AnalysisResult] = []
    for delta, add, drop in sorted(candidates, reverse=True, key=lambda item: item[0])[:limit]:
        suggested_faab = min(30, max(1, round(delta * 1.6 + add.percent_owned / 25)))
        results.append(
            AnalysisResult(
                kind="waiver",
                title=f"Add {add.name}; consider dropping {drop.name}",
                summary=(
                    f"Estimated roster-value gain: {delta:.1f} points per week. "
                    f"Suggested FAAB: {suggested_faab}% with a backup claim configured."
                ),
                confidence=_confidence(add, drop),
                impact_points=round(delta, 2),
                payload={
                    "add_player_id": add.id,
                    "add_player": add.name,
                    "drop_player_id": drop.id,
                    "drop_player": drop.name,
                    "suggested_faab_percent": suggested_faab,
                    "add_value": round(player_value(add), 2),
                    "drop_value": round(max(0.0, player_value(drop)), 2),
                    "evidence_source": _evidence_source(add, drop),
                    "risk_flags": _risk_flags(add, drop),
                    "execution_capability": "approval-only",
                },
            )
        )
    return results


def analyze_trades(snapshot: LeagueSnapshot, limit: int = 6) -> list[AnalysisResult]:
    mine = snapshot.my_team
    my_strength = _position_strength(mine)
    needs = [position for position, _ in sorted(my_strength.items(), key=lambda item: item[1])]
    scored_results: list[tuple[float, AnalysisResult]] = []

    for other in snapshot.teams:
        if other.id == mine.id:
            continue
        their_strength = _position_strength(other)
        their_needs = [
            position for position, _ in sorted(their_strength.items(), key=lambda item: item[1])
        ]
        for wanted_position in needs[:2]:
            targets = sorted(
                [player for player in other.roster if player.position == wanted_position],
                key=player_value,
                reverse=True,
            )
            offers = sorted(
                [player for player in mine.roster if player.position in their_needs[:2]],
                key=player_value,
                reverse=True,
            )
            pair = _closest_value_pair(offers, targets)
            if pair is None:
                continue
            offer, target = pair
            if offer.position == target.position:
                continue
            offer_value = player_value(offer)
            target_value = player_value(target)
            difference = abs(offer_value - target_value)
            fairness = max(50, round(100 - difference / max(offer_value, target_value) * 100))
            my_gain = _lineup_gain(snapshot, mine, target, exclude=offer)
            partner_gain = _lineup_gain(snapshot, other, offer, exclude=target)
            if my_gain < -2.0 or partner_gain < -2.0:
                continue
            need_alignment = _need_alignment(my_strength, their_strength, target, offer)
            mutual_fit = round(
                max(0.0, my_gain) + max(0.0, partner_gain) + need_alignment / 20,
                2,
            )
            confidence = min(90, max(58, round(fairness * 0.65 + need_alignment * 0.35)))
            result = AnalysisResult(
                kind="trade",
                title=f"Explore {offer.name} for {target.name} with {other.name}",
                summary=(
                    f"This targets your {target.position} need and their {offer.position} need. "
                    f"Preliminary fairness: {fairness}/100; mutual roster fit: {mutual_fit:.1f}."
                ),
                confidence=confidence,
                impact_points=round(max(0.0, my_gain), 2),
                payload={
                    "offer_player_id": offer.id,
                    "offer_player": offer.name,
                    "target_player_id": target.id,
                    "target_player": target.name,
                    "partner_team_id": other.id,
                    "partner_team": other.name,
                    "fairness_score": fairness,
                    "mutual_fit_score": mutual_fit,
                    "my_estimated_lineup_gain": round(my_gain, 2),
                    "partner_estimated_lineup_gain": round(partner_gain, 2),
                    "copy_paste_pitch": _trade_pitch(
                        partner=other,
                        offer=offer,
                        target=target,
                        partner_gain=partner_gain,
                    ),
                    "evidence_source": _evidence_source(offer, target),
                    "risk_flags": _risk_flags(offer, target),
                    "execution_capability": "approval-only",
                },
            )
            scored_results.append((mutual_fit + fairness / 25, result))
    deduplicated: dict[tuple[str, str, int], tuple[float, AnalysisResult]] = {}
    for score, result in scored_results:
        key = (
            str(result.payload["offer_player_id"]),
            str(result.payload["target_player_id"]),
            int(result.payload["partner_team_id"]),
        )
        current = deduplicated.get(key)
        if current is None or score > current[0]:
            deduplicated[key] = (score, result)
    return [
        result
        for _, result in sorted(deduplicated.values(), key=lambda item: item[0], reverse=True)[
            :limit
        ]
    ]


def power_rankings(snapshot: LeagueSnapshot) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    points = [team.points_for for team in snapshot.teams] or [1.0]
    high_points = max(points) or 1.0
    projections = [team.projected_total for team in snapshot.teams] or [1.0]
    high_projection = max(projections) or 1.0
    for team in snapshot.teams:
        games = team.wins + team.losses + team.ties
        win_rate = (team.wins + team.ties * 0.5) / games if games else 0.5
        points_score = team.points_for / high_points
        projection_score = (
            min(1.0, team.projected_total / high_projection) if team.projected_total else 0.5
        )
        score = 100 * (0.4 * win_rate + 0.4 * points_score + 0.2 * projection_score)
        rows.append(
            {
                "team_id": team.id,
                "team": team.name,
                "score": round(score, 1),
                "record_score": round(win_rate * 100, 1),
                "points_score": round(points_score * 100, 1),
                "projection_score": round(projection_score * 100, 1),
                "projected_total": round(team.projected_total, 2),
            }
        )
    return sorted(rows, key=lambda row: float(row["score"]), reverse=True)


def _position_strength(team: Team) -> dict[str, float]:
    result: dict[str, float] = {}
    for position in ("QB", "RB", "WR", "TE"):
        values = sorted(
            [
                max(0.0, player_value(player))
                for player in team.roster
                if player.position == position
            ],
            reverse=True,
        )
        result[position] = mean(values[:2]) if values else 0.0
    return result


def _closest_value_pair(
    offers: list[Player], targets: list[Player]
) -> tuple[Player, Player] | None:
    pairs = [
        (abs(player_value(offer) - player_value(target)), offer, target)
        for offer in offers
        for target in targets
        if player_value(offer) > 0 and player_value(target) > 0
    ]
    if not pairs:
        return None
    difference, offer, target = min(pairs, key=lambda item: item[0])
    if difference > max(player_value(offer), player_value(target)) * 0.4:
        return None
    return offer, target


def _lineup_gain(
    snapshot: LeagueSnapshot, team: Team, incoming: Player, *, exclude: Player
) -> float:
    count = _starter_count(snapshot, incoming.position)
    current = sorted(
        [
            max(0.0, player_value(player))
            for player in team.roster
            if player.position == incoming.position and player.id != exclude.id
        ],
        reverse=True,
    )
    threshold = current[count - 1] if len(current) >= count else 0.0
    return player_value(incoming) - threshold


def _starter_count(snapshot: LeagueSnapshot, position: str) -> int:
    direct = sum(1 for slot in snapshot.roster_slots if slot == position)
    return max(1, direct)


def _need_alignment(
    my_strength: dict[str, float],
    their_strength: dict[str, float],
    target: Player,
    offer: Player,
) -> float:
    max_my = max(my_strength.values()) or 1.0
    max_their = max(their_strength.values()) or 1.0
    my_need = max(0.0, 1 - my_strength.get(target.position, 0.0) / max_my)
    their_need = max(0.0, 1 - their_strength.get(offer.position, 0.0) / max_their)
    return round((my_need + their_need) * 50, 1)


def _evidence_source(*players: Player) -> str:
    independent_sources = sorted(
        {player.availability.source for player in players if player.availability is not None}
    )
    if independent_sources and all(player.projected_points > 0 for player in players):
        return "espn_projection_plus_" + "_and_".join(independent_sources) + "_availability"
    if all(player.projected_points > 0 for player in players):
        return "espn_weekly_projection"
    if all(player.average_points > 0 for player in players):
        return "season_average_fallback"
    return "mixed_or_limited_projection_data"


def _risk_flags(*players: Player) -> list[str]:
    flags = [
        f"{player.name}: {player.injury_status.upper()}"
        for player in players
        if player.injury_status.upper() not in {"ACTIVE", "NORMAL", "HEALTHY"}
    ]
    if any(player.projected_points <= 0 for player in players):
        flags.append("At least one weekly ESPN projection is unavailable")
    for player in players:
        signal = player.availability
        if signal is None:
            continue
        if signal.practice_status in {"DNP", "LP"}:
            flags.append(
                f"{player.name}: {signal.practice_status} on the {_source_label(signal.source)} "
                "practice report"
            )
        if signal.game_status and signal.game_status not in {"ACTIVE", "NORMAL", "HEALTHY"}:
            flags.append(
                f"{player.name}: {signal.game_status} on the {_source_label(signal.source)} "
                "game-status report"
            )
    return flags


def _confidence(left: Player, right: Player) -> int:
    confidence = 72
    if left.projected_points > 0 and right.projected_points > 0:
        confidence += 10
    if _effective_game_status(left) == "ACTIVE":
        confidence += 4
    if _effective_game_status(right) in INACTIVE:
        confidence += 10
    if left.availability is not None or right.availability is not None:
        confidence += 4
    if any(
        player.availability is not None
        and player.availability.practice_status in {"DNP", "LP"}
        for player in (left, right)
    ):
        confidence -= 5
    return min(96, confidence)


def _effective_game_status(player: Player) -> str:
    signal = player.availability
    if signal is not None:
        if signal.confirmed_inactive is True:
            return "OUT"
        if signal.game_status:
            return signal.game_status.upper()
    return player.injury_status.upper()


def _evidence_description(*players: Player) -> str:
    sources = sorted(
        {_source_label(player.availability.source) for player in players if player.availability}
    )
    if sources:
        return "ESPN projections plus independent " + " and ".join(sources) + " availability"
    return "the synchronized ESPN projections"


def _source_label(source: str) -> str:
    return "nflverse" if source.lower() == "nflverse" else source[:40]


def _trade_pitch(*, partner: Team, offer: Player, target: Player, partner_gain: float) -> str:
    addendum = (
        f" It projects as about a {partner_gain:.1f}-point lineup improvement for you."
        if partner_gain > 0.25
        else " It gives you another option at a position your roster could use."
    )
    recipient = partner.owner or partner.name
    return (
        f"Hey {recipient} — would you consider sending {target.name} for {offer.name}? "
        f"You would add help at {offer.position}, while I would fill a need at {target.position}."
        f"{addendum} No pressure—just thought it was a fair fit for both rosters."
    )
