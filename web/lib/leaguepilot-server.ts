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
  recommendations: "-confidence",
  reports: "-published_at",
  job_runs: "-scheduled_for",
  league_snapshots: "",
  espn_connections: "-last_synced_at",
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
