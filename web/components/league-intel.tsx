"use client";

import { useMemo } from "react";
import type { LeagueSnapshot, SnapshotTeam } from "@/lib/leaguepilot-client";

/**
 * Derivations over a real league snapshot.
 *
 * Every value here comes from backend data. Nothing is modelled, projected or invented:
 * where the backend did not supply a field, the caller renders an explicit unknown rather
 * than a plausible-looking number.
 */

export type RankedTeam = SnapshotTeam & {
  rank: number;
  isMine: boolean;
  /** Wins + points-for composite, matching how standings are conventionally broken. */
  record: string;
};

export function rankTeams(snapshot: LeagueSnapshot | null): RankedTeam[] {
  const payload = snapshot?.payload;
  const teams = payload?.teams;
  if (!Array.isArray(teams) || teams.length === 0) return [];
  const mine = payload?.my_team_id;

  // Standings order: wins desc, then points_for desc — the usual tiebreak. Teams missing
  // either field sort last rather than being assigned a fabricated value.
  const sorted = [...teams].sort((a, b) => {
    const w = (b.wins ?? -1) - (a.wins ?? -1);
    if (w !== 0) return w;
    return (b.points_for ?? -1) - (a.points_for ?? -1);
  });

  return sorted.map((team, index) => ({
    ...team,
    rank: index + 1,
    isMine: mine != null && team.id === mine,
    record:
      team.wins == null || team.losses == null
        ? "—"
        : `${team.wins}-${team.losses}${team.ties ? `-${team.ties}` : ""}`,
  }));
}

export function myTeam(ranked: RankedTeam[]): RankedTeam | null {
  return ranked.find((t) => t.isMine) ?? null;
}

/**
 * The honest Path to #1.
 *
 * Returns only what the snapshot supports. If the backend never reported points_for, the
 * gap is null and the UI says so — it does not estimate one. There is deliberately no
 * championship probability: nothing in the data supports it.
 */
export type PathToTop = {
  rank: number | null;
  teamCount: number;
  leader: RankedTeam | null;
  pointsBehind: number | null;
  gamesBehind: number | null;
  isLeader: boolean;
};

export function pathToTop(ranked: RankedTeam[]): PathToTop {
  const me = myTeam(ranked);
  const leader = ranked[0] ?? null;
  if (!me || !leader) {
    return { rank: null, teamCount: ranked.length, leader, pointsBehind: null, gamesBehind: null, isLeader: false };
  }
  const pointsBehind =
    me.points_for != null && leader.points_for != null
      ? Math.round((leader.points_for - me.points_for) * 100) / 100
      : null;
  const gamesBehind =
    me.wins != null && leader.wins != null ? leader.wins - me.wins : null;
  return {
    rank: me.rank,
    teamCount: ranked.length,
    leader,
    pointsBehind,
    gamesBehind,
    isLeader: me.rank === 1,
  };
}

/** This week's matchup for the user's team, if the snapshot carries one. */
export function myMatchup(snapshot: LeagueSnapshot | null) {
  const payload = snapshot?.payload;
  const mine = payload?.my_team_id;
  const matchups = payload?.matchups;
  if (mine == null || !Array.isArray(matchups)) return null;
  const game = matchups.find((m) => m.home_team_id === mine || m.away_team_id === mine);
  if (!game) return null;
  const home = game.home_team_id === mine;
  const teams = payload?.teams ?? [];
  const opponentId = home ? game.away_team_id : game.home_team_id;
  return {
    week: game.week,
    opponent: teams.find((t) => t.id === opponentId)?.name ?? `Team ${opponentId}`,
    myProjected: home ? game.home_projected : game.away_projected,
    opponentProjected: home ? game.away_projected : game.home_projected,
    myScore: home ? game.home_score : game.away_score,
    opponentScore: home ? game.away_score : game.home_score,
  };
}

export function useLeagueIntel(snapshot: LeagueSnapshot | null) {
  return useMemo(() => {
    const ranked = rankTeams(snapshot);
    return {
      ranked,
      me: myTeam(ranked),
      path: pathToTop(ranked),
      matchup: myMatchup(snapshot),
      warnings: snapshot?.payload?.data_quality_warnings ?? [],
      week: snapshot?.payload?.week ?? snapshot?.week ?? null,
      leagueName: snapshot?.payload?.league_name ?? null,
      fetchedAt: snapshot?.fetched_at ?? null,
    };
  }, [snapshot]);
}
