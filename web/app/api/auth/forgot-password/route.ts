import { backendFetch, publicError, readJson } from "@/lib/leaguepilot-server";

export async function POST(request: Request) {
  const body = await request.json().catch(() => null) as { email?: string } | null;
  if (!body?.email?.trim()) {
    return Response.json({ message: "Enter the email address on your account." }, { status: 400 });
  }

  const response = await backendFetch("/api/collections/users/request-password-reset", undefined, {
    method: "POST",
    body: JSON.stringify({ email: body.email.trim().toLowerCase() }),
  });
  const payload = await readJson(response);
  if (!response.ok) {
    return Response.json({
      message: publicError(payload, "Password recovery email is not configured yet. Please contact LEAGUEPILOT AI support."),
      configured: false,
    }, { status: response.status || 503 });
  }

  return Response.json({ message: "If that account exists and email delivery is configured, a reset link will arrive shortly.", configured: true });
}
