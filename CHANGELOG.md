# Changelog

## 0.5.0 — 2026-08-30

- Added the authenticated FΛNTΛSY WΛRROOM MCP gateway using the official Python SDK and
  Streamable HTTP transport at `/mcp`.
- Added tenant-scoped league, snapshot, roster, matchup, draft-context, recommendation, report and
  job-status tools with fixed safe field allowlists.
- Added confirmed sync, analysis and recommendation-review tools while preserving the read-only
  ESPN boundary and explicitly reporting that approvals execute no ESPN action.
- Added PocketBase bearer-token verification, OAuth protected-resource metadata, DNS-rebinding
  protection, container packaging and MCP transport/security regression tests.

## 0.4.0 — 2026-08-29

- Added provider-neutral availability evidence and a zero-cost nflverse practice/game-status
  adapter with ESPN-to-GSIS ID mapping, bounded downloads, attribution and visible degradation.
- Added urgent availability-alert analysis and scheduled Thursday/Sunday/Monday inactive sweeps.
- Fixed multi-league analysis selection and scoped recommendation superseding to the exact ESPN
  connection and recommendation kind.
- Added idempotent Discord/GroupMe delivery jobs, encrypted CloudPod channel management and stale
  alert retirement.
- Added copy-paste trade pitches, verified upset callouts and mass-mention/report sanitization.
- Expanded the regression suite from 42 to 51 tests before final validation.

## 0.3.0 — 2026-08-28

- Added a deployed PocketBase control plane with user profiles, workspaces, memberships, encrypted
  ESPN connections, snapshots, recommendations, reports, channels, jobs, usage and audit records.
- Enforced owner-scoped reads, default-deny sensitive writes and cross-tenant 404 behavior.
- Added authenticated internal worker routes with atomic leases, retry/backoff, dead-letter handling
  and expired-lease recovery.
- Added a stateless Python CloudPod worker that preserves the normalized `LeagueSnapshot` boundary,
  runs existing intelligence engines and never performs ESPN writes.
- Captured the live CloudPod schema and deployment hooks in source, plus full operations guidance.
- Expanded the regression suite to 42 tests; lint, tests, coverage and package builds pass.

## 0.2.1 — 2026-08-28

- Reused the workspace's existing ESPN connection when editing league identity, preventing hidden
  duplicate connections and stale synchronization targets.
- Restored owner-only permissions when force-rotating `.env` and redacted database passwords from
  diagnostics.
- Validated encryption keys during startup and stopped unhandled exceptions from returning internal
  diagnostic values.
- Disabled testing of erased notification channels and added coverage for the closed state.
- Moved Gemini credentials from the URL into a header and disabled ambient proxy use for every
  optional AI provider request.
- Extended deterministic report fallback to missing provider configuration and empty model output.
- Preferred ESPN's current scoring period and added a roster-projection fallback when live matchup
  projections are unavailable.
- Prevented the frontend full-analysis workflow from announcing complete success after a partial
  failure.
- Expanded the regression suite to 38 tests with 86% total application coverage.

## 0.2.0 — 2026-08-28

- Locked the product identity as **LEAGUEPILOT AI** while preserving the existing `FCC_`
  configuration contract and legacy CLI alias.
- Added evidence, risk flags, data-quality state and honest projection labeling to recommendations.
- Improved waiver drop selection, trade mutual-fit scoring and transparent power-ranking components.
- Added resilient weekly narration with an explicit deterministic fallback when an optional AI
  provider fails.
- Added encrypted channel management, secret-safe delivery errors, activity history and report
  archive/copy controls.
- Added browser-tab CSRF recovery, CSRF rotation, founder-login throttling and safe credential reuse
  when editing a private ESPN connection.
- Expanded regression coverage from 15 to 27 tests, including scheduled full-job orchestration and
  notification-boundary tests.

## 0.1.0

- Initial owner-operated beta with read-only ESPN sync, deterministic fantasy analyzers, optional AI
  narration, approval state, scheduled jobs and encrypted integrations.
