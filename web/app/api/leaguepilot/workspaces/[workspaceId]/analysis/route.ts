import { cookies } from "next/headers";
import { backendFetch, LEAGUEPILOT_AUTH_COOKIE, readJson } from "@/lib/leaguepilot-server";

export async function POST(request: Request, context: { params: Promise<{ workspaceId: string }> }) {
  const token = (await cookies()).get(LEAGUEPILOT_AUTH_COOKIE)?.value;
  if (!token) return Response.json({ message: "Not authenticated." }, { status: 401 });
  const { workspaceId } = await context.params;
  if (!/^[a-zA-Z0-9_-]+$/.test(workspaceId)) {
    return Response.json({ message: "Invalid workspace." }, { status: 400 });
  }
  const body = await request.json().catch(() => ({ kind: "full", notify: false }));
  const response = await backendFetch(`/api/leaguepilot/workspaces/${workspaceId}/analysis`, token, {
    method: "POST",
    body: JSON.stringify(body),
  });
  const payload = await readJson(response);
  return Response.json(payload ?? {}, { status: response.status });
}
