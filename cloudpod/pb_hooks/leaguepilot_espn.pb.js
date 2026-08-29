/// <reference path="../pb_data/types.d.ts" />

/**
 * Read-only ESPN league discovery, shared by the web dashboard and the iOS app.
 *
 * Lets a client resolve which team belongs to the signed-in ESPN identity so onboarding
 * never asks a consumer to hunt for a numeric team ID.
 *
 * Kept in its own hook file so the discovery surface can be reviewed, reverted or
 * disabled without touching leaguepilot.pb.js, which carries the connection, analysis and
 * worker contracts the mobile client already depends on. PocketBase loads every *.pb.js
 * in pb_hooks, so this is purely additive.
 *
 * Guarantees:
 * - ESPN is read-only. One GET against the league read host; no mutating verb.
 * - Session values are used in-flight only. Never stored, never logged, never echoed.
 * - Owner identifiers are matched inside leaguepilot_lib.js and never appear in a response.
 * - ESPN's own error body is never forwarded, because an authenticated error response can
 *   carry account information. Callers get fixed, actionable messages instead.
 */
routerAdd(
  "POST",
  "/api/leaguepilot/espn/discover",
  (e) => {
    const {
      bodyOf,
      cleanText,
      integer,
      setPrivateResponse,
      espnFetchLeague,
      espnSafeTeams,
      espnMatchTeam,
    } = require(`${__hooks}/leaguepilot_lib.js`);
    setPrivateResponse(e);

    const body = bodyOf(e);
    const leagueId = integer(body.league_id, "League ID", 1, 999999999999);
    const season = integer(body.season, "Season", 2019, 2100);
    const espnS2 = cleanText(body.espn_s2, 4096);
    const swid = cleanText(body.swid, 200);
    if (!!espnS2 !== !!swid) {
      throw new BadRequestError("Provide both ESPN session values together");
    }

    const result = espnFetchLeague(leagueId, season, espnS2, swid);

    if (result.status === 401 || result.status === 403) {
      return e.json(401, {
        message: espnS2
          ? "ESPN rejected those session values. They may have expired."
          : "That league is private. Add your ESPN session values to continue.",
        needs_credentials: !espnS2,
      });
    }
    if (result.status === 404) {
      return e.json(404, {
        message: "ESPN has no league with that ID for that season.",
      });
    }
    if (result.status !== 200) {
      return e.json(502, {
        message: "ESPN is unavailable right now. Please try again.",
      });
    }

    const teams = espnSafeTeams(result.teams);
    if (teams.length === 0) {
      return e.json(422, {
        message: "ESPN returned no teams for that league and season.",
      });
    }

    return e.json(200, {
      league_id: leagueId,
      season: season,
      league_name: result.leagueName,
      teams: teams,
      matched_team_id: espnMatchTeam(result.teams, swid),
    });
  },
  $apis.requireAuth("users"),
  $apis.bodyLimit(8 * 1024),
);
