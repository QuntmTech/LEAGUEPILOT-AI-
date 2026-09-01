export const LEAGUEPILOT_BACKEND = "https://leaguepilot-ai.cloudpod.pro";
export const LEAGUEPILOT_AUTH_COOKIE = "leaguepilot_session";

export const authCookieOptions = {
  httpOnly: true,
  secure: true,
  sameSite: "lax" as const,
  path: "/",
  maxAge: 60 * 60 * 24 * 7,
};

export async function backendFetch(
  path: string,
  token?: string,
  init: RequestInit = {},
) {
  const headers = new Headers(init.headers);
  headers.set("Accept", "application/json");
  if (init.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  if (token) headers.set("Authorization", `Bearer ${token}`);

  return fetch(`${LEAGUEPILOT_BACKEND}${path}`, {
    ...init,
    headers,
    cache: "no-store",
  });
}

export async function readJson(response: Response) {
  const text = await response.text();
  if (!text) return null;
  try {
    return JSON.parse(text);
  } catch {
    return { message: text };
  }
}

/**
 * PocketBase record ids are exactly 15 lowercase alphanumerics. Validating before
 * interpolating into a backend path keeps caller-supplied values out of the URL.
 */
export function isRecordId(value: string): boolean {
  return /^[a-z0-9]{15}$/.test(value);
}

/**
 * Collections the dashboard may read directly, with the sort field to use for each.
 *
 * Only `users` has `created`/`updated` autodate fields — `recommendations`, `reports`,
 * `job_runs`, `league_snapshots` and `workspaces` have none, so `sort=-created` returns
 * HTTP 400 rather than an empty list. Sorts are pinned here so a caller cannot
 * reintroduce that bug. `id` is random, not time-ordered, so it is never a recency proxy.
 */
export const READABLE_COLLECTIONS = {
  recommendations: {
    sort: "-confidence",
    fields:
      "id,workspace,kind,title,summary,confidence,impact_points,payload,status,expires_at,reviewed_at",
  },
  reports: {
    sort: "-published_at",
    fields: "id,workspace,week,title,body_markdown,metrics,narration_mode,published_at",
  },
  job_runs: {
    // lease_token_hash, worker_id and raw result are deliberately excluded — operational
    // internals must never reach the browser.
    sort: "-scheduled_for",
    fields:
      "id,workspace,connection,kind,status,attempts,max_attempts,scheduled_for,started_at,completed_at,last_error",
  },
  league_snapshots: {
    // fetched_at is a real date field on this collection, so it is a valid sort — unlike
    // `created`, which does not exist here. `payload` carries the normalized league data
    // (teams, matchups, rosters, free agents) the dashboard renders; it holds no
    // credentials, and credentials_ciphertext lives on espn_connections, not here.
    sort: "-fetched_at",
    fields:
      "id,workspace,connection,week,payload,content_hash,schema_version,fetched_at,expires_at",
  },
  espn_connections: {
    // Matches the real schema. credentials_ciphertext is deliberately absent — it is also
    // marked hidden in PocketBase, so the API withholds it regardless, but listing fields
    // explicitly means a future schema change cannot silently start returning it.
    sort: "-last_synced_at",
    fields:
      "id,workspace,league_id,team_id,season,is_public,league_name,status,last_error,last_synced_at,next_sync_at,sync_failures",
  },
} as const;

export type ReadableCollection = keyof typeof READABLE_COLLECTIONS;

export function isReadableCollection(value: string): value is ReadableCollection {
  return Object.prototype.hasOwnProperty.call(READABLE_COLLECTIONS, value);
}

/** Read the session token, or null when the request is unauthenticated. */
export async function sessionToken(): Promise<string | null> {
  const { cookies } = await import("next/headers");
  return (await cookies()).get(LEAGUEPILOT_AUTH_COOKIE)?.value ?? null;
}

export function unauthorized() {
  return Response.json({ message: "Not authenticated." }, { status: 401 });
}

export function publicError(payload: unknown, fallback: string) {
  if (payload && typeof payload === "object") {
    const value = payload as Record<string, unknown>;
    if (typeof value.message === "string" && value.message.trim()) {
      return value.message;
    }
  }
  return fallback;
}
