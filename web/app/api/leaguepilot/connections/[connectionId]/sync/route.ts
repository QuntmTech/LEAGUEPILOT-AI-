import {
  backendFetch,
  isRecordId,
  publicError,
  readJson,
  sessionToken,
  unauthorized,
} from "@/lib/leaguepilot-server";

/** Queue a sync for one ESPN connection. Read-only against ESPN — never writes a lineup. */
export async function POST(_request: Request, context: { params: Promise<{ connectionId: string }> }) {
  const token = await sessionToken();
  if (!token) return unauthorized();

  const { connectionId } = await context.params;
  if (!isRecordId(connectionId)) {
    return Response.json({ message: "Invalid connection." }, { status: 400 });
  }

  const response = await backendFetch(
    `/api/leaguepilot/connections/${connectionId}/sync`,
    token,
    { method: "POST", body: JSON.stringify({}) },
  );
  const payload = await readJson(response);
  if (!response.ok) {
    return Response.json(
      { message: publicError(payload, "We couldn't start that sync.") },
      { status: response.status },
    );
  }
  return Response.json(payload ?? { ok: true }, { status: response.status });
}
