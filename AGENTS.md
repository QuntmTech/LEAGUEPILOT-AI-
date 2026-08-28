# Repository instructions

- Preserve the normalized `LeagueSnapshot` boundary; raw provider objects stay in provider adapters.
- Never log, return, fixture or commit ESPN cookies, API keys, webhook targets or session tokens.
- Every workspace-scoped query must enforce membership before revealing object existence.
- Model output is prose/advice only. It cannot authorize ESPN, messaging, billing or destructive actions.
- No ESPN write capability without a separate reviewed adapter, preview, idempotency, audit and kill switch.
- Keep missing sports data visibly missing; never manufacture projections, injuries, scores or odds.
- Required checks: `ruff check .`, `pytest --cov=app`, and `python -m build`.
- Update `.env.example`, docs and tests when configuration or public behavior changes.

