import {
  backendFetch,
  publicError,
  readJson,
  sessionToken,
  unauthorized,
} from "@/lib/leaguepilot-server";

/**
 * Thin authenticated proxy to the shared backend discovery endpoint.
 *
 * All ESPN provider logic — the read call, team normalization and SWID owner matching —
 * lives in the CloudPod hook (cloudpod/pb_hooks/leaguepilot_espn.pb.js) so the web
 * dashboard and the iOS app share one implementation and one contract. This route only
 * attaches the session bearer token, which the browser cannot hold under the HttpOnly
 * model.
 *
 * ESPN session values pass straight through in the request body and are never stored,
 * logged or echoed here. The backend response already contains only the safe list
 * (team id and display name), so nothing further needs filtering.
 */
export async function POST(request: Request) {
  const token = await sessionToken();
  if (!token) return unauthorized();

  const body = (await request.json().catch(() => null)) as Record<string, unknown> | null;
  if (!body) return Response.json({ message: "Invalid request." }, { status: 400 });

  const response = await backendFetch("/api/leaguepilot/espn/discover", token, {
    method: "POST",
    body: JSON.stringify(body),
  });
  const payload = await readJson(response);
  if (!response.ok) {
    return Response.json(
      {
        message: publicError(payload, "We couldn't reach that league."),
        // Preserved so the form knows to reveal the private-league fields.
        needs_credentials:
          typeof (payload as { needs_credentials?: unknown } | null)?.needs_credentials ===
          "boolean"
            ? (payload as { needs_credentials: boolean }).needs_credentials
            : undefined,
      },
      { status: response.status },
    );
  }
  return Response.json(payload ?? {}, { status: response.status });
}
