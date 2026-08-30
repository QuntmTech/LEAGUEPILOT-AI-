# LEAGUEPILOT AI

An ESPN-first fantasy-football intelligence and league-automation platform. It combines live
league context, deterministic optimization, optional AI narration, scheduled analysis, group-chat
delivery and a human approval ledger in one local-first application.

> **Locked product name:** LEAGUEPILOT AI. Existing `FCC_` environment variables remain supported
> so upgrading the earlier founder build does not invalidate configuration or secrets.

## What works in v0.5.0

- Connects public or private ESPN Fantasy Football leagues through an isolated read-only HTTPX
  adapter, without handing account cookies to a third-party service.
- Encrypts `espn_s2`, `SWID`, Discord webhooks and GroupMe bot IDs with AES-256-GCM.
- Enriches ESPN snapshots with independent nflverse practice participation and weekly game-status
  reports in the zero-cost founder beta, with visible missing/stale-data warnings.
- Keeps the normalized availability contract provider-neutral so licensed Sportradar or
  SportsDataIO 90-minute inactive feeds can replace the beta source without rewriting analysis.
- Ranks waiver upgrades against a real drop candidate and suggests bounded FAAB percentages.
- Finds preliminary trade matches based on both teams' position strengths and needs, then generates
  a copy-paste pitch written for the other manager.
- Creates transparent power rankings and safer, personality-forward weekly league reports.
- Uses a deterministic rules narrator for free; Gemini and OpenAI-compatible narration are optional.
- Runs connection-scoped analysis for multiple leagues per user, schedules lineup-lock sweeps, and
  can post idempotent results to encrypted Discord or GroupMe channels.
- Records connections, syncs, recommendations, approvals, dismissals, reports and jobs in an audit log.
- Shows the exact projection source, risk flags, trade fairness and mutual-fit evidence behind moves.
- Manages encrypted Discord/GroupMe channels, report history and audit activity from the dashboard.
- Recovers CSRF state across browser tabs and rate-limits repeated failed founder sign-ins.
- Falls back to deterministic narration if an optional external AI provider is unavailable.
- Never lets model output directly execute an ESPN roster change.
- Runs a hosted PocketBase control plane with per-user workspaces and default-deny internal writes.
- Queues ESPN sync and analysis work through atomic leases, retries and dead-letter handling.
- Scales stateless read-only ESPN workers horizontally without exposing credentials in result payloads.
- Exposes the authenticated FΛNTΛSY WΛRROOM MCP gateway over Streamable HTTP with safe league,
  roster, matchup, recommendation, report and job tools plus confirmed queue/review operations.

## Fastest local setup on macOS or Linux

Run from the repository root:

```bash
chmod +x scripts/start-local.sh
./scripts/start-local.sh
```

The first run creates a virtual environment, installs dependencies and generates `.env` with
owner-only permissions. Open [http://127.0.0.1:8765](http://127.0.0.1:8765), then paste the
`FCC_ADMIN_TOKEN` printed in Terminal.

For an instant product tour, set `FCC_DEMO_MODE=true` in `.env` before starting. The dashboard
loads fictional players and makes every analysis engine usable without ESPN credentials. Demo data
is visibly labeled, never mixed with a real sync and rejected by production configuration.

### Manual setup

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
python -m app.cli init
python -m app.cli doctor
python -m app.cli serve
```

## Connect ESPN

1. Open **Connections → Connect your league**.
2. Enter the league ID, season and your team ID.
3. For a private league, obtain `espn_s2` and `SWID` from the ESPN cookies in your browser.
4. Save, then synchronize. Raw credentials are never returned to the browser or written to logs.

ESPN does not publish or support this fantasy API. The connector is therefore isolated behind
`app/services/espn.py`, has explicit failure states and must be regression-tested before each season.

## Scheduled jobs

CloudPod queues tenant-scoped lineup-lock sweeps and analysis requests. The included GitHub Actions
workflow is a cost-efficient founder-beta worker that drains that queue every five minutes. Add the
repository Actions secret `FCC_CLOUDPOD_WORKER_KEY` with the same value as CloudPod's existing
`LEAGUEPILOT_WORKER_KEY`; never put the value in source. Move to monitored long-running container
workers before promising real-time service at production scale.

## Hosted CloudPod worker

The live v0.4.0 control plane is `https://leaguepilot-ai.cloudpod.pro`. Configure a worker with
`FCC_CLOUDPOD_URL`, `FCC_CLOUDPOD_WORKER_KEY` and a unique `FCC_CLOUDPOD_WORKER_ID`, then run:

```bash
leaguepilot-ai worker
```

See [docs/CLOUDPOD_BACKEND.md](docs/CLOUDPOD_BACKEND.md) for the schema, routes, deployment flow,
security boundaries and honest scale envelope.

## FΛNTΛSY WΛRROOM MCP

Run the private MCP gateway on port 8787:

```bash
leaguepilot-mcp
```

The authenticated Streamable HTTP endpoint is `/mcp`. The MCP reuses PocketBase tenant rules and
never calls ESPN directly. Private bearer-token use is implemented; public one-click ChatGPT
account linking still requires a real OAuth 2.1 issuer and deployment verification. See
[docs/MCP_SERVER.md](docs/MCP_SERVER.md) for tools, security boundaries, testing and deployment.

## Validation

```bash
source .venv/bin/activate
ruff check .
pytest --cov=app --cov-report=term-missing --cov-fail-under=80
pip-audit --local --progress-spinner off
python -m build
```

See [CHANGELOG.md](CHANGELOG.md), [docs/SETUP.md](docs/SETUP.md),
[docs/PILOT_PLAN.md](docs/PILOT_PLAN.md), [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md),
[docs/SECURITY.md](docs/SECURITY.md), [docs/VALIDATION.md](docs/VALIDATION.md),
[docs/CLOUDPOD_BACKEND.md](docs/CLOUDPOD_BACKEND.md) and
[docs/COMMERCIALIZATION.md](docs/COMMERCIALIZATION.md). The complete Claude Design / ChatGPT Sites
marketing brief is in [docs/LANDING_PAGE_BUILD_BRIEF.md](docs/LANDING_PAGE_BUILD_BRIEF.md).
The credit-efficient app briefs are in [docs/RORK_MOBILE_MVP_PROMPT.md](docs/RORK_MOBILE_MVP_PROMPT.md)
and [docs/CHATGPT_SITES_DASHBOARD_PROMPT.md](docs/CHATGPT_SITES_DASHBOARD_PROMPT.md).

## Honest limitations

- v0.4.0 is a hosted multi-tenant beta foundation, not an unrestricted public SaaS launch.
- The MCP is private-client ready, but not ready for public plugin submission until OAuth 2.1
  account linking and a stable public HTTPS deployment pass ChatGPT and MCP Inspector testing.
- Authentication is founder-token-to-HTTP-only-session with single-instance throttling. Public
  launch needs verified email/OAuth, passwordless recovery, distributed rate limiting and
  transactional email.
- CloudPod/PocketBase is a single SQLite-backed control-plane node. Stateless workers scale
  horizontally, but thousands-user claims require measured load tests and a PostgreSQL migration
  plan if write contention or multi-region requirements exceed the node's envelope.
- Recommendation approval is recorded but does not submit ESPN lineup, waiver or trade actions.
  Browser-driven execution is intentionally excluded until account-risk and terms are resolved.
- Live ESPN validation requires the user's league ID and credentials and was not performed with
  synthetic test data.
- nflverse is suitable for the cheap founder beta but is not the contractual real-time inactive
  feed for a paid launch. A licensed provider remains a production launch gate.

## Ownership and licensing

The product source is proprietary to Colton Wood / QuntmTech. Third-party packages retain their
licenses. See [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

## Web homepage and authenticated dashboard

The complete production web experience now lives in [`web/`](web/):

- Public marketing homepage at `/`
- PocketBase authentication routes
- Protected dashboard at `/app`
- Fictional interactive review route at `/dashboard-preview`
- Responsive desktop, iPhone, and Android web layouts

Start with [`docs/WEB_DASHBOARD_HANDOFF.md`](docs/WEB_DASHBOARD_HANDOFF.md) before editing or
deploying the web application. The existing Python backend and the mobile application remain
separate from `web/`.
