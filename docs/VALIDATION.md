# Release validation — v0.4.0

Validated on Python 3.12.13 and Node.js 24.19 on 2026-08-29 UTC.

| Gate | Result |
|---|---|
| Ruff format and lint | Pass |
| Python test suite | 51 passed |
| Application coverage | 83% total |
| CloudPod tenant isolation | Pass with two temporary authenticated tenants |
| Private ESPN credential storage | Pass with synthetic credentials; ciphertext hidden from clients |
| Durable job enqueue | Pass with zero-attempt queued sync job |
| Worker client and completion contract | Pass with HTTPX mock transport |
| ESPN normalization contract | Pass with HTTPX mock transport |
| nflverse ID/status normalization and visible degradation | Pass with HTTPX mock transport |
| Multi-league connection selection and scoped superseding | Pass with static hook contracts |
| Urgent availability alerts and stale-alert retirement | Pass |
| Idempotent CloudPod notification job contract | Pass |
| AES-GCM tamper/context tests | Pass |
| Workspace and CSRF API tests | Pass |
| Founder-login throttling | Pass |
| Scheduled full-job orchestration | Pass with a deterministic fake ESPN boundary |
| Discord delivery and secret-safe errors | Pass with HTTPX mock transport |
| External-AI report fallback | Pass |
| JavaScript syntax | Pass |
| Python compile | Pass |
| Wheel and source distribution | Pass |
| Installed dependency integrity | Pass |
| Known-vulnerability audit | No known vulnerabilities |
| Live server, session, CSRF, demo analysis and security headers | Pass |

## Deliberately unverified

- A real ESPN sync was not attempted because no user league ID or credentials were supplied.
- A live nflverse regular-season 2026 sync cannot validate until the current season report is
  published; 2025 format and failure behavior were verified.
- Discord and GroupMe delivery were not called because no notification target was supplied.
- Pixel-level browser automation was unavailable in the build runtime. The HTML parser, JavaScript
  syntax check, FastAPI static-file test and live HTTP smoke all passed, but a human visual pass is
  still required before marketing screenshots or public release.
- No external message or paid API call was performed.
- The source repository push occurs only after these validation gates pass and does not alter any
  ESPN league or notification channel.
