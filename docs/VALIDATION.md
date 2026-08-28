# Release validation — v0.2.1

Validated on Python 3.12.13 and Node.js 24.19 on 2026-08-28 UTC.

| Gate | Result |
|---|---|
| Ruff format and lint | Pass |
| Python test suite | 38 passed |
| Application coverage | 86% total |
| ESPN normalization contract | Pass with HTTPX mock transport |
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
- Discord and GroupMe delivery were not called because no notification target was supplied.
- Pixel-level browser automation was unavailable in the build runtime. The HTML parser, JavaScript
  syntax check, FastAPI static-file test and live HTTP smoke all passed, but a human visual pass is
  still required before marketing screenshots or public release.
- No deployment, external message or paid API call was performed.
- The source repository push occurs only after these validation gates pass and does not alter any
  ESPN league or notification channel.
