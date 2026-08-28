import { cookies } from "next/headers";
import { backendFetch, LEAGUEPILOT_AUTH_COOKIE, readJson } from "@/lib/leaguepilot-server";

export async function POST() {
  const token = (await cookies()).get(LEAGUEPILOT_AUTH_COOKIE)?.value;
  if (!token) return Response.json({ message: "Not authenticated." }, { status: 401 });

  const response = await backendFetch("/api/leaguepilot/bootstrap", token, {
    method: "POST",
    body: JSON.stringify({}),
  });
  const payload = await readJson(response);
  return Response.json(payload ?? {}, { status: response.status });
}
