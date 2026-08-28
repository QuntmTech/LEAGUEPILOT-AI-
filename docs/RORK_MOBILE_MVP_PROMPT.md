# Rork prompt — ultra-minimum mobile starter

Build only the smallest functional mobile starter for **LEAGUEPILOT AI**. I have approximately 50
Rork credits, so do not add anything beyond this exact scope.

## Stack and repository

- Expo React Native with TypeScript and Expo Router.
- Put the mobile project in `mobile/` inside `QuntmTech/LEAGUEPILOT-AI-`.
- Do not change or delete the existing Python, CloudPod, PocketBase or documentation files.
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
- ESPN connection status.
- One **Connect ESPN** button when disconnected.
- One **Run Analysis** button when connected.
- Latest job status.
- A plain list of the newest recommendations.

Run analysis with:

`POST /api/leaguepilot/workspaces/{workspaceId}/analysis`

Body:

```json
{ "kind": "full", "notify": false }
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

Use a simple dark sports theme:

- Near-black or navy background
- White text
- Electric-blue buttons
- Basic readable cards
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

- The app opens on iOS and Android.
- A user can create an account or sign in.
- The app bootstraps the workspace.
- The user can connect ESPN.
- The user can queue full analysis.
- The Home screen can display job status and recommendations after refresh.
- No secrets are committed or logged.
- Add a short `mobile/README.md` with setup and run instructions.

Stop immediately after these three screens work. Do not spend credits generating anything else.

