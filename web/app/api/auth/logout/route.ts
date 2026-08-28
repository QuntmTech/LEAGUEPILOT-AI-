import { cookies } from "next/headers";
import { LEAGUEPILOT_AUTH_COOKIE } from "@/lib/leaguepilot-server";

export async function POST() {
  const cookieStore = await cookies();
  cookieStore.delete(LEAGUEPILOT_AUTH_COOKIE);
  return Response.json({ ok: true });
}
