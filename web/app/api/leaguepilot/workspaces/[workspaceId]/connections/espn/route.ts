import {
  backendFetch,
  isRecordId,
  publicError,
  readJson,
  sessionToken,
  unauthorized,
} from "@/lib/leaguepilot-server";

/**
 * Create or update the workspace's ESPN connection.
 *
 * ESPN cookies (espn_s2 / SWID) are the most sensitive values this app handles. They pass
 * through this route straight to the backend, which encrypts them into
 * credentials_ciphertext; they are never persisted here, never logged, and never echoed
 * back. The backend's connectionView response omits the ciphertext entirely, and the
 * column is marked hidden in PocketBase, so nothing encrypted can reach the browser.
 *
 * Validation mirrors the backend's own bounds so a malformed submission fails fast with a
 * message the user can act on, rather than as a generic 400 from the hook.
 *
 * Saving enqueues a sync job. This is read-only against ESPN — it never writes a lineup,
 * waiver claim or trade.
 */
function intInRange(value: unknown, min: number, max: number): number | null {
  const n = typeof value === "number" ? value : Number(String(value ?? "").trim());
  if (!Number.isInteger(n) || n < min || n > max) return null;
  return n;
}

export async function PUT(request: Request, context: { params: Promise<{ workspaceId: string }> }) {
  const token = await sessionToken();
  if (!token) return unauthorized();

  const { workspaceId } = await context.params;
  if (!isRecordId(workspaceId)) {
    return Response.json({ message: "Invalid workspace." }, { status: 400 });
  }

  const body = (await request.json().catch(() => null)) as Record<string, unknown> | null;
  if (!body) return Response.json({ message: "Invalid request." }, { status: 400 });

  const leagueId = intInRange(body.league_id, 1, 999_999_999_999);
  if (leagueId === null) {
    return Response.json({ message: "Enter the numeric ESPN league ID." }, { status: 400 });
  }
  const teamId = intInRange(body.team_id, 1, 999_999_999);
  if (teamId === null) {
    return Response.json({ message: "Enter your numeric ESPN team ID." }, { status: 400 });
  }
  const season = intInRange(body.season, 2019, 2100);
  if (season === null) {
    return Response.json({ message: "Season must be between 2019 and 2100." }, { status: 400 });
  }

  const isPublic = body.is_public === true;
  const espnS2 = typeof body.espn_s2 === "string" ? body.espn_s2.trim() : "";
  const swid = typeof body.swid === "string" ? body.swid.trim() : "";

  // The backend requires both cookies together; catching it here gives a clearer message.
  if (!!espnS2 !== !!swid) {
    return Response.json(
      { message: "Provide both ESPN cookies together, or mark the league public." },
      { status: 400 },
    );
  }
  if (espnS2.length > 4096 || swid.length > 200) {
    return Response.json({ message: "That ESPN cookie value is too long." }, { status: 400 });
  }

  const payload: Record<string, unknown> = {
    league_id: leagueId,
    team_id: teamId,
    season,
    is_public: isPublic,
  };
  // Only forward cookies when supplied. Omitting them on an update preserves the stored
  // ciphertext rather than clearing it.
  if (espnS2 && swid) {
    payload.espn_s2 = espnS2;
    payload.swid = swid;
  }

  const response = await backendFetch(
    `/api/leaguepilot/workspaces/${workspaceId}/connections/espn`,
    token,
    { method: "PUT", body: JSON.stringify(payload) },
  );
  const result = await readJson(response);
  if (!response.ok) {
    return Response.json(
      { message: publicError(result, "We couldn't save that league connection.") },
      { status: response.status },
    );
  }
  return Response.json(result ?? {}, { status: response.status });
}
