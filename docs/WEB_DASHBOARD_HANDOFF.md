# LEAGUEPILOT AI — Complete Website + Dashboard Handoff

Prepared August 28, 2026 for Colton Wood / QuntmTech.

## Live URLs

- Homepage: https://leaguepilot-ai.amplycoindustries.chatgpt.site/
- Interactive dashboard preview: https://leaguepilot-ai.amplycoindustries.chatgpt.site/dashboard-preview
- Real authenticated dashboard: https://leaguepilot-ai.amplycoindustries.chatgpt.site/app
- Sign in: https://leaguepilot-ai.amplycoindustries.chatgpt.site/sign-in
- Create account: https://leaguepilot-ai.amplycoindustries.chatgpt.site/create-account
- Password recovery: https://leaguepilot-ai.amplycoindustries.chatgpt.site/forgot-password

Deployed source commit: f797d4c3644eae66f671d6aad684d322bb5b4ec8

## Read this first

This ZIP contains the complete source used for the live homepage and web dashboard. It is not one static HTML file. It is a full-stack React/TypeScript application using Next.js App Router conventions, Vinext, Vite, Tailwind CSS, Shadcn UI, Cloudflare Workers, and PocketBase.

The browser HTML is generated from TSX:

- app/page.tsx — public homepage
- components/leaguepilot-dashboard.tsx — dashboard interface
- components/leaguepilot-auth.tsx — authentication interface
- app/globals.css — homepage design
- app/platform.css — dashboard and authentication design
- app/api/**/route.ts — protected server routes

Do not flatten this into one index.html. That would remove protected routes, secure cookies, backend proxying, reusable components, and current deployment behavior.

## Product surfaces

### Public homepage at /

Includes sticky navigation, mobile drawer, hero, fictional command-center demonstration, problem/solution comparison, feature bento grid, five-step workflow, human-approval section, data-honesty section, group-chat recap demo, user segments, transparent planned tiers, FAQ, Founder Beta form, mobile sticky CTA, evidence drawer, footer, and legal disclaimer.

Main files:

- app/page.tsx
- app/globals.css
- app/layout.tsx
- public/favicon.svg

### Authentication

Routes:

- /sign-in
- /create-account
- /forgot-password
- /app redirects to /sign-in without a session

Main files:

- components/leaguepilot-auth.tsx
- app/sign-in/page.tsx
- app/create-account/page.tsx
- app/forgot-password/page.tsx
- app/api/auth/login/route.ts
- app/api/auth/register/route.ts
- app/api/auth/forgot-password/route.ts
- app/api/auth/logout/route.ts
- app/api/auth/session/route.ts
- lib/leaguepilot-server.ts

### Authenticated dashboard at /app

Sections:

1. Overview
2. My League
3. Recommendations
4. Reports
5. Activity
6. Settings

It includes desktop sidebar navigation, compact top bar, mobile drawer, fixed mobile bottom navigation, safe-area support for iPhones, PocketBase session refresh, bootstrap loading, ESPN status, league context, last sync, warnings, roster, reports, recommendation evidence, real Full Analysis requests, job-state display, four-second polling, and honest loading/empty/error/first-run states.

Main files:

- app/app/page.tsx
- components/leaguepilot-dashboard.tsx
- app/platform.css
- app/api/leaguepilot/bootstrap/route.ts
- app/api/leaguepilot/workspaces/[workspaceId]/analysis/route.ts

### Public preview at /dashboard-preview

This is a clearly labeled fictional review environment. It contains fictional league records and a simulated queued → running → succeeded analysis flow. It never writes to PocketBase.

Main file:

- app/dashboard-preview/page.tsx

## Technology

- Node.js 22.13.0+
- React 19
- Next.js 16 structure
- Vinext
- Vite 8
- TypeScript
- Tailwind CSS 4
- Shadcn UI
- Lucide icons
- Sonner notifications
- Cloudflare Workers
- PocketBase
- ChatGPT Sites

## Brand system

| Token | Value |
|---|---|
| Deep forest | #122F28 |
| Primary green | #1D5949 |
| Secondary green | #2F7A63 |
| Warm paper | #F5F1E8 |
| Secondary paper | #ECE6DA |
| Panel white | #FFFDF8 |
| Lime accent | #B8DC73 |
| Gold accent | #E4B949 |
| Dark text | #17221F |
| Muted text | #6E7772 |
| Risk red | #B75042 |

Homepage CSS belongs in app/globals.css. Dashboard/authentication CSS uses isolated .lp-* selectors in app/platform.css. Keep that separation.

## PocketBase

Backend:

    https://leaguepilot-ai.cloudpod.pro

The constant is in lib/leaguepilot-server.ts.

Standard endpoints used:

    POST /api/collections/users/records
    POST /api/collections/users/auth-with-password
    POST /api/collections/users/auth-refresh
    POST /api/collections/users/request-password-reset

Custom endpoints used:

    POST /api/leaguepilot/bootstrap
    POST /api/leaguepilot/workspaces/{workspaceId}/analysis

Analysis body:

    {
      "kind": "full",
      "notify": false
    }

Authentication flow:

1. Browser sends credentials to a same-origin /api/auth route.
2. Server calls PocketBase.
3. PocketBase returns a token.
4. Server stores it in a seven-day HttpOnly, Secure, SameSite=Lax cookie named leaguepilot_session.
5. Dashboard calls same-origin server routes.
6. Server adds the PocketBase bearer token.

Never move the token into localStorage. Never expose PocketBase superuser credentials, worker keys, encryption keys, ESPN cookies, lease tokens, or private API keys.

Plain HTTP localhost may not retain the Secure cookie. Test real authentication on HTTPS rather than weakening production security.

## Preferred bootstrap shape

    {
      "workspace": { "id": "workspace_id", "name": "Sunday Strategists" },
      "league": {
        "id": "league_id",
        "name": "Fourth & Forever",
        "season": "2026",
        "current_week": "4",
        "team_count": 12,
        "last_synced_at": "2026-08-28T13:42:00.000Z",
        "roster": []
      },
      "espn_connected": true,
      "recommendations": [],
      "reports": [],
      "jobs": [],
      "data_quality_warnings": []
    }

Preferred analysis response:

    {
      "job": {
        "id": "job_id",
        "status": "queued",
        "kind": "full",
        "message": "Analysis queued."
      }
    }

Recognized job states: queued, pending, running, succeeded, failed.

## Run locally

    npm ci
    npm run dev

Build:

    npm run build

Lint:

    npm run lint

Tests:

    npm test

## Apply the complete project

Best method:

1. Extract LEAGUEPILOT-AI-COMPLETE-SOURCE.zip.
2. Open the LEAGUEPILOT-AI folder.
3. Install Node.js 22.13.0 or newer.
4. Run npm ci.
5. Run npm run dev.
6. Keep the App Router structure unchanged.
7. Deploy from the project root.

If merging into another compatible Next/Vinext project, copy these together:

Homepage:

    app/page.tsx
    app/globals.css
    public/favicon.svg

Dashboard/auth:

    app/platform.css
    components/leaguepilot-auth.tsx
    components/leaguepilot-dashboard.tsx
    app/app/page.tsx
    app/dashboard-preview/page.tsx
    app/sign-in/page.tsx
    app/create-account/page.tsx
    app/forgot-password/page.tsx
    app/api/auth/**
    app/api/leaguepilot/**
    lib/leaguepilot-server.ts

Shared foundation:

    app/layout.tsx
    components/ui/**
    hooks/use-mobile.ts
    lib/utils.ts
    package.json

Then merge dependencies, preserve the @/* TypeScript alias, keep both stylesheet imports in app/layout.tsx, and run build/lint.

Do not put these web files inside a React Native mobile/ directory.

## Continue in ChatGPT Sites

Use:

    Use @Sites to edit the existing Site with the slug leaguepilot-ai.
    Preserve /, /app, and /dashboard-preview.
    Do not create a second Site.
    Do not place web code inside mobile/.

.openai/hosting.json connects this source to the existing Sites project. Preserve it when updating this same Site. A separate copy must be initialized as its own Site instead of inventing or reusing a project ID.

## Mobile rules

Homepage breakpoints: 760px and 390px.

Dashboard breakpoints: 1100px, 860px, 767px, and 480px.

At 767px and below, the dashboard uses a mobile drawer, fixed bottom navigation, compact top bar, stacked cards, full-width actions, large touch targets, and env(safe-area-inset-bottom) for iPhone home indicators.

Keep the viewport export in app/layout.tsx with device width, initial scale 1, viewport-fit cover, and theme color #102e27.

## Real versus simulated

| Feature | Status |
|---|---|
| Public homepage | Real and deployed |
| Homepage dashboard/evidence | Interactive fictional demo |
| Homepage Approve/Dismiss | Demo only |
| Founder Beta validation/success UI | Working frontend |
| Founder Beta database submission | Not connected |
| Auth server routes | Implemented against PocketBase |
| Protected /app | Implemented |
| Session refresh | Implemented |
| Bootstrap proxy | Implemented |
| Real analysis request | Implemented |
| Live job polling | Implemented |
| /dashboard-preview | Fictional and labeled |
| Settings switches | Disabled; write endpoint not supplied |
| ESPN status | Reads backend state |
| ESPN connection setup UI | Not implemented; contract not supplied |
| Full report-detail route | Not implemented; contract not supplied |

## Next integration work

1. Replace the Founder Beta preview delay inside BetaForm.submit() in app/page.tsx with a same-origin POST endpoint.
2. Add the ESPN connection flow only after its secure backend contract is defined.
3. Add settings persistence before enabling the switches.
4. Add a report-detail route after the backend supplies full report records or an endpoint.
5. Configure PocketBase SMTP and test password recovery.
6. Review PocketBase collection rules and add rate limiting before broad public onboarding.

## Verification

Proven:

- Production build passes.
- ESLint passes.
- Homepage remains at /.
- Authentication screens render.
- Dashboard preview renders.
- Navigation works.
- Recommendation evidence works.
- Preview analysis progresses through job states.
- Responsive CSS includes small-iPhone breakpoints and safe areas.
- The version is deployed to the existing production Site.

Not run:

- Real production account creation.
- Real PocketBase credential submission.
- Customer bootstrap data.
- Customer workspace analysis.
- Real reset-email delivery.

These require an authorized test account. Do not claim they are proven until tested.

## Exact instruction for the next AI/developer

Continue from the existing LEAGUEPILOT AI source. Do not start over. Preserve the public homepage at /, authenticated dashboard at /app, and fictional preview at /dashboard-preview. Preserve the warm-paper, forest-green, lime-accent visual system. PocketBase at https://leaguepilot-ai.cloudpod.pro remains the single source of truth. Keep auth tokens in secure HttpOnly cookies. Never expose privileged credentials, encryption keys, ESPN cookies, worker tokens, or private API keys. Inspect the current files before editing. Keep homepage CSS in app/globals.css and dashboard/auth CSS isolated in app/platform.css. Every new dashboard feature needs loading, empty, error, success, mobile, and honest-data states. Never claim a backend flow works unless it was tested with an authorized account.

End of handoff.
