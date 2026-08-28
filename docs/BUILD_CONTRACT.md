# Build contract — v0.2.1

- **Outcome:** A nearly free ESPN fantasy-football command center that produces personalized,
  scheduled, approval-controlled decisions and league content; structured for eventual sale.
- **Starting point:** Strategic in-place upgrade of the validated v0.1.0 founder build. The ESPN
  boundary, normalized snapshot, database schema and approval model were preserved and extended.
- **Users:** Founder managing one ESPN team; league commissioner sharing reports; future paying
  managers with isolated workspaces.
- **Target:** Python 3.11+, macOS/Linux local beta, inexpensive container hosting later.
- **Required:** ESPN sync, evidence-rich lineup/waiver/trade analysis, weekly reports with a
  deterministic fallback, encrypted notifications, visible data quality, audit/activity history,
  approval state, resilient browser sessions, responsive dashboard and deterministic tests.
- **Non-goals:** Silent ESPN roster writes, payment processing, public OAuth onboarding, betting,
  DFS entry submission and unsupported claims of predictive certainty.
- **Dangerous failures:** Leaking ESPN cookies; cross-workspace data access; fabricated data; AI
  triggering privileged actions; accidental group-chat spam; undocumented API drift.
- **Done:** Package installs; tests, lint, dependency audit and build pass; scheduled-job and
  notification boundaries are regression tested; local server health/UI validate; archive includes
  setup, security, commercialization and rollback instructions.
- **Rollback:** Stop service and restore the `.data` directory backup; source is a self-contained
  archive with no external mutations.
- **Assumptions:** ESPN Football is the initial sport; Discord/GroupMe are the first messaging
  surfaces; LEAGUEPILOT AI is the locked product name.
