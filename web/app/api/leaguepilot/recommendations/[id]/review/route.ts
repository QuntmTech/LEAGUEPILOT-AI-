import {
  backendFetch,
  isRecordId,
  publicError,
  readJson,
  sessionToken,
  unauthorized,
} from "@/lib/leaguepilot-server";

/**
 * Record a human decision on a recommendation.
 *
 * The `recommendations` collection is client read-only (createRule/updateRule/deleteRule
 * are all null), so this MUST go through the backend's review endpoint rather than a
 * direct record write — a direct PATCH would 403.
 *
 * The backend rejects anything whose status is not "proposed", so a double submit
 * returns 400 rather than silently re-reviewing. This records a decision only:
 * LEAGUEPILOT never executes the move on ESPN.
 */
export async function POST(request: Request, context: { params: Promise<{ id: string }> }) {
  const token = await sessionToken();
  if (!token) return unauthorized();

  const { id } = await context.params;
  if (!isRecordId(id)) {
    return Response.json({ message: "Invalid recommendation." }, { status: 400 });
  }

  const body = (await request.json().catch(() => null)) as { decision?: string } | null;
  const decision = body?.decision;
  if (decision !== "approved" && decision !== "dismissed") {
    return Response.json(
      { message: "Decision must be approved or dismissed." },
      { status: 400 },
    );
  }

  const response = await backendFetch(
    `/api/leaguepilot/recommendations/${id}/review`,
    token,
    { method: "POST", body: JSON.stringify({ decision }) },
  );
  const payload = await readJson(response);
  if (!response.ok) {
    return Response.json(
      { message: publicError(payload, "We couldn't record that decision.") },
      { status: response.status },
    );
  }
  return Response.json(payload ?? { ok: true }, { status: response.status });
}
