# LEAGUEPILOT authorization server

OAuth 2.1 authorization server for MCP clients that sign in through a browser — Claude.ai
Custom Connectors in particular. It exists because the MCP advertised an authorization
server that did not exist, so dynamic client registration had nothing to talk to.

- Issuer: `https://auth.leaguepilot.quntm.xyz/` (permanent; **not** the dashboard host,
  which runs on temporary cPanel infrastructure)
- Resource: the MCP gateway, `https://mcp.leaguepilot.quntm.xyz/`
- Identity: existing LEAGUEPILOT/PocketBase accounts. **ESPN credentials are never
  requested, accepted or stored by this service.**

## Security properties

| Property | Where |
|---|---|
| Authorization code + S256 PKCE only; `plain` rejected | `keys.verify_pkce` |
| Codes single-use, 60s TTL; replay revokes every derived grant | `server.token` |
| Codes and refresh tokens stored only as SHA-256 hashes | `models` |
| Signing keys and upstream session tokens encrypted at rest (Fernet) | `keys.KeyStore` |
| Key rotation keeps the retiring key published so live tokens still verify | `keys.public_jwks` |
| Refresh tokens rotate on every use; replay invalidates the grant | `server._refresh` |
| Redirect URI mismatch renders an error, never redirects | `server.authorize` |
| Tokens audience-bound to the MCP resource | `tokens` |
| Client ID Metadata Documents: HTTPS-only, SSRF-guarded, no redirects, 64KB cap, must self-identify | `clients` |
| Consent pages: no framing, no caching, escaped output | `server._PAGE_HEADERS`, `pages` |
| Sign-in throttled per identifier and per network, bounded and self-clearing | `throttle` |
| Grant introspection requires a service credential, constant-time compared | `server.grant_state` |

## Scopes

`leaguepilot:read` and `leaguepilot:write`. Both are advertised; neither is enforced at
the MCP transport, because one scope list applies to every request and requiring write
there would stop a read-only grant from connecting at all. Each tool enforces its own
scope. `leaguepilot:write` is never a substitute for `confirmed=true`.

## Deployment notes

Two secrets, each its own credential — never the Claude Code bearer, the worker key, a
signing key, or a PocketBase administrator password:

- `LEAGUEPILOT_AUTH_ENCRYPTION_KEY` — Fernet key. **Not rotatable** without invalidating
  every stored grant. Back it up.
- `LEAGUEPILOT_AUTH_INTROSPECTION_SECRET` — shared with the gateway as
  `LEAGUEPILOT_MCP_INTROSPECTION_SECRET`. Minimum 32 characters.

Both services refuse to start without their secrets, deliberately: a startup failure you
see immediately beats a runtime fail-closed you diagnose later.

The gateway reaches JWKS and introspection over `LEAGUEPILOT_MCP_INTERNAL_AUTH_URL` (a
private origin), while `LEAGUEPILOT_MCP_ISSUER_URL` stays the public issuer. Do not
collapse the two: the issuer is the identity stamped into every token, the internal URL is
only where the bytes travel. `/introspect` should be denied at the public reverse proxy.

## Known limitation — accepted for the first interoperability release

**Pending authorization requests are held in process memory.** Consequences:

- The auth server must run **exactly one worker**. With more, roughly half of all sign-ins
  land on a process that never saw the request and fail with "authorization request
  expired".
- A restart discards in-flight sign-ins. Affected users get the controlled "authorization
  request expired" page.

Nothing already issued is affected: codes, grants, refresh tokens and signing keys are in
SQLite, so a restart never invalidates an existing connection. Only the window between
rendering the consent page and submitting it is at risk.

### Post-interoperability hardening backlog

1. **Move pending authorization requests to shared persistent storage.** This is the only
   thing pinning the worker count to one, and the only reason a restart interrupts a
   sign-in. Highest priority of this list.
2. Move the sign-in throttle to shared storage as well, so budgets are not per process
   once there is more than one.
3. Consider mTLS or a private network policy for gateway-to-auth traffic, rather than
   relying on a shared bearer plus proxy denial.
4. Add an operator view of active grants, so a user can be signed out without a database
   query.
