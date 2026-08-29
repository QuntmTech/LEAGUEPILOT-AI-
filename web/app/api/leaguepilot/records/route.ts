import {
  backendFetch,
  isReadableCollection,
  isRecordId,
  READABLE_COLLECTIONS,
  readJson,
  sessionToken,
  unauthorized,
} from "@/lib/leaguepilot-server";

/**
 * Owner-scoped collection reads for the dashboard.
 *
 * The browser never holds the PocketBase token, so direct collection queries are
 * proxied here. PocketBase still enforces `owner = @request.auth.id` on every rule,
 * so this route widens no access — it only moves the bearer token server-side.
 */
export async function GET(request: Request) {
  const token = await sessionToken();
  if (!token) return unauthorized();

  const url = new URL(request.url);
  const collection = url.searchParams.get("collection") ?? "";
  if (!isReadableCollection(collection)) {
    return Response.json({ message: "Unknown collection." }, { status: 400 });
  }

  const filters: string[] = [];
  const workspace = url.searchParams.get("workspace");
  if (workspace) {
    if (!isRecordId(workspace)) {
      return Response.json({ message: "Invalid workspace." }, { status: 400 });
    }
    filters.push(`workspace = "${workspace}"`);
  }
  const connection = url.searchParams.get("connection");
  if (connection) {
    if (!isRecordId(connection)) {
      return Response.json({ message: "Invalid connection." }, { status: 400 });
    }
    filters.push(`connection = "${connection}"`);
  }

  const perPage = Math.min(Math.max(Number(url.searchParams.get("perPage")) || 50, 1), 200);
  const query = new URLSearchParams({ perPage: String(perPage) });
  if (filters.length) query.set("filter", filters.join(" && "));

  // Sort AND field list are pinned per collection — see READABLE_COLLECTIONS. Neither is
  // ever caller-supplied, so the browser cannot request an unlisted column (credential
  // ciphertext, lease tokens) or a sort expression the collection does not support.
  const { sort, fields } = READABLE_COLLECTIONS[collection];
  if (sort) query.set("sort", sort);
  query.set("fields", fields);

  const response = await backendFetch(
    `/api/collections/${collection}/records?${query.toString()}`,
    token,
  );
  const payload = await readJson(response);
  return Response.json(payload ?? {}, { status: response.status });
}
