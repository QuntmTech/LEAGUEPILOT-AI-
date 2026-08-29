import assert from "node:assert/strict";
import test from "node:test";
import { readFile } from "node:fs/promises";

/**
 * Transforms the real TypeScript source with esbuild and evaluates it, so this is a
 * behavioural test of the shipped parser rather than a reimplementation of it.
 */
const sourcePath = new URL("../lib/espn-league-url.ts", import.meta.url);
const { transformSync } = await import("esbuild");
const { code } = transformSync(await readFile(sourcePath, "utf8"), {
  loader: "ts",
  format: "cjs",
});
const parserModule = { exports: {} };
new Function("module", "exports", code)(parserModule, parserModule.exports);
const parse = parserModule.exports.parseEspnLeagueLink;

test("parses a full team URL with league, team and season", () => {
  const r = parse("https://fantasy.espn.com/football/team?leagueId=123456&teamId=4&seasonId=2026");
  assert.deepEqual(r, { leagueId: 123456, teamId: 4, season: 2026 });
});

test("parses a league URL with no team", () => {
  const r = parse("https://fantasy.espn.com/football/league?leagueId=987654");
  assert.equal(r.leagueId, 987654);
  assert.equal(r.teamId, null, "team must stay null so the connect flow resolves it");
});

test("parses extra path segments and unrelated query params", () => {
  const r = parse("https://fantasy.espn.com/football/league/scoreboard?leagueId=555&matchupPeriodId=3");
  assert.equal(r.leagueId, 555);
  assert.equal(r.teamId, null);
});

test("accepts a URL with no scheme", () => {
  assert.equal(parse("fantasy.espn.com/football/team?leagueId=42&teamId=7").leagueId, 42);
});

test("accepts a bare numeric league id", () => {
  assert.deepEqual(parse("  1234567 "), { leagueId: 1234567, teamId: null, season: null });
});

test("rejects non-ESPN hosts, including lookalikes", () => {
  for (const host of [
    "https://notespn.com/football/league?leagueId=1",
    "https://espn.com.evil.test/football/league?leagueId=1",
    "https://evil.test/?leagueId=1",
  ]) {
    assert.equal(parse(host).leagueId, null, `${host} must not be trusted`);
  }
});

test("accepts espn.com and its subdomains", () => {
  assert.equal(parse("https://espn.com/football/league?leagueId=9").leagueId, 9);
  assert.equal(parse("https://fantasy.espn.com/football/league?leagueId=9").leagueId, 9);
});

test("rejects non-numeric and out-of-range ids rather than coercing them", () => {
  assert.equal(parse("https://fantasy.espn.com/x?leagueId=12a").leagueId, null);
  assert.equal(parse("https://fantasy.espn.com/x?leagueId=0").leagueId, null);
  assert.equal(parse("https://fantasy.espn.com/x?leagueId=-5").leagueId, null);
  assert.equal(parse("https://fantasy.espn.com/x?teamId=abc").teamId, null);
});

test("returns empty for junk input instead of throwing", () => {
  for (const junk of ["", "   ", "not a url", "://///", "javascript:alert(1)"]) {
    const r = parse(junk);
    assert.equal(r.leagueId, null);
    assert.equal(r.teamId, null);
  }
});
