import {
  backendFetch,
  readJson,
  sessionToken,
  unauthorized,
} from "@/lib/leaguepilot-server";

/**
 * List the workspace's ESPN connections. `bootstrap` does not return these, so
 * multi-league selection needs its own read.
 *
 * Credential ciphertext is never requested: `fields` is pinned to display-safe
 * columns so no encrypted payload can reach the browser even if the schema grows.
 */
const SAFE_FIELDS = [
  "id",
  "workspace",
  "league_id",
  "season",
  "label",
  "visibility",
  "status",
  "last_synced_at",
  "last_error",
].join(",");

export async function GET() {
  const token = await sessionToken();
  if (!token) return unauthorized();

  const query = new URLSearchParams({
    perPage: "50",
    sort: "-last_synced_at",
    fields: SAFE_FIELDS,
  });
  const response = await backendFetch(
    `/api/collections/espn_connections/records?${query.toString()}`,
    token,
  );
  const payload = await readJson(response);
  return Response.json(payload ?? {}, { status: response.status });
}
