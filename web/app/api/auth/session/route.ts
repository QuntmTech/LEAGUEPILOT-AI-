import { cookies } from "next/headers";
import {
  authCookieOptions,
  backendFetch,
  LEAGUEPILOT_AUTH_COOKIE,
  readJson,
} from "@/lib/leaguepilot-server";

export async function GET() {
  const cookieStore = await cookies();
  const token = cookieStore.get(LEAGUEPILOT_AUTH_COOKIE)?.value;
  if (!token) return Response.json({ message: "Not authenticated." }, { status: 401 });

  const response = await backendFetch("/api/collections/users/auth-refresh", token, { method: "POST" });
  const payload = await readJson(response);
  if (!response.ok || !payload?.token) {
    cookieStore.delete(LEAGUEPILOT_AUTH_COOKIE);
    return Response.json({ message: "Your session expired. Please sign in again." }, { status: 401 });
  }

  cookieStore.set(LEAGUEPILOT_AUTH_COOKIE, payload.token, authCookieOptions);
  return Response.json({ user: payload.record });
}
