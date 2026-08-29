import assert from "node:assert/strict";
import test from "node:test";
import { readFile } from "node:fs/promises";

/**
 * Static guards over the server-proxied API surface.
 *
 * These assert the security properties of the route source rather than booting a
 * server: the properties are structural (allowlists, pinned sorts/fields, no
 * caller-supplied query passthrough) and a source-level check cannot pass by
 * accident the way a mocked request can.
 */

const read = (p) => readFile(new URL(`../${p}`, import.meta.url), "utf8");

test("every protected route requires a session before doing work", async () => {
  const routes = [
    "app/api/leaguepilot/records/route.ts",
    "app/api/leaguepilot/connections/route.ts",
    "app/api/leaguepilot/connections/[connectionId]/sync/route.ts",
    "app/api/leaguepilot/recommendations/[id]/review/route.ts",
    "app/api/leaguepilot/realtime/route.ts",
  ];
  for (const route of routes) {
    const src = await read(route);
    assert.match(src, /sessionToken\(\)/, `${route} must read the session cookie`);
    assert.match(src, /unauthorized\(\)/, `${route} must refuse without a session`);
    // Compare call sites, not the import block: `backendFetch` also appears in the
    // import statement, which necessarily precedes the guard.
    const body = src.slice(src.lastIndexOf("} from"));
    const guardIndex = body.indexOf("unauthorized()");
    const fetchIndex = body.search(/(backendFetch|fetch)\(/);
    if (fetchIndex !== -1) {
      assert.ok(
        guardIndex !== -1 && guardIndex < fetchIndex,
        `${route} must check auth before calling the backend`,
      );
    }
  }
});

test("collection and field allowlists are pinned server-side", async () => {
  const src = await read("lib/leaguepilot-server.ts");
  for (const collection of [
    "recommendations",
    "reports",
    "job_runs",
    "league_snapshots",
    "espn_connections",
  ]) {
    assert.ok(src.includes(`${collection}:`), `${collection} must be in the allowlist`);
  }
  // Credential and operational columns must never appear in any field allowlist.
  for (const forbidden of ["credential", "ciphertext", "lease_token_hash", "password"]) {
    assert.ok(
      !new RegExp(`fields:[^"]*"[^"]*${forbidden}`).test(src),
      `${forbidden} must never be in a field allowlist`,
    );
  }
});

test("the records route never accepts caller-supplied sort, fields, filter or expand", async () => {
  const src = await read("app/api/leaguepilot/records/route.ts");
  for (const param of ["sort", "fields", "filter", "expand"]) {
    assert.ok(
      !src.includes(`searchParams.get("${param}")`),
      `${param} must not be read from the query string`,
    );
  }
  // Sort and fields must come from the pinned table only.
  assert.match(src, /READABLE_COLLECTIONS\[collection\]/);
});

test("workspace and connection filters are built server-side from validated ids", async () => {
  const src = await read("app/api/leaguepilot/records/route.ts");
  assert.match(src, /isRecordId\(workspace\)/);
  assert.match(src, /isRecordId\(connection\)/);
  assert.match(src, /workspace = "\$\{workspace\}"/);
});

test("record id validation rejects anything that is not a PocketBase id", async () => {
  const src = await read("lib/leaguepilot-server.ts");
  const match = src.match(/isRecordId[\s\S]*?return (\/.*?\/)\.test/);
  assert.ok(match, "isRecordId must use an anchored pattern");
  const pattern = new RegExp(match[1].slice(1, -1));
  assert.ok(pattern.test("abcdefghij12345"));
  for (const bad of [
    "",
    "short",
    "ABCDEFGHIJ12345",
    "abcdefghij12345x",
    'abc" || true || "',
    "../../etc/passwd",
  ]) {
    assert.ok(!pattern.test(bad), `${bad || "(empty)"} must be rejected`);
  }
});

test("review only accepts approved or dismissed, and never writes the record directly", async () => {
  const src = await read("app/api/leaguepilot/recommendations/[id]/review/route.ts");
  assert.match(src, /decision !== "approved" && decision !== "dismissed"/);
  assert.match(src, /leaguepilot\/recommendations\/\$\{id\}\/review/);
  assert.ok(
    !src.includes("/api/collections/recommendations"),
    "review must not write the collection directly — that would 403",
  );
});

test("no sort uses -created, which 400s on collections without autodate fields", async () => {
  const src = await read("lib/leaguepilot-server.ts");
  assert.ok(!/sort:\s*"-?created"/.test(src), "-created is not a valid sort on these collections");
  assert.ok(!/sort:\s*"-id"/.test(src), "ids are random, not time-ordered");
});

test("the realtime proxy keeps the bearer token server-side and cleans up", async () => {
  const src = await read("app/api/leaguepilot/realtime/route.ts");
  assert.match(src, /release\(/, "must release the upstream connection");
  assert.match(src, /request\.signal/, "must react to browser disconnect");
  assert.match(src, /clearInterval\(heartbeat\)/, "must clear the heartbeat");
  const client = await read("lib/leaguepilot-realtime.ts");
  assert.ok(
    !/Authorization/i.test(client),
    "the browser client must never send an Authorization header",
  );
  assert.match(client, /MAX_DELAY_MS/, "reconnect backoff must be bounded");
});

test("league switching clears stale data and discards superseded responses", async () => {
  const src = await read("lib/use-league-scope.ts");
  assert.match(src, /clearLeagueData\(\)/);
  assert.match(src, /mine !== generation\.current/, "superseded responses must be dropped");
  assert.match(src, /aborter\.current\?\.abort\(\)/, "in-flight requests must be aborted");
  // Clearing must happen before the new load is kicked off.
  const clearAt = src.indexOf("clearLeagueData();\n      setConnectionId(id)");
  const loadAt = src.indexOf("void load(id)");
  assert.ok(clearAt !== -1 && clearAt < loadAt, "clear must precede the new load");
});

test("the ESPN connection route never persists, logs or echoes credentials", async () => {
  const src = await read("app/api/leaguepilot/workspaces/[workspaceId]/connections/espn/route.ts");
  // Cookies may only be forwarded to the backend, never written anywhere else.
  assert.ok(!/console\.(log|info|warn|error)/.test(src), "must not log anything");
  assert.ok(!/localStorage|sessionStorage|cookies\(\)\.set/.test(src), "must not persist credentials");
  assert.match(src, /!!espnS2 !== !!swid/, "must require both cookies together");
  assert.match(src, /espnS2\.length > 4096 \|\| swid\.length > 200/, "must bound cookie sizes");
  // Omitting cookies on an update must preserve stored ciphertext rather than clear it.
  assert.match(src, /if \(espnS2 && swid\)/);
});

test("the connect form keeps credentials out of React state and clears them", async () => {
  const src = await read("components/connect-espn-form.tsx");
  assert.match(src, /useRef<HTMLInputElement>/, "credentials must live in refs, not state");
  assert.ok(
    !/useState[^\n]*espnS2|useState[^\n]*swid/i.test(src),
    "credentials must never be React state",
  );
  assert.match(src, /clearCredentials\(\);/, "must clear after submit");
  // Clearing must be in the finally block so it runs on failure too.
  assert.match(src, /finally \{[\s\S]{0,220}clearCredentials\(\)/);
  assert.match(src, /type="password"/, "cookie inputs must be masked");
  assert.match(src, /autoComplete="off"/, "browsers must not offer to save them");
});

test("discovery keeps ESPN read-only and never leaks credentials or ESPN error bodies", async () => {
  const src = await read("app/api/leaguepilot/espn/discover/route.ts");
  assert.match(src, /sessionToken\(\)/);
  assert.match(src, /unauthorized\(\)/);
  // Read-only: one GET, no mutating verb anywhere.
  assert.ok(!/method:\s*"(POST|PUT|PATCH|DELETE)"/.test(src.replace(/export async function POST/, "")),
    "discovery must not issue a mutating request to ESPN");
  assert.ok(!/console\.(log|info|warn|error)/.test(src), "must not log");
  assert.ok(!/localStorage|sessionStorage|cookies\(\)\.set/.test(src), "must not persist credentials");
  // ESPN's own error body may contain account details and must never be forwarded.
  assert.ok(!/espnBody|await response\.text\(\)/.test(src), "ESPN error bodies must not be forwarded");
  assert.match(src, /AbortSignal\.timeout/, "outbound call must be bounded");
});

test("the discovery response exposes only the safe team list", async () => {
  const src = await read("app/api/leaguepilot/espn/discover/route.ts");
  const shape = src.match(/\.map\(\(t\) => \(\{([^}]+)\}\)\)/);
  assert.ok(shape, "teams must be mapped to an explicit shape");
  const fields = shape[1];
  assert.match(fields, /team_id/);
  assert.match(fields, /name/);
  // Owner identifiers are used for matching but must never be returned.
  assert.ok(!/owners|primaryOwner|swid/i.test(fields), "no ESPN account identifiers may be returned");
});

test("auto-selection only fires on an unambiguous single owner match", async () => {
  const src = await read("app/api/leaguepilot/espn/discover/route.ts");
  assert.match(src, /owned\.length === 1/, "two matches is ambiguous and must fall through to the picker");
});

test("the connect form never asks for a team ID", async () => {
  const src = await read("components/connect-espn-form.tsx");
  assert.ok(!/Your team ID|lp-team-id/.test(src), "the team ID field must be gone");
  assert.match(src, /Which team is yours\?/, "must offer the team picker instead");
  assert.match(src, /parseEspnLeagueLink/, "must accept a pasted league link");
});

test("the espn_connections field allowlist can never return ciphertext", async () => {
  const src = await read("lib/leaguepilot-server.ts");
  const match = src.match(/espn_connections:\s*\{[\s\S]*?fields:\s*\n?\s*"([^"]+)"/);
  assert.ok(match, "espn_connections must declare an explicit field list");
  const fields = match[1].split(",").map((f) => f.trim());
  assert.ok(!fields.includes("credentials_ciphertext"), "ciphertext must never be listed");
  for (const required of ["id", "league_id", "season", "status"]) {
    assert.ok(fields.includes(required), `${required} should be readable`);
  }
});

test("the selected league is stored as a non-secret id and never sent to PocketBase", async () => {
  const src = await read("lib/leaguepilot-client.ts");
  assert.match(src, /localStorage/);
  assert.match(src, /catch \{/, "storage access must be guarded");
  assert.ok(!/selectedConnection[\s\S]{0,400}backendFetch/.test(src));
});
