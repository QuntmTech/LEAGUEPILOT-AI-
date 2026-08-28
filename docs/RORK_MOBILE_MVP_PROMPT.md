# Rork prompt — credit-efficient mobile MVP

Build the bare-minimum mobile MVP for **LEAGUEPILOT AI**, an ESPN-first fantasy-football
intelligence app. Keep this intentionally small because the build has a limited Rork credit budget.
Produce a clean foundation that can be expanded after the GitHub repository is connected.

## Technical direction

- Build an Expo React Native app in TypeScript for iOS and Android.
- Use Expo Router and simple reusable components.
- If the existing GitHub repository `QuntmTech/LEAGUEPILOT-AI-` is connected, place all mobile code
  under `mobile/`. Do not replace, rewrite or delete the existing Python backend, CloudPod hooks,
  documentation or tests.
- Use PocketBase at `https://leaguepilot-ai.cloudpod.pro` as the single backend/source of truth.
- Read the backend URL from `EXPO_PUBLIC_CLOUDPOD_URL`; do not hard-code any secret.
- Never include a PocketBase superuser token, the CloudPod worker key, ESPN cookies, webhook URLs or
  private API keys in source code, Expo public variables, logs or fixtures.
- Add a small typed backend service layer so later screens can be added without rewriting the app.

## Build only these flows

1. **Authentication**
   - One polished screen with Sign In and Create Account modes using the PocketBase `users` auth
     collection.
   - After first authentication, call `POST /api/leaguepilot/bootstrap` once. The endpoint is
     idempotent and returns the user's profile and workspace.
   - Persist the normal PocketBase user session securely using the platform-appropriate local auth
     store. Provide Sign Out.

2. **Home dashboard**
   - Show LEAGUEPILOT AI branding, the current workspace name, ESPN connection status and one primary
     action.
   - If ESPN is not connected, show **Connect ESPN**.
   - If connected, show **Run Full Analysis**, latest job status and up to three newest
     recommendations.
   - Add pull-to-refresh plus useful loading, empty and error states.

3. **Connect ESPN form**
   - Fields: league ID, team ID, season, public/private league toggle.
   - For a private league only, show `espn_s2` and `SWID` password-style inputs with a short privacy
     explanation.
   - Submit to
     `PUT /api/leaguepilot/workspaces/{workspaceId}/connections/espn`.
   - Never display the cookies again after submission and never save them in local state longer than
     necessary to submit the form.

4. **Recommendations**
   - A simple list and detail view for lineup, waiver and trade recommendations.
   - Show title, summary, confidence, estimated point impact, evidence/risk flags and status.
   - Buttons: **Approve** and **Dismiss**, calling
     `POST /api/leaguepilot/recommendations/{id}/review` with `approved` or `dismissed`.
   - Make it explicit that approval records the user's decision but does not execute an ESPN move.

5. **Reports and settings**
   - Reports: basic list of weekly reports and a readable Markdown detail screen.
   - Settings: account email, workspace name, connection status and Sign Out. No complex account
     management in this first build.

## Navigation and design

- Use four bottom tabs: **Home**, **Recommendations**, **Reports**, **Settings**.
- Style: premium modern sports command center, dark navy/near-black background, crisp white text,
  electric blue primary accent and restrained green/orange/red status colors.
- Prioritize readability, large tap targets, accessible contrast and safe-area behavior.
- Use one font family, a small spacing scale and subtle cards. Avoid expensive custom illustrations,
  video, 3D, excessive animation and unnecessary design variants.

## Real-time behavior

- Subscribe through the PocketBase SDK to the signed-in user's `espn_connections`, `job_runs`,
  `recommendations` and `reports` records.
- Refresh the relevant query when a subscription event arrives.
- The backend is authoritative. The future web dashboard and this mobile app must display the same
  state and sync both directions through PocketBase; do not build a separate mobile-only database.
- Unsubscribe on sign-out/unmount and reconnect cleanly after the app returns from the background.

## Exact actions

- Full analysis:
  `POST /api/leaguepilot/workspaces/{workspaceId}/analysis` with
  `{ "kind": "full", "notify": false }`.
- Read only records allowed by PocketBase's authenticated owner-scoped collection rules.
- Treat 401 as signed-out, 404 as unavailable/not owned and 429 as a temporary rate limit.
- Do not implement any direct ESPN write action.

## Explicitly out of scope for this credit-limited build

Do not build payments, subscriptions, commissioner tools, chat, social feeds, push notifications,
advanced charts, AI chat, manual roster execution, offline conflict resolution, multiple sports,
multi-workspace switching, an admin panel, custom theming, marketing pages or elaborate onboarding.
Do not create fake production statistics. A tiny clearly labeled local preview state is acceptable
only for design-time rendering.

## Definition of done

- App boots on iOS and Android without warnings.
- A user can register/sign in, bootstrap a workspace, connect ESPN, queue full analysis, watch the job
  status update, read recommendations/reports, approve or dismiss a recommendation and sign out.
- Real-time changes made by the future web dashboard appear in the mobile app and mobile changes are
  stored in the same PocketBase records for the web dashboard.
- No secret is committed or printed.
- Include a short `mobile/README.md` with install, environment and run instructions.
- Stop after this foundation. Favor working data flows over extra screens or visual polish.

