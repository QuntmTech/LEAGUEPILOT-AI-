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

export function publicError(payload: unknown, fallback: string) {
  if (payload && typeof payload === "object") {
    const value = payload as Record<string, unknown>;
    if (typeof value.message === "string" && value.message.trim()) {
      return value.message;
    }
  }
  return fallback;
}
