# Security model

## Protected assets

- ESPN session cookies and league data.
- Discord webhooks and GroupMe bot identifiers.
- Cross-workspace recommendations, reports and audit history.
- Founder/session/job tokens.

## Implemented controls

- AES-256-GCM with context-bound additional authenticated data for stored integration secrets.
- Raw API and session tokens are represented in the database only by SHA-256 digests. Tokens are
  generated with a cryptographic random source and contain high entropy.
- Browser sessions use `HttpOnly`, `SameSite=Strict` cookies, secure cookies in production and a
  separately rotated CSRF cookie/token for every unsafe method and browser tab.
- Repeated founder-login failures are throttled with a single-instance sliding window.
- Workspace lookups are authorized before object existence is revealed.
- API responses receive CSP, anti-framing, MIME-sniffing, referrer and permissions headers.
- External strings are length-bounded and treated as data, never prompt instructions.
- AI output cannot authorize or execute ESPN, notification, billing or destructive actions.
- Exceptions redact the current ESPN cookie before creating a user-safe integration error.
- Notification targets are allow-listed and length-bounded; delivery disables redirects, ignores
  ambient proxy settings and returns errors that never include the encrypted target.
- Disabling a notification channel replaces the encrypted target so the webhook or bot ID is no
  longer retained.
- `.env`, databases, caches and coverage outputs are ignored by Git.

## Before public launch

1. Replace the bootstrap-token login with verified OAuth or magic-link authentication and safe
   recovery.
2. Add Redis-backed distributed rate limiting, abuse detection and session revocation UX.
3. Move encryption keys to a managed secret store and document rotation with dual-read migration.
4. Move to PostgreSQL, run cross-tenant tests against production policies and add backups/restore tests.
5. Add SBOM and container scanning alongside the existing dependency audit; commission an external
   security review.
6. Add retention/deletion controls, privacy terms, subprocessor disclosures and export/delete flows.
7. Review ESPN terms and trademark use with counsel before charging users.

## Incident response

If an ESPN cookie is exposed: revoke ESPN sessions, rotate the application encryption key through a
controlled re-encryption migration, revoke browser/API sessions, preserve audit logs and notify the
affected workspace. Never paste cookies into issues, support chat or screenshots.
