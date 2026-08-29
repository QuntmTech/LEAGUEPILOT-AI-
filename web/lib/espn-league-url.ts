/**
 * Parse an ESPN fantasy football league or team URL.
 *
 * Consumers paste a link rather than hunting for numeric IDs. ESPN uses several shapes
 * across its web app and mobile handoffs, and the ids appear as query parameters in all
 * of them:
 *
 *   https://fantasy.espn.com/football/league?leagueId=123456
 *   https://fantasy.espn.com/football/team?leagueId=123456&teamId=4&seasonId=2026
 *   https://fantasy.espn.com/football/league/scoreboard?leagueId=123456&matchupPeriodId=3
 *   fantasy.espn.com/football/team?leagueId=123456&teamId=4   (no scheme)
 *
 * A bare numeric id is also accepted, because plenty of people know their league id and
 * will type it directly.
 *
 * Returns nulls rather than throwing: the caller renders a field-level message, and a
 * partial parse (league without team) is a normal, useful result — the team is then
 * resolved by the connect flow instead of being typed.
 */
export type ParsedEspnLink = {
  leagueId: number | null;
  teamId: number | null;
  season: number | null;
};

const EMPTY: ParsedEspnLink = { leagueId: null, teamId: null, season: null };

function toId(value: string | null, max: number): number | null {
  if (!value) return null;
  const trimmed = value.trim();
  // Reject anything non-numeric outright — "12a" must not silently become 12.
  if (!/^\d+$/.test(trimmed)) return null;
  const parsed = Number(trimmed);
  return Number.isInteger(parsed) && parsed >= 1 && parsed <= max ? parsed : null;
}

export function parseEspnLeagueLink(input: string): ParsedEspnLink {
  const raw = (input ?? "").trim();
  if (!raw) return EMPTY;

  // A bare id typed directly.
  if (/^\d+$/.test(raw)) {
    return { ...EMPTY, leagueId: toId(raw, 999_999_999_999) };
  }

  // Tolerate a missing scheme so a copied "fantasy.espn.com/..." still parses.
  const candidate = /^https?:\/\//i.test(raw) ? raw : `https://${raw}`;
  let url: URL;
  try {
    url = new URL(candidate);
  } catch {
    return EMPTY;
  }

  // Only trust espn.com hosts. Matching the suffix on a dot boundary prevents
  // "notespn.com" or "espn.com.evil.test" from being treated as ESPN.
  const host = url.hostname.toLowerCase();
  if (host !== "espn.com" && !host.endsWith(".espn.com")) return EMPTY;

  const params = url.searchParams;
  return {
    leagueId: toId(params.get("leagueId"), 999_999_999_999),
    teamId: toId(params.get("teamId"), 999_999_999),
    season: toId(params.get("seasonId") ?? params.get("season"), 2100),
  };
}
