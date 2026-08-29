# Rork prompt — ultra-minimum mobile starter

Build only the smallest functional mobile starter for **LEAGUEPILOT AI**. I have approximately 50
Rork credits, so do not add anything beyond this exact scope.

## Existing project and repository

- Continue the existing native SwiftUI/Xcode project in
  `QuntmTech/rork-build-only-the-smallest-functi`.
- Do not start over, migrate frameworks, create another repository or regenerate working screens.
- Spend credits only connecting the existing three-screen shell to the backend.
- Use PocketBase at `https://leaguepilot-ai.cloudpod.pro`.
- Read that URL from `EXPO_PUBLIC_CLOUDPOD_URL`.
- Never place worker keys, superuser tokens, ESPN cookies or other secrets in source code.

## Build exactly three screens

### 1. Sign in

- Email and password fields.
- Sign In button using PocketBase `users` authentication.
- Small Create Account option using email and password.
- After successful authentication, call `POST /api/leaguepilot/bootstrap`.
- Keep the user signed in and provide a basic Sign Out button.

### 2. Home

Show:

- LEAGUEPILOT AI name.
- Workspace name.
- A tiny league picker only when the account has more than one ESPN connection.
- Selected ESPN connection status.
- One **Connect ESPN** button when disconnected.
- One **Run Analysis** button when connected.
- Latest job status.
- A plain list of the newest recommendations.

Run analysis with:

`POST /api/leaguepilot/workspaces/{workspaceId}/analysis`

Body:

```json
{ "kind": "full", "notify": false, "connection_id": "SELECTED_CONNECTION_ID" }
```

Use pull-to-refresh. Do not build charts, animations or complex cards.

### 3. Connect ESPN

Fields:

- League ID
- Team ID
- Season
- Public/private toggle
- Private leagues only: password-style `espn_s2` and `SWID`

Submit to:

`PUT /api/leaguepilot/workspaces/{workspaceId}/connections/espn`

Clear the cookie inputs immediately after submission. Never display or save those values afterward.

## Design

Match the existing LEAGUEPILOT AI homepage:

- Warm light-tan background `#F3EFE5`
- Off-white cards `#FFFDF8`
- Primary forest-green `#1D5949`
- Secondary green `#2F7A63`, lime accent `#B8DC73`, dark ink `#17221F`
- Basic readable cards with subtle `#D7D1C6` borders
- Large tap targets

Do not create custom graphics, videos, elaborate animation, multiple themes or extra design options.

## Do not build yet

Do not build reports, recommendation detail pages, approve/dismiss actions, settings, payments,
notifications, chat, AI chat, commissioner features, advanced realtime subscriptions, offline mode,
multiple sports, admin tools, marketing pages or automated ESPN actions.

The web and mobile apps will eventually share PocketBase in real time, but for this first build simply
read and write the same PocketBase records and use pull-to-refresh. Leave the service layer clean so
realtime subscriptions can be added later.

## Done means

- The existing iOS project builds and opens without a framework rewrite.
- A user can create an account or sign in.
- The app bootstraps the workspace.
- The user can connect ESPN.
- The user can queue full analysis.
- The Home screen can display job status and recommendations after refresh.
- No secrets are committed or logged.
- Add a short `mobile/README.md` with setup and run instructions.

Stop immediately after these three screens work. Do not spend credits generating anything else.
