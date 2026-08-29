import { sessionToken, unauthorized } from "@/lib/leaguepilot-server";

/**
 * Discover the teams in an ESPN league so the user can tap theirs instead of hunting for
 * a numeric team ID.
 *
 * ESPN is read-only here: this issues a single GET against the league read API and never
 * posts, patches or mutates anything.
 *
 * Credentials are used strictly in-flight. They arrive in the request body, are attached
 * to one outbound Cookie header, and are never stored, cached, logged or echoed. The
 * response contains only team id, name and owner display name — the safe list.
 *
 * Errors are sanitised: ESPN's body is never forwarded, because an authenticated error
 * response can contain account details. Callers get a fixed, actionable message.
 */
const ESPN_BASE = "https://lm-api-reads.fantasy.espn.com/apis/v3/games/ffl";

type EspnTeam = {
  id?: number;
  name?: string;
  location?: string;
  nickname?: string;
  owners?: unknown;
  primaryOwner?: unknown;
};

/** ESPN has used both a single `name` and split location/nickname over the years. */
function teamName(team: EspnTeam): string {
  const combined = [team.location, team.nickname].filter(Boolean).join(" ").trim();
  return (team.name || combined || `Team ${team.id ?? "?"}`).trim();
}

function ownerIds(team: EspnTeam): string[] {
  const list = Array.isArray(team.owners) ? team.owners : [];
  const ids = list.filter((o): o is string => typeof o === "string");
  if (typeof team.primaryOwner === "string") ids.push(team.primaryOwner);
  return ids;
}

/** SWID appears with and without braces depending on where it was copied from. */
function normalizeSwid(value: string): string {
  return value.trim().replace(/^\{|\}$/g, "").toUpperCase();
}

export async function POST(request: Request) {
  const token = await sessionToken();
  if (!token) return unauthorized();

  const body = (await request.json().catch(() => null)) as Record<string, unknown> | null;
  if (!body) return Response.json({ message: "Invalid request." }, { status: 400 });

  const leagueId = Number(body.league_id);
  const season = Number(body.season);
  if (!Number.isInteger(leagueId) || leagueId < 1) {
    return Response.json({ message: "Enter a valid ESPN league link or ID." }, { status: 400 });
  }
  if (!Number.isInteger(season) || season < 2019 || season > 2100) {
    return Response.json({ message: "Season must be between 2019 and 2100." }, { status: 400 });
  }

  const espnS2 = typeof body.espn_s2 === "string" ? body.espn_s2.trim() : "";
  const swid = typeof body.swid === "string" ? body.swid.trim() : "";
  if (!!espnS2 !== !!swid) {
    return Response.json(
      { message: "Provide both ESPN values together, or mark the league public." },
      { status: 400 },
    );
  }

  const headers: Record<string, string> = { Accept: "application/json" };
  if (espnS2 && swid) {
    // In-flight only. Never persisted, never logged.
    headers.Cookie = `espn_s2=${espnS2}; SWID=${swid}`;
  }

  let response: Response;
  try {
    response = await fetch(
      `${ESPN_BASE}/seasons/${season}/segments/0/leagues/${leagueId}?view=mTeam`,
      { headers, cache: "no-store", signal: AbortSignal.timeout(15_000) },
    );
  } catch {
    return Response.json(
      { message: "We couldn't reach ESPN. Please try again in a moment." },
      { status: 502 },
    );
  }

  if (response.status === 401 || response.status === 403) {
    return Response.json(
      {
        message: espnS2
          ? "ESPN rejected those values. They may have expired — copy them again from a signed-in ESPN tab."
          : "That league is private. Switch off “This league is public” and add your ESPN values.",
        needs_credentials: !espnS2,
      },
      { status: 401 },
    );
  }
  if (response.status === 404) {
    return Response.json(
      { message: "ESPN has no league with that ID for that season. Check the link and season." },
      { status: 404 },
    );
  }
  if (!response.ok) {
    return Response.json({ message: "ESPN returned an unexpected error." }, { status: 502 });
  }

  const payload = (await response.json().catch(() => null)) as { teams?: EspnTeam[] } | null;
  const rawTeams = Array.isArray(payload?.teams) ? payload!.teams! : [];
  if (rawTeams.length === 0) {
    return Response.json(
      { message: "ESPN returned no teams for that league and season." },
      { status: 422 },
    );
  }

  // The safe list: id, name, owner display name. No ESPN account identifiers leave here.
  const teams = rawTeams
    .filter((t) => Number.isInteger(t.id))
    .map((t) => ({ team_id: t.id as number, name: teamName(t) }));

  // Automatic identification: match the authenticated SWID against each team's owners.
  let matched: number | null = null;
  if (swid) {
    const target = normalizeSwid(swid);
    const owned = rawTeams.filter((t) =>
      ownerIds(t).some((id) => normalizeSwid(id) === target),
    );
    // Only auto-select when exactly one team matches. Two matches is ambiguous — a
    // co-managed league — and the user picks rather than us guessing wrong.
    if (owned.length === 1 && Number.isInteger(owned[0].id)) matched = owned[0].id as number;
  }

  return Response.json({
    league_id: leagueId,
    season,
    teams,
    matched_team_id: matched,
  });
}
