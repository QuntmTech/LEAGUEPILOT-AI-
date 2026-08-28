# Setup and operation

## Local founder beta

1. Run `./scripts/start-local.sh` in the project root.
2. Open `http://127.0.0.1:8765`.
3. Paste the founder token printed during initialization.
4. Open **Connections**, enter the ESPN values and synchronize.
5. Run Full Analysis, then review each recommendation.

The installed command is `leaguepilot-ai`; the legacy `fantasy-command-center` command remains as a
compatibility alias for existing local setups.

To tour the product before connecting ESPN, set `FCC_DEMO_MODE=true` in `.env` and restart. The
seeded league and players are fictional and visibly labeled. Production configuration refuses to
start with demo mode enabled.

## Rotate local access

Stop the server, back up `.data`, then run `python -m app.cli init --force`. This rotates the
environment tokens and encryption key, so existing encrypted integration credentials will no longer
decrypt. For a live product, implement dual-key re-encryption before rotation.

## Backup

Stop writes, then copy the `.data` directory to a protected location. Restore by stopping the service,
replacing `.data` with the known-good copy and restarting. Test this before relying on it.

## Optional AI

Keep `FCC_AI_PROVIDER=rules` for zero API cost. To use another provider, set the provider, exact model,
API key and—only for OpenAI-compatible services—the base URL. Model names and prices are volatile;
verify them when configuring deployment rather than hard-coding them in this durable guide.
