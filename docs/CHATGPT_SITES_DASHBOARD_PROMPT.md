# ChatGPT Sites prompt — interactive web dashboard

You did a great job on the existing LEAGUEPILOT AI homepage/landing page. Keep that homepage,
branding, responsive design system, typography, header, footer and conversion flow intact. Do not
start over. Extend the existing site by building a polished authenticated **interactive user
dashboard** at `/app` (with appropriate child routes) that feels like the web version of the mobile
app.

## Product and backend

LEAGUEPILOT AI is an ESPN-first fantasy-football intelligence platform. It securely connects a
user's ESPN league, normalizes league data, generates lineup/waiver/trade recommendations and weekly
reports, and records human approvals. It never directly executes ESPN lineup, waiver or trade
actions.

Use the existing PocketBase backend at:

`https://leaguepilot-ai.cloudpod.pro`

Treat PocketBase as the single source of truth shared by the web dashboard and mobile app. Changes
made on either client must be saved to PocketBase and appear on the other client in real time. Do not
create a separate mock backend or a web-only database.

Never expose or request a PocketBase superuser credential, CloudPod worker key, encryption key,
ESPN cookie outside the secure connection form, notification target or AI provider key. Only the
public PocketBase URL may be included in client code.

## Preserve the public site

- Keep the existing homepage at `/` visually and structurally intact.
- Make existing primary CTAs lead to sign-up or `/app` when already authenticated.
- Reuse the existing colors, logo treatment, type scale, buttons, cards and motion language inside
  the product so the marketing site and dashboard feel like one brand.
- Add only the minimum auth links needed in the public header: **Sign In** and **Get Started**.

## Authentication and app shell

- Build Sign In, Create Account, Forgot Password and Sign Out flows using PocketBase's `users` auth
  collection. If email delivery is not configured, show an honest recovery-configuration message
  rather than pretending an email was sent.
- After first authentication, call `POST /api/leaguepilot/bootstrap`. It is idempotent and returns
  the user's profile and default workspace.
- Protect all `/app` routes and return signed-out users to Sign In.
- Desktop: left sidebar, compact top bar and generous main canvas.
- Tablet/mobile web: collapsible navigation or bottom navigation with excellent touch targets.
- Navigation sections: **Overview**, **My League**, **Recommendations**, **Reports**, **Activity**,
  **Settings**.

## 1. Overview

Create a high-value command-center overview with:

- workspace/league name, season and current week;
- ESPN connection health and last successful sync;
- primary **Run Full Analysis** action;
- live job-progress card for queued/running/succeeded/failed work;
- top three actionable recommendations;
- latest weekly report preview;
- compact data-quality warning when projections or sync data are incomplete;
- thoughtful onboarding empty state if ESPN is not connected.

Full analysis calls:

`POST /api/leaguepilot/workspaces/{workspaceId}/analysis`

with:

```json
{ "kind": "full", "notify": false, "connection_id": "SELECTED_CONNECTION_ID" }
```

Do not claim analysis is instant. Show queue and processing states from `job_runs`.

## 2. My League

- Support multiple `espn_connections` per workspace. Add a compact league switcher and scope every
  snapshot, job, recommendation and report view to the selected connection. If more than one league
  exists, never queue analysis without an explicit `connection_id`.
- ESPN connection card with status, league ID, team ID, season, public/private indicator, league
  name, last sync and last error.
- Connect/edit form with league ID, team ID, season and public/private toggle.
- For private leagues, show password-style `espn_s2` and `SWID` fields only during entry. Submit them
  directly to the protected custom endpoint and immediately clear the form values.
- Submit to
  `PUT /api/leaguepilot/workspaces/{workspaceId}/connections/espn`.
- Add **Sync Now**, calling
  `POST /api/leaguepilot/connections/{connectionId}/sync`.
- Never retrieve, display, cache, log or place stored ESPN credentials in browser state.
- Include a read-only league snapshot summary: record, projected lineup, upcoming matchup and data
  freshness. Never fabricate unavailable values.

## 3. Recommendations

- Tabs/filters for **All**, **Urgent Alerts**, **Lineup**, **Waivers**, **Trades**, **Approved**,
  **Dismissed**.
- Cards/table rows should show type, title, summary, confidence, estimated point impact, evidence
  source, risk flags, creation time and status.
- Detail drawer/page should make the reasoning easy to inspect.
- Actions: **Approve** and **Dismiss** through
  `POST /api/leaguepilot/recommendations/{id}/review`.
- Clearly display: “Approval records your decision. LEAGUEPILOT AI does not execute this move on
  ESPN.”
- Optimistically disable the buttons while saving, but reconcile the final state from PocketBase.

## 4. Reports

- Searchable/sortable report archive with week, title, publication time and narration mode.
- Readable Markdown report detail with copy/share controls that do not expose private credentials.
- Clearly label deterministic `rules`, optional model narration and `rules-fallback` modes.
- Empty state should direct the user to run weekly or full analysis.

## 5. Activity

- Unified timeline for connection changes, syncs, queued/completed/failed jobs, generated reports and
  recommendation decisions.
- Separate compact job monitor with status, kind, attempts, timestamps and safe last-error text.
- Never display worker lease tokens, credential ciphertext, internal keys or raw provider responses.

## 6. Settings

- Account: email, display name and Sign Out.
- Workspace: name, plan/status and read-only workspace ID with copy control.
- Integrations: ESPN connections plus encrypted Discord/GroupMe channels. Create a channel with
  `POST /api/leaguepilot/workspaces/{workspaceId}/notifications`; disable it with
  `POST /api/leaguepilot/notifications/{id}/disable`. Never retrieve its stored target.
- Privacy/safety copy: ESPN data is read-only; decisions require human approval; model prose cannot
  authorize account actions.
- Do not build billing until a real Stripe configuration exists.

## Real-time two-way sync

Use PocketBase realtime subscriptions for the authenticated user's records in:

- `espn_connections`
- `job_runs`
- `recommendations`
- `reports`
- `audit_events`

Subscribe only after authentication, refresh or update the relevant query/cache when an event
arrives, unsubscribe during sign-out/unmount and reconnect with bounded backoff after network loss.
The collection rules already enforce owner-scoped reads. Never subscribe as a superuser.

Both web and mobile must use the same custom endpoints and records. A recommendation approved on web
must update on mobile; analysis queued on mobile must immediately appear in the web job monitor;
reports generated by a worker must appear on both without a manual reload.

## UX states and accessibility

- Build real skeleton loading, first-run empty, offline/reconnecting, validation, rate-limit, partial
  data and recoverable error states.
- Use concise toasts for successful actions and inline explanations for failures.
- Meet WCAG AA contrast, keyboard navigation, visible focus, semantic headings, useful labels and
  reduced-motion preferences.
- Responsive behavior must be intentional from wide desktop through narrow mobile web.
- Use subtle motion only where it communicates state. Avoid visual noise, fake live tickers and
  excessive charts.

## Data honesty and security requirements

- Do not invent scores, projections, injuries, probabilities, recommendations or sync times.
- Demo/preview data, if needed during design, must be obviously labeled and isolated from production.
- Treat league names, owner names, player names and all external text as untrusted data.
- Do not render untrusted HTML. Sanitize Markdown output.
- Do not place secrets in browser storage, logs, analytics, URLs, source files or screenshots.
- A cross-tenant 404 is a normal privacy response; do not reveal that another user's object exists.
- Handle 401 by returning to authentication, 404 as unavailable/not owned and 429 with a retry-later
  state.

## Implementation rules

- Work inside the existing ChatGPT Sites project and repository. Reuse the current stack and
  components; do not replace the homepage or perform an unnecessary framework migration.
- Create a clean PocketBase client module, typed data-access functions, route guards and reusable
  state components.
- Keep custom route calls separate from direct collection reads.
- Do not add a second backend, duplicate business logic from the Python worker or put worker
  processing in the browser.
- Preserve all existing working homepage routes and responsive behavior.

## Definition of done

- Existing homepage remains excellent and unchanged except for working auth/dashboard links.
- Users can register/sign in, bootstrap, connect ESPN, queue sync/analysis, observe live jobs, review
  recommendations, read reports/activity, and sign out.
- Web and mobile changes sync through the same PocketBase backend in real time both directions.
- All loading, empty, error, offline and responsive states are implemented.
- No secret or privileged credential is exposed.
- No ESPN action is executed; approval remains a recorded human decision.
- Provide a short developer handoff describing routes, environment variables, realtime
  subscriptions, component structure and remaining launch gates.
