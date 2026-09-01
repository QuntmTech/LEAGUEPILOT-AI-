"use client";

import { ArrowRight, CircleAlert, Crown, FileText, TrendingUp, Users } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import type { Recommendation } from "@/lib/leaguepilot-client";
import type { RankedTeam } from "@/components/league-intel";

/**
 * Section views rendered from a real league snapshot.
 *
 * Nothing here synthesises data. Absent backend fields render an explicit dash, and a
 * section with no records renders an empty state rather than placeholder rows.
 */

function n(value?: number, digits = 1): string {
  return value == null || Number.isNaN(value) ? "—" : value.toFixed(digits);
}

/** Honest Path to #1: only what the snapshot supports. No championship probability. */
export function PathToTopPanel({
  path, topMoves, onOpen,
}: {
  path: {
    rank: number | null; teamCount: number; leader: RankedTeam | null;
    pointsBehind: number | null; gamesBehind: number | null; isLeader: boolean;
  };
  topMoves: Recommendation[];
  onOpen: (r: Recommendation) => void;
}) {
  return (
    <article className="lp-panel lp-path">
      <div className="lp-panel-head">
        <div>
          <p className="lp-app-kicker">PATH TO #1</p>
          <h2>
            {path.rank == null
              ? "Standings unavailable"
              : path.isLeader
                ? "You lead the league"
                : `You are ${ordinal(path.rank)} of ${path.teamCount}`}
          </h2>
        </div>
        {path.rank != null && <Badge className="lp-rank-badge"><Crown aria-hidden /> #{path.rank}</Badge>}
      </div>

      {path.rank == null ? (
        <p className="lp-empty-note">
          The latest snapshot did not include standings, so no gap can be calculated.
        </p>
      ) : (
        <div className="lp-path-gap">
          <span>
            <small>LEADER</small>
            <b>{path.leader?.name ?? "—"}</b>
          </span>
          <span>
            <small>GAMES BACK</small>
            <b>{path.isLeader ? "—" : path.gamesBehind == null ? "Not reported" : path.gamesBehind}</b>
          </span>
          <span>
            <small>POINTS BACK</small>
            <b>{path.isLeader ? "—" : path.pointsBehind == null ? "Not reported" : n(path.pointsBehind, 2)}</b>
          </span>
        </div>
      )}

      <div className="lp-path-moves">
        <small>NEXT MOVES, RANKED BY PROJECTED IMPACT</small>
        {topMoves.length === 0 ? (
          <p className="lp-empty-note">No open recommendations. Run an analysis to generate them.</p>
        ) : (
          <ol>
            {topMoves.map((r, i) => (
              <li key={r.id}>
                <button type="button" onClick={() => onOpen(r)}>
                  <span className="lp-move-rank">{i + 1}</span>
                  <span className="lp-move-body">
                    <b>{r.title}</b>
                    <small>{r.kind} · {r.confidence}% confidence · {n(r.impact_points, 2)} impact</small>
                  </span>
                  <ArrowRight aria-hidden />
                </button>
              </li>
            ))}
          </ol>
        )}
      </div>
    </article>
  );
}

export function StandingsTable({ ranked }: { ranked: RankedTeam[] }) {
  if (ranked.length === 0) {
    return <p className="lp-empty-note">No standings in the latest snapshot.</p>;
  }
  return (
    <div className="lp-table-wrap">
      <table className="lp-table">
        <caption className="sr-only">League standings and power rankings</caption>
        <thead>
          <tr>
            <th scope="col">#</th><th scope="col">Team</th><th scope="col">Manager</th>
            <th scope="col">Record</th><th scope="col">Points for</th><th scope="col">Projected</th>
          </tr>
        </thead>
        <tbody>
          {ranked.map((t) => (
            <tr key={t.id} className={t.isMine ? "lp-mine" : undefined}>
              <td>{t.rank}</td>
              <td><b>{t.name}</b>{t.isMine && <Badge className="lp-you">You</Badge>}</td>
              <td>{t.owner || "—"}</td>
              <td>{t.record}</td>
              <td>{n(t.points_for, 2)}</td>
              <td>{n(t.projected_total, 2)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/** Opponent roster explorer — every team's roster from the snapshot. */
export function OpponentExplorer({
  ranked, selectedId, onSelect,
}: {
  ranked: RankedTeam[]; selectedId: number | null; onSelect: (id: number) => void;
}) {
  const team = ranked.find((t) => t.id === selectedId) ?? null;
  if (ranked.length === 0) {
    return <p className="lp-empty-note">No teams in the latest snapshot.</p>;
  }
  return (
    <div className="lp-explorer">
      <ul className="lp-explorer-list">
        {ranked.map((t) => (
          <li key={t.id}>
            <button
              type="button"
              className={t.id === selectedId ? "active" : ""}
              aria-current={t.id === selectedId ? "true" : undefined}
              onClick={() => onSelect(t.id)}
            >
              <span className="lp-explorer-rank">{t.rank}</span>
              <span><b>{t.name}</b><small>{t.record}{t.owner ? ` · ${t.owner}` : ""}</small></span>
            </button>
          </li>
        ))}
      </ul>
      <div className="lp-explorer-roster">
        {!team ? (
          <p className="lp-empty-note">Select a team to view its roster.</p>
        ) : !team.roster || team.roster.length === 0 ? (
          <p className="lp-empty-note">The snapshot contains no roster for {team.name}.</p>
        ) : (
          <>
            <h3>{team.name}{team.isMine ? " (you)" : ""}</h3>
            <div className="lp-table-wrap">
              <table className="lp-table">
                <caption className="sr-only">{team.name} roster</caption>
                <thead>
                  <tr>
                    <th scope="col">Slot</th><th scope="col">Player</th>
                    <th scope="col">Pos</th><th scope="col">Team</th><th scope="col">Proj</th>
                  </tr>
                </thead>
                <tbody>
                  {team.roster.map((p, i) => (
                    <tr key={`${p.id ?? p.name ?? i}`}>
                      <td>{p.slot || "—"}</td>
                      <td><b>{p.name || "—"}</b>{p.status && p.status !== "Active" && (
                        <Badge className="lp-status-flag">{p.status}</Badge>
                      )}</td>
                      <td>{p.position || "—"}</td>
                      <td>{p.team || "—"}</td>
                      <td>{n(p.projected_points, 1)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

export function MatchupPanel({ matchup }: { matchup: ReturnType<typeof import("@/components/league-intel").myMatchup> }) {
  if (!matchup) {
    return (
      <article className="lp-panel">
        <div className="lp-panel-head"><div><p className="lp-app-kicker">THIS WEEK</p><h2>No matchup</h2></div></div>
        <p className="lp-empty-note">The snapshot contains no matchup for your team this week.</p>
      </article>
    );
  }
  const margin =
    matchup.myProjected != null && matchup.opponentProjected != null
      ? Math.round((matchup.myProjected - matchup.opponentProjected) * 100) / 100
      : null;
  return (
    <article className="lp-panel">
      <div className="lp-panel-head">
        <div><p className="lp-app-kicker">WEEK {matchup.week}</p><h2>vs {matchup.opponent}</h2></div>
        {margin != null && (
          <Badge className={margin >= 0 ? "lp-margin up" : "lp-margin down"}>
            <TrendingUp aria-hidden /> {margin >= 0 ? "+" : ""}{margin} projected
          </Badge>
        )}
      </div>
      <div className="lp-matchup">
        <span><small>YOU</small><b>{n(matchup.myProjected)}</b><em>{matchup.myScore != null ? `live ${n(matchup.myScore)}` : "not started"}</em></span>
        <span><small>{matchup.opponent.toUpperCase()}</small><b>{n(matchup.opponentProjected)}</b><em>{matchup.opponentScore != null ? `live ${n(matchup.opponentScore)}` : "not started"}</em></span>
      </div>
    </article>
  );
}

export function DataQualityPanel({ warnings, fetchedAt }: { warnings: string[]; fetchedAt: string | null }) {
  return (
    <article className="lp-panel lp-quality">
      <div className="lp-panel-head">
        <div><p className="lp-app-kicker">DATA CONFIDENCE</p><h2>Snapshot freshness</h2></div>
      </div>
      <p className="lp-quality-age">
        <small>LAST FETCHED</small>
        <b>{fetchedAt ? new Date(fetchedAt).toLocaleString() : "Never"}</b>
      </p>
      {warnings.length === 0 ? (
        <p className="lp-empty-note">The backend reported no data-quality warnings.</p>
      ) : (
        <ul className="lp-warnings">
          {warnings.map((w) => (
            <li key={w}><CircleAlert aria-hidden /> {w}</li>
          ))}
        </ul>
      )}
    </article>
  );
}

export function ReportsArchive({
  reports, onOpen,
}: {
  reports: { id: string; week?: number; title?: string; published_at?: string; narration_mode?: string }[];
  onOpen: (id: string) => void;
}) {
  if (reports.length === 0) {
    return <p className="lp-empty-note">No reports yet. A full analysis produces a weekly brief.</p>;
  }
  return (
    <div className="lp-reports-grid">
      {reports.map((r) => (
        <article key={r.id}>
          <div>
            <span><FileText aria-hidden /></span>
            <Badge>{r.narration_mode || "rules"}</Badge>
          </div>
          <p className="lp-app-kicker">WEEK {r.week ?? "—"}</p>
          <h2>{r.title || "Weekly brief"}</h2>
          <footer>
            <span>{r.published_at ? new Date(r.published_at).toLocaleDateString() : "—"}</span>
            <Button variant="outline" size="sm" onClick={() => onOpen(r.id)}>Read <ArrowRight aria-hidden /></Button>
          </footer>
        </article>
      ))}
    </div>
  );
}

function ordinal(n: number): string {
  const s = ["th", "st", "nd", "rd"];
  const v = n % 100;
  return n + (s[(v - 20) % 10] || s[v] || s[0]);
}

export { Users };
