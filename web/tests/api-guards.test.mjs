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

test("the selected league is stored as a non-secret id and never sent to PocketBase", async () => {
  const src = await read("lib/leaguepilot-client.ts");
  assert.match(src, /localStorage/);
  assert.match(src, /catch \{/, "storage access must be guarded");
  assert.ok(!/selectedConnection[\s\S]{0,400}backendFetch/.test(src));
});
