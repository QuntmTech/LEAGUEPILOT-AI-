import { cookies } from "next/headers";
import {
  authCookieOptions,
  backendFetch,
  LEAGUEPILOT_AUTH_COOKIE,
  publicError,
  readJson,
} from "@/lib/leaguepilot-server";

export async function POST(request: Request) {
  const body = await request.json().catch(() => null) as { email?: string; password?: string } | null;
  if (!body?.email || !body.password) {
    return Response.json({ message: "Email and password are required." }, { status: 400 });
  }

  const response = await backendFetch("/api/collections/users/auth-with-password", undefined, {
    method: "POST",
    body: JSON.stringify({ identity: body.email.trim(), password: body.password }),
  });
  const payload = await readJson(response);
  if (!response.ok || !payload?.token) {
    return Response.json({ message: publicError(payload, "We couldn’t sign you in with those details.") }, { status: response.status || 401 });
  }

  const cookieStore = await cookies();
  cookieStore.set(LEAGUEPILOT_AUTH_COOKIE, payload.token, authCookieOptions);

  const bootstrapResponse = await backendFetch("/api/leaguepilot/bootstrap", payload.token, {
    method: "POST",
    body: JSON.stringify({}),
  });
  const bootstrap = await readJson(bootstrapResponse);

  return Response.json({ user: payload.record, bootstrap: bootstrapResponse.ok ? bootstrap : null });
}
