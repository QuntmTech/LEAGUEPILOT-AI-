import { cookies } from "next/headers";
import {
  authCookieOptions,
  backendFetch,
  LEAGUEPILOT_AUTH_COOKIE,
  publicError,
  readJson,
} from "@/lib/leaguepilot-server";

export async function POST(request: Request) {
  const body = await request.json().catch(() => null) as { name?: string; email?: string; password?: string; passwordConfirm?: string } | null;
  if (!body?.name?.trim() || !body.email?.trim() || !body.password || !body.passwordConfirm) {
    return Response.json({ message: "Complete every required field." }, { status: 400 });
  }
  if (body.password !== body.passwordConfirm) {
    return Response.json({ message: "The passwords do not match." }, { status: 400 });
  }

  const createResponse = await backendFetch("/api/collections/users/records", undefined, {
    method: "POST",
    body: JSON.stringify({
      name: body.name.trim(),
      email: body.email.trim().toLowerCase(),
      password: body.password,
      passwordConfirm: body.passwordConfirm,
    }),
  });
  const created = await readJson(createResponse);
  if (!createResponse.ok) {
    return Response.json({ message: publicError(created, "We couldn’t create that account.") }, { status: createResponse.status || 400 });
  }

  const authResponse = await backendFetch("/api/collections/users/auth-with-password", undefined, {
    method: "POST",
    body: JSON.stringify({ identity: body.email.trim(), password: body.password }),
  });
  const auth = await readJson(authResponse);
  if (!authResponse.ok || !auth?.token) {
    return Response.json({ message: "Your account was created, but automatic sign-in failed. Please sign in." }, { status: 409 });
  }

  const cookieStore = await cookies();
  cookieStore.set(LEAGUEPILOT_AUTH_COOKIE, auth.token, authCookieOptions);
  const bootstrapResponse = await backendFetch("/api/leaguepilot/bootstrap", auth.token, {
    method: "POST",
    body: JSON.stringify({}),
  });
  const bootstrap = await readJson(bootstrapResponse);

  return Response.json({ user: auth.record ?? created, bootstrap: bootstrapResponse.ok ? bootstrap : null }, { status: 201 });
}
