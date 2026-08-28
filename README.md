# LEAGUEPILOT AI

An ESPN-first fantasy-football intelligence and league-automation platform. It combines live
league context, deterministic optimization, optional AI narration, scheduled analysis, group-chat
delivery and a human approval ledger in one local-first application.

> **Locked product name:** LEAGUEPILOT AI. Existing `FCC_` environment variables remain supported
> so upgrading the earlier founder build does not invalidate configuration or secrets.

## What works in v0.2.1

- Connects public or private ESPN Fantasy Football leagues through an isolated read-only HTTPX
  adapter, without handing account cookies to a third-party service.
- Encrypts `espn_s2`, `SWID`, Discord webhooks and GroupMe bot IDs with AES-256-GCM.
- Produces injury-aware lineup optimization without inventing missing projections.
- Ranks waiver upgrades against a real drop candidate and suggests bounded FAAB percentages.
- Finds preliminary trade matches based on both teams' position strengths and needs.
- Creates transparent power rankings and weekly league reports.
- Uses a deterministic rules narrator for free; Gemini and OpenAI-compatible narration are optional.
- Runs scheduled jobs for every connected workspace and can post results to Discord or GroupMe.
- Records connections, syncs, recommendations, approvals, dismissals, reports and jobs in an audit log.
- Shows the exact projection source, risk flags, trade fairness and mutual-fit evidence behind moves.
- Manages encrypted Discord/GroupMe channels, report history and audit activity from the dashboard.
- Recovers CSRF state across browser tabs and rate-limits repeated failed founder sign-ins.
- Falls back to deterministic narration if an optional external AI provider is unavailable.
- Never lets model output directly execute an ESPN roster change.

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

After deployment, call the protected endpoint with `X-Job-Token`:

```bash
curl --fail-with-body \
  --request POST \
  --header "Content-Type: application/json" \
  --header "X-Job-Token: YOUR_FCC_JOB_TOKEN" \
  --data '{"kind":"lineup","notify":true}' \
  https://YOUR_DEPLOYMENT.example/api/internal/jobs/run
```

The included GitHub Actions workflow shows the four weekly runs. Add `FCC_BASE_URL` and
`FCC_JOB_TOKEN` as repository secrets before enabling scheduled runs in a hosted repository.

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
[docs/SECURITY.md](docs/SECURITY.md), [docs/VALIDATION.md](docs/VALIDATION.md) and
[docs/COMMERCIALIZATION.md](docs/COMMERCIALIZATION.md). The complete Claude Design / ChatGPT Sites
marketing brief is in [docs/LANDING_PAGE_BUILD_BRIEF.md](docs/LANDING_PAGE_BUILD_BRIEF.md).

## Honest limitations

- v0.2.1 is an owner-operated beta, not an unrestricted public SaaS launch.
- Authentication is founder-token-to-HTTP-only-session with single-instance throttling. Public
  launch needs verified email/OAuth, passwordless recovery, distributed rate limiting and
  transactional email.
- SQLite is excellent for a free single-instance beta. Public multi-instance hosting should use
  PostgreSQL after the repository layer and migrations are upgraded.
- Recommendation approval is recorded but does not submit ESPN lineup, waiver or trade actions.
  Browser-driven execution is intentionally excluded until account-risk and terms are resolved.
- Live ESPN validation requires the user's league ID and credentials and was not performed with
  synthetic test data.

## Ownership and licensing

The product source is proprietary to Colton Wood / QuntmTech. Third-party packages retain their
licenses. See [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
