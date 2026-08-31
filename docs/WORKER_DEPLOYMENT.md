# Persistent worker deployment

## Why this exists

GitHub Actions scheduling is best-effort. Measured against production history over a
38.1-hour window (2026-08-29 07:26Z → 2026-08-30 21:29Z):

| Metric | Value |
|---|---|
| Expected runs at `*/5` | 457 |
| Actual scheduled runs | 11 |
| Delivery rate | **2.4%** |
| Mean gap between runs | 3.81 h |
| Worst observed gap | 5.87 h |
| Mean run duration | 228 s |
| **Worker duty cycle** | **1.66%** |

Every scheduled run *succeeded*. The problem is not reliability of starting — it is that
the queue is unattended ~98% of the time.

This matters most for the Sunday inactive sweep. PocketBase's in-process `cronAdd`
enqueues it on time; the GitHub worker then drains it hours later:

```
Sunday 1pm ET kickoff  = 17:00 UTC
  sweep enqueued         16:30 UTC   on time
  worst-case drained     22:22 UTC   +5.87 h — after the lineup locked
```

No cron expression fixes a worker that is asleep. `scheduled-analysis.yml` is unchanged
and stays enabled as a **fallback**.

## Services on the container host

| Service | Exposure | Purpose |
|---|---|---|
| `fantasy-warroom-mcp` | public HTTPS `/mcp` | MCP gateway |
| `leaguepilot-worker` | **none** — outbound only | persistent queue drain |

The worker binds no port and accepts no inbound connections. It dials CloudPod.

## Configuration

| Variable | Value | Notes |
|---|---|---|
| `FCC_CLOUDPOD_URL` | `https://leaguepilot-ai.cloudpod.pro` | set in compose |
| `FCC_CLOUDPOD_WORKER_KEY` | **secret store only** | never in compose, never committed |
| `FCC_CLOUDPOD_WORKER_ID` | unique per replica | defaults to `leaguepilot-worker-1` |
| `FCC_WORKER_POLL_SECONDS` | `3` | valid range 0.25–60 |

The key is loaded as a Pydantic `SecretStr`, so it does not appear in reprs or tracebacks.

## Duplicate processing

Running this worker alongside the GitHub fallback is safe. `/internal/jobs/claim`
selects and leases inside `$app.runInTransaction`, setting `status = "running"`,
`lease_expires_at` (+5 min) and `lease_token_hash` atomically. Only one worker can claim
a given job; a second sees no queued row. Completion requires the matching lease token —
`validateLease` rejects anything else — so a stale worker cannot overwrite a job another
worker finished.

Abandoned leases are recovered by the `leaguepilot-requeue-expired-leases` cron
(`*/2 * * * *`, in-process in PocketBase), which requeues `running` jobs whose lease has
expired, or dead-letters them past `max_attempts`.

## Health checks

The main `Dockerfile` probes the web API on `:8765`. **Do not reuse it here** — this
image runs no HTTP server, so that check would mark a healthy worker unhealthy on every
interval.

`Dockerfile.worker` instead asserts liveness from the drain loop itself. The worker
writes `FCC_WORKER_LIVENESS_PATH` (default `/tmp/leaguepilot-worker.heartbeat`) on every
iteration. **The health check reads the same variable with the same default**, so
overriding it moves writer and reader together — hardcoding the path in the check would
silently mark an otherwise healthy container unhealthy forever. A regression test asserts
both defaults stay in sync.

The worker writes that file on every — including idle polls, so an idle worker stays healthy while a wedged one does
not. The container is unhealthy if that file is older than 180 s, a window deliberately
generous against a slow ESPN fetch or a long analysis so one slow job cannot flap the
container.

Separately, the worker POSTs `/internal/workers/heartbeat` every 30 s, which is what
populates `worker_nodes` for operational monitoring.

## Deploy

```bash
docker compose build leaguepilot-worker
docker compose up -d leaguepilot-worker
docker compose ps leaguepilot-worker          # expect Up (healthy)
docker compose logs -f leaguepilot-worker
```

## Post-deployment verification

1. **Heartbeat** — a `worker_nodes` row with your `FCC_CLOUDPOD_WORKER_ID`,
   `status: online`, `last_seen_at` within 30 s.
2. **Claim latency** — queue a sync; it should move `queued → running` within ~3–10 s.
3. **Full lifecycle** — `queued → running → succeeded`, `attempts: 1`.
4. **Restart recovery** — `docker compose restart leaguepilot-worker`; confirm it
   re-heartbeats and drains the next job.
5. **Lease recovery** — kill the container mid-job (`docker compose kill`); within ~5 min
   the lease expires and the requeue cron returns the job to `queued`.
6. **Secret redaction** — `docker compose logs leaguepilot-worker` must contain no
   `espn_s2`, `SWID`, worker key or lease token. ESPN errors are scrubbed in
   `app/services/espn.py` before logging.

## Scaling

Raise `FCC_CLOUDPOD_WORKER_ID` uniqueness per replica and scale out. Atomic leasing makes
concurrent workers safe. Keep `FCC_WORKER_POLL_SECONDS` at or above 3 to avoid
unnecessary load on a single-node PocketBase.
