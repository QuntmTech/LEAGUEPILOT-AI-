# Project state

- **Mission:** Build a nearly free ESPN fantasy intelligence and league automation product with a
  path to commercial launch.
- **Mode:** BUILD.
- **Locked product name:** LEAGUEPILOT AI.
- **Stack:** Python/FastAPI, SQLAlchemy/SQLite beta, vanilla responsive dashboard, isolated HTTPX
  ESPN adapter.
- **Safety locks:** Human approval required; no ESPN writes; no secret values in source/logs/API;
  workspace authorization before object access.
- **Current candidate:** v0.2.1 final hardening built directly on the validated v0.2.0 release.
- **Completed:** Locked-brand integration, evidence-rich intelligence, data-quality warnings,
  session resilience, functional automation controls, report archive, activity feed, resilient AI
  narration and expanded regression coverage.
- **Not validated:** A pixel-level browser run was unavailable in the build runtime; live ESPN sync
  still requires a real user league and credentials.
- **Source repository:** `QuntmTech/LEAGUEPILOT-AI-` on the `main` branch.
- **External actions:** Source push authorized; no deployment, messaging or paid API use performed.
- **Rollback:** Stop the service and restore the prior source archive plus its `.data` backup; no
  external state was mutated during the build.
- **Next:** Pilot against three real ESPN league configurations before any public launch.
