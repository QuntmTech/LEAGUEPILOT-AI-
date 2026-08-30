# FΛNTΛSY WΛRROOM MCP server

`FΛNTΛSY WΛRROOM 🏈⚡` is the authenticated MCP gateway for LEAGUEPILOT. It exposes
tenant-scoped fantasy data and controlled queue/review operations through the official MCP Python
SDK. It does not call ESPN directly. The existing CloudPod backend remains the only control plane,
and the existing worker remains the only ESPN data path.

## Current readiness

| Capability | State |
|---|---|
| Streamable HTTP transport | Implemented at `/mcp` |
| MCP initialization and tool discovery | Implemented |
| PocketBase bearer-token verification | Implemented |
| Tenant authorization | Enforced again by every PocketBase collection rule and hook |
| Read-only league tools | Implemented |
| Confirmed queue/review tools | Implemented |
| ESPN transaction execution | Intentionally unavailable |
| Private MCP use with an existing PocketBase token | Ready |
| Public one-click ChatGPT account linking | Blocked on a real OAuth 2.1 issuer |

The protected-resource metadata route is present. `LEAGUEPILOT_MCP_ISSUER_URL` must point to a real
OAuth 2.1 or OpenID Connect issuer before public ChatGPT distribution. PocketBase user tokens work
as bearer tokens for private clients, but PocketBase is not an MCP-compatible OAuth authorization
server by itself. Do not describe public account linking as complete until authorization-code +
PKCE, discovery metadata, the `resource` parameter, and a supported client-registration method pass
an end-to-end ChatGPT test.

## Tools

| Tool | Behavior | State change |
|---|---|---|
| `leaguepilot_health` | Checks the CloudPod service and queue | No |
| `list_leagues` | Returns the current workspace and safe league connections | No |
| `get_league_snapshot` | Returns the latest normalized provider-neutral snapshot | No |
| `get_roster` | Returns a team roster from the latest snapshot | No |
| `get_matchup` | Returns the configured team's matchup for a week | No |
| `get_draft_context` | Returns snapshot-based roster needs and candidate players | No |
| `list_recommendations` | Lists safe, filtered recommendations | No |
| `get_weekly_report` | Returns the latest or requested weekly report | No |
| `get_job_status` | Returns safe queue state without leases or worker secrets | No |
| `sync_league` | Queues a read-only ESPN sync | Yes; requires `confirmed=true` |
| `run_analysis` | Queues deterministic analysis | Yes; requires `confirmed=true` |
| `review_recommendation` | Records approved/dismissed intent only | Yes; requires `confirmed=true` |

There is no `make_draft_pick`, lineup mutation, waiver submission, trade submission, internal job
claim, job completion, or job failure tool. MCP consumers must not infer that an approved
recommendation was executed on ESPN. The review response must continue to report
`espn_action_executed: false`.

`get_draft_context` is deliberately honest: it is based on the last completed snapshot, not a live
ESPN draft-room event feed. It must display its staleness warning. A future live draft adapter may
replace this limitation only after it supplies pick order, drafted-player events, available-player
state, timestamps, retries, and reconciliation tests.

## Run locally

```bash
python -m pip install -e '.[dev]'
export LEAGUEPILOT_MCP_PUBLIC_URL=http://127.0.0.1:8787
leaguepilot-mcp
```

The endpoints are:

- `http://127.0.0.1:8787/mcp` — authenticated Streamable HTTP MCP endpoint
- `http://127.0.0.1:8787/healthz` — process health only; it does not prove CloudPod access
- `http://127.0.0.1:8787/.well-known/oauth-protected-resource` — MCP authorization metadata

For Docker:

```bash
docker compose up --build fantasy-warroom-mcp
```

## Private-client authentication

Private MCP clients send the existing PocketBase user token in the request header:

```text
Authorization: Bearer <PocketBase user token>
```

Never place that token in source, a prompt, a chat message, logs, screenshots, or an MCP tool
argument. The verifier calls PocketBase's authenticated refresh endpoint and turns a valid session
into the MCP request identity. Every subsequent collection read and hook call forwards the same
token, so PocketBase still enforces `owner = @request.auth.id`.

For an everyday consumer, the Web AI must add a secure account-linking page; consumers should not
copy tokens. Public ChatGPT linking should use OAuth 2.1 and keep PocketBase tokens server-side.

## Result contract

Every tool returns the same top-level envelope:

```json
{
  "status": "ok | queued | unavailable",
  "data": {},
  "as_of": "ISO-8601 timestamp",
  "source": "LEAGUEPILOT CloudPod",
  "data_quality": "live | cached | stale | missing",
  "warnings": [],
  "missing_fields": [],
  "next_actions": [],
  "correlation_id": "opaque request correlation id"
}
```

Missing snapshots are returned as unavailable rather than filled with invented players or scores.
Queued operations return a job ID and direct the caller to `get_job_status`.

## Production deployment gates

1. Merge the MCP branch only after the repository gates pass.
2. Deploy `Dockerfile.mcp` as a separate always-on service.
3. Set `LEAGUEPILOT_MCP_PUBLIC_URL` to the exact stable HTTPS origin, excluding `/mcp`.
4. Restrict ingress, configure TLS, rate limits, secret redaction, logs, metrics, and rollback.
5. Configure a real OAuth 2.1/OIDC issuer and supported OpenAI client registration.
6. Verify `/.well-known/oauth-protected-resource` and the issuer discovery document.
7. Run MCP Inspector against the production `/mcp` URL.
8. Call every tool with valid, invalid, cross-tenant, empty, stale, and expired-session cases.
9. Connect in ChatGPT Developer Mode and rerun the evaluation set.
10. Do not submit publicly until account linking and privacy/terms documentation pass review.

## Client responsibilities

The web and mobile applications do not embed the MCP server. They keep using CloudPod directly.
MCP is an additional agent-facing interface over the same records and hooks.

- Web owns consumer account linking, OAuth consent/callback UX, MCP connection status, and a clear
  “snapshot-based, not live draft room” disclosure.
- Mobile owns displaying the same connection, job, snapshot, recommendation, report, and review
  states. It should not add an independent ESPN or MCP implementation.
- Backend owns tenant enforcement, tool contracts, OAuth token exchange/storage, rate limiting,
  observability, and the persistent worker.
