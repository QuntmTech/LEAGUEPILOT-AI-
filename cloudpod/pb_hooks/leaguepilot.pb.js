/// <reference path="../pb_data/types.d.ts" />

// LEAGUEPILOT AI CloudPod control plane.
// Secrets are supplied only through the PocketBase process environment.

routerAdd("GET", "/api/leaguepilot/health", (e) => {
  const { LP_VERSION, nowIso, setPrivateResponse } = require(`${__hooks}/leaguepilot_lib.js`);
  setPrivateResponse(e);
  return e.json(200, {
    status: "ok",
    service: "leaguepilot-cloudpod",
    version: LP_VERSION,
    queue: "available",
    timestamp: nowIso(),
  });
});

routerAdd(
  "POST",
  "/api/leaguepilot/bootstrap",
  (e) => {
    const { audit, authId, bodyOf, cleanText, findOptional, setPrivateResponse } = require(
      `${__hooks}/leaguepilot_lib.js`,
    );
    setPrivateResponse(e);
    const userId = authId(e);
    const body = bodyOf(e);
    let profile = findOptional("profiles", "user = {:user}", { user: userId });
    let workspace = findOptional("workspaces", "owner = {:owner} && status = 'active'", {
      owner: userId,
    });

    if (!profile) {
      profile = new Record($app.findCollectionByNameOrId("profiles"));
      profile.set("user", userId);
      profile.set(
        "display_name",
        cleanText(body.display_name, 120) || cleanText(e.auth.getString("name"), 120) || "Manager",
      );
      profile.set("plan", "free");
      profile.set("onboarding_complete", false);
      profile.set("timezone", cleanText(body.timezone, 64) || "America/New_York");
      profile.set("status", "active");
      $app.save(profile);
    }

    if (!workspace) {
      workspace = new Record($app.findCollectionByNameOrId("workspaces"));
      workspace.set("owner", userId);
      workspace.set("name", cleanText(body.workspace_name, 120) || "My Fantasy Command Center");
      workspace.set("slug", "lp-" + userId);
      workspace.set("plan", profile.getString("plan") || "free");
      workspace.set("status", "active");
      workspace.set("timezone", profile.getString("timezone") || "America/New_York");
      $app.save(workspace);

      const membership = new Record($app.findCollectionByNameOrId("workspace_memberships"));
      membership.set("workspace", workspace.id);
      membership.set("user", userId);
      membership.set("role", "owner");
      membership.set("status", "active");
      $app.save(membership);
      audit($app, userId, workspace.id, userId, "workspace.created", "workspace", workspace.id, {});
    }

    return e.json(200, {
      profile: {
        id: profile.id,
        display_name: profile.getString("display_name"),
        plan: profile.getString("plan"),
        onboarding_complete: profile.getBool("onboarding_complete"),
        timezone: profile.getString("timezone"),
      },
      workspace: {
        id: workspace.id,
        name: workspace.getString("name"),
        slug: workspace.getString("slug"),
        plan: workspace.getString("plan"),
        status: workspace.getString("status"),
      },
    });
  },
  $apis.requireAuth("users"),
  $apis.bodyLimit(16 * 1024),
);

routerAdd(
  "PUT",
  "/api/leaguepilot/workspaces/{workspaceId}/connections/espn",
  (e) => {
    const {
      audit,
      authId,
      bodyOf,
      cleanText,
      connectionView,
      encryptionKey,
      enqueueJob,
      findOptional,
      integer,
      ownedWorkspace,
      setPrivateResponse,
    } = require(`${__hooks}/leaguepilot_lib.js`);
    setPrivateResponse(e);
    const userId = authId(e);
    const workspace = ownedWorkspace(e, e.request.pathValue("workspaceId"));
    const body = bodyOf(e);
    const leagueId = integer(body.league_id, "League ID", 1, 999999999999);
    const teamId = integer(body.team_id, "Team ID", 1, 999999999);
    const season = integer(body.season, "Season", 2019, 2100);
    const isPublic = body.is_public === true;
    const espnS2 = cleanText(body.espn_s2, 4096);
    const swid = cleanText(body.swid, 200);
    if (!!espnS2 !== !!swid) throw new BadRequestError("Provide both ESPN cookies together");

    let connection = findOptional(
      "espn_connections",
      "workspace = {:workspace} && league_id = {:league} && season = {:season}",
      { workspace: workspace.id, league: leagueId, season: season },
    );
    const isNew = !connection;
    if (!connection) connection = new Record($app.findCollectionByNameOrId("espn_connections"));
    if (!isPublic && !espnS2 && !connection.getString("credentials_ciphertext")) {
      throw new BadRequestError("Private ESPN leagues require ESPN cookies");
    }

    connection.set("owner", userId);
    connection.set("workspace", workspace.id);
    connection.set("league_id", leagueId);
    connection.set("team_id", teamId);
    connection.set("season", season);
    connection.set("is_public", isPublic);
    connection.set("status", "pending");
    connection.set("last_error", "");
    if (isPublic) {
      connection.set("credentials_ciphertext", "");
    } else if (espnS2 && swid) {
      connection.set(
        "credentials_ciphertext",
        $security.encrypt(JSON.stringify({ espn_s2: espnS2, swid: swid }), encryptionKey()),
      );
    }
    $app.save(connection);

    const bucket = new Date().toISOString().slice(0, 13);
    const job = enqueueJob($app, {
      owner: userId,
      workspace: workspace.id,
      connection: connection.id,
      kind: "sync",
      priority: 80,
      idempotencyKey: "sync:" + connection.id + ":" + bucket,
      payload: { reason: isNew ? "connection-created" : "connection-updated" },
    });
    audit(
      $app,
      userId,
      workspace.id,
      userId,
      "connection.espn.saved",
      "espn_connection",
      connection.id,
      { league_id: leagueId, season: season, is_public: isPublic },
    );
    return e.json(isNew ? 201 : 200, { connection: connectionView(connection), job_id: job.id });
  },
  $apis.requireAuth("users"),
  $apis.bodyLimit(16 * 1024),
);

routerAdd(
  "POST",
  "/api/leaguepilot/connections/{connectionId}/sync",
  (e) => {
    const { enqueueJob, ownedRecord, setPrivateResponse } = require(
      `${__hooks}/leaguepilot_lib.js`,
    );
    setPrivateResponse(e);
    const connection = ownedRecord(e, "espn_connections", e.request.pathValue("connectionId"));
    const key = "sync:" + connection.id + ":" + new Date().toISOString().slice(0, 16);
    const job = enqueueJob($app, {
      owner: connection.getString("owner"),
      workspace: connection.getString("workspace"),
      connection: connection.id,
      kind: "sync",
      priority: 90,
      idempotencyKey: key,
      payload: { reason: "user-requested" },
    });
    return e.json(202, { queued: true, job_id: job.id, status: job.getString("status") });
  },
  $apis.requireAuth("users"),
);

routerAdd(
  "POST",
  "/api/leaguepilot/workspaces/{workspaceId}/analysis",
  (e) => {
    const {
      authId,
      bodyOf,
      cleanText,
      enqueueJob,
      ownedRecord,
      ownedWorkspace,
      setPrivateResponse,
    } = require(`${__hooks}/leaguepilot_lib.js`);
    setPrivateResponse(e);
    const userId = authId(e);
    const workspace = ownedWorkspace(e, e.request.pathValue("workspaceId"));
    const body = bodyOf(e);
    const allowed = [
      "lineup",
      "waivers",
      "trades",
      "weekly-report",
      "inactive-sweep",
      "full",
    ];
    const kind = cleanText(body.kind, 30);
    if (allowed.indexOf(kind) === -1) throw new BadRequestError("Analysis kind is invalid");
    const requestedConnectionId = cleanText(body.connection_id, 15);
    let connection = null;
    if (requestedConnectionId) {
      connection = ownedRecord(e, "espn_connections", requestedConnectionId);
      if (connection.getString("workspace") !== workspace.id) {
        throw new NotFoundError("ESPN connection not found");
      }
      if (connection.getString("status") === "disabled") {
        throw new BadRequestError("The selected ESPN connection is disabled");
      }
    } else {
      const connections = $app.findRecordsByFilter(
        "espn_connections",
        "workspace = {:workspace} && status != 'disabled'",
        "-last_synced_at",
        2,
        0,
        { workspace: workspace.id },
      );
      if (!connections.length) throw new BadRequestError("Connect ESPN before running analysis");
      if (connections.length > 1) {
        throw new BadRequestError("connection_id is required when a workspace has multiple leagues");
      }
      connection = connections[0];
    }
    const key =
      "analysis:" +
      connection.id +
      ":" +
      kind +
      ":" +
      new Date().toISOString().slice(0, 16);
    const job = enqueueJob($app, {
      owner: userId,
      workspace: workspace.id,
      connection: connection.id,
      kind: kind,
      priority: 70,
      idempotencyKey: key,
      payload: { notify: body.notify === true, connection_id: connection.id },
    });
    return e.json(202, {
      queued: true,
      job_id: job.id,
      connection_id: connection.id,
      status: job.getString("status"),
    });
  },
  $apis.requireAuth("users"),
  $apis.bodyLimit(8 * 1024),
);

routerAdd(
  "POST",
  "/api/leaguepilot/recommendations/{id}/review",
  (e) => {
    const { audit, bodyOf, cleanText, ownedRecord, setPrivateResponse } = require(
      `${__hooks}/leaguepilot_lib.js`,
    );
    setPrivateResponse(e);
    const recommendation = ownedRecord(e, "recommendations", e.request.pathValue("id"));
    const body = bodyOf(e);
    const decision = cleanText(body.decision, 20);
    if (["approved", "dismissed"].indexOf(decision) === -1) {
      throw new BadRequestError("Decision must be approved or dismissed");
    }
    if (recommendation.getString("status") !== "proposed") {
      throw new BadRequestError("Recommendation is no longer reviewable");
    }
    recommendation.set("status", decision);
    recommendation.set("reviewed_at", nowIso());
    $app.save(recommendation);
    audit(
      $app,
      recommendation.getString("owner"),
      recommendation.getString("workspace"),
      e.auth.id,
      "recommendation." + decision,
      "recommendation",
      recommendation.id,
      { kind: recommendation.getString("kind") },
    );
    return e.json(200, { id: recommendation.id, status: decision, espn_action_executed: false });
  },
  $apis.requireAuth("users"),
  $apis.bodyLimit(4 * 1024),
);

routerAdd(
  "POST",
  "/api/leaguepilot/workspaces/{workspaceId}/notifications",
  (e) => {
    const {
      audit,
      authId,
      bodyOf,
      cleanText,
      encryptionKey,
      ownedWorkspace,
      requiredText,
      setPrivateResponse,
    } = require(`${__hooks}/leaguepilot_lib.js`);
    setPrivateResponse(e);
    const userId = authId(e);
    const workspace = ownedWorkspace(e, e.request.pathValue("workspaceId"));
    const body = bodyOf(e);
    const kind = cleanText(body.kind, 20);
    const label = requiredText(body.label, "Channel label", 80);
    const target = requiredText(body.target, "Notification target", 2048);
    if (["discord", "groupme"].indexOf(kind) === -1) {
      throw new BadRequestError("Notification kind is invalid");
    }
    if (kind === "discord") {
      const discordPattern =
        /^https:\/\/(www\.)?(discord\.com|discordapp\.com)\/api\/webhooks\/[A-Za-z0-9._-]+\/[A-Za-z0-9._-]+$/;
      if (!discordPattern.test(target)) {
        throw new BadRequestError("Discord target must be an official HTTPS webhook URL");
      }
    } else if (!/^[A-Za-z0-9_-]{10,100}$/.test(target)) {
      throw new BadRequestError("GroupMe target must be a valid bot ID");
    }

    const channel = new Record($app.findCollectionByNameOrId("notification_channels"));
    channel.set("owner", userId);
    channel.set("workspace", workspace.id);
    channel.set("kind", kind);
    channel.set("label", label);
    channel.set("target_ciphertext", $security.encrypt(target, encryptionKey()));
    channel.set("is_active", true);
    channel.set("failure_count", 0);
    $app.save(channel);
    audit(
      $app,
      userId,
      workspace.id,
      userId,
      "notification.created",
      "notification_channel",
      channel.id,
      { kind: kind },
    );
    return e.json(201, {
      channel: {
        id: channel.id,
        kind: kind,
        label: label,
        is_active: true,
      },
    });
  },
  $apis.requireAuth("users"),
  $apis.bodyLimit(8 * 1024),
);

routerAdd(
  "POST",
  "/api/leaguepilot/notifications/{id}/disable",
  (e) => {
    const { audit, encryptionKey, ownedRecord, setPrivateResponse } = require(
      `${__hooks}/leaguepilot_lib.js`,
    );
    setPrivateResponse(e);
    const channel = ownedRecord(e, "notification_channels", e.request.pathValue("id"));
    channel.set("is_active", false);
    channel.set(
      "target_ciphertext",
      $security.encrypt($security.randomString(48), encryptionKey()),
    );
    $app.save(channel);
    audit(
      $app,
      channel.getString("owner"),
      channel.getString("workspace"),
      e.auth.id,
      "notification.disabled",
      "notification_channel",
      channel.id,
      { kind: channel.getString("kind") },
    );
    return e.json(200, { id: channel.id, is_active: false });
  },
  $apis.requireAuth("users"),
);

routerAdd("POST", "/api/leaguepilot/internal/workers/heartbeat", (e) => {
  const {
    bodyOf,
    cleanText,
    findOptional,
    nowIso,
    requiredText,
    requireWorker,
    setPrivateResponse,
  } = require(`${__hooks}/leaguepilot_lib.js`);
  setPrivateResponse(e);
  requireWorker(e);
  const body = bodyOf(e);
  const workerId = requiredText(body.worker_id, "Worker ID", 120);
  let worker = findOptional("worker_nodes", "worker_id = {:id}", { id: workerId });
  if (!worker) worker = new Record($app.findCollectionByNameOrId("worker_nodes"));
  worker.set("worker_id", workerId);
  worker.set("status", cleanText(body.status, 20) || "online");
  worker.set("version", cleanText(body.version, 40) || "unknown");
  worker.set("active_jobs", Math.max(0, Number(body.active_jobs) || 0));
  worker.set("last_seen_at", nowIso());
  worker.set("metadata", body.metadata || {});
  $app.save(worker);
  return e.json(200, { ok: true, worker_id: workerId });
}, $apis.bodyLimit(16 * 1024));

routerAdd("POST", "/api/leaguepilot/internal/jobs/claim", (e) => {
  const {
    bodyOf,
    encryptionKey,
    findOptional,
    nowIso,
    requiredText,
    requireWorker,
    setPrivateResponse,
  } = require(`${__hooks}/leaguepilot_lib.js`);
  setPrivateResponse(e);
  requireWorker(e);
  const body = bodyOf(e);
  const workerId = requiredText(body.worker_id, "Worker ID", 120);
  const leaseToken = $security.randomString(48);
  let claimed = null;
  $app.runInTransaction((txApp) => {
    const jobs = txApp.findRecordsByFilter(
      "job_runs",
      "status = 'queued' && scheduled_for <= {:now}",
      "-priority,scheduled_for",
      1,
      0,
      { now: nowIso() },
    );
    if (!jobs.length) return;
    const job = jobs[0];
    const attempts = job.getInt("attempts") + 1;
    const leaseUntil = new Date(Date.now() + 5 * 60 * 1000).toISOString();
    job.set("status", "running");
    job.set("attempts", attempts);
    job.set("worker_id", workerId);
    job.set("started_at", nowIso());
    job.set("lease_expires_at", leaseUntil);
    job.set("lease_token_hash", $security.sha256(leaseToken));
    txApp.save(job);

    let connection = null;
    const connectionId = job.getString("connection");
    if (connectionId) connection = txApp.findRecordById("espn_connections", connectionId);
    let credentials = null;
    if (connection && connection.getString("credentials_ciphertext")) {
      credentials = JSON.parse(
        String($security.decrypt(connection.getString("credentials_ciphertext"), encryptionKey())),
      );
    }
    let notification = null;
    let notificationUnavailable = false;
    const jobPayload = job.get("payload") || {};
    if (job.getString("kind") === "notification") {
      const channelId = requiredText(jobPayload.channel_id, "Channel ID", 15);
      const channel = findOptional("notification_channels", "id = {:id}", { id: channelId }, txApp);
      if (
        !channel ||
        channel.getString("owner") !== job.getString("owner") ||
        channel.getString("workspace") !== job.getString("workspace") ||
        !channel.getBool("is_active")
      ) {
        notificationUnavailable = true;
        job.set("status", "cancelled");
        job.set("last_error", "Notification channel is unavailable");
        job.set("completed_at", nowIso());
        job.set("lease_expires_at", "");
        job.set("lease_token_hash", "");
        job.set("worker_id", "");
        txApp.save(job);
      } else {
        notification = {
          channel_id: channel.id,
          kind: channel.getString("kind"),
          target: String(
            $security.decrypt(channel.getString("target_ciphertext"), encryptionKey()),
          ),
          message: requiredText(jobPayload.message, "Notification message", 8000),
        };
      }
    }
    if (notificationUnavailable) return;
    claimed = {
      id: job.id,
      kind: job.getString("kind"),
      owner: job.getString("owner"),
      workspace: job.getString("workspace"),
      connection: connection
        ? {
            id: connection.id,
            league_id: connection.getInt("league_id"),
            team_id: connection.getInt("team_id"),
            season: connection.getInt("season"),
            is_public: connection.getBool("is_public"),
            credentials: credentials,
          }
        : null,
      payload: job.get("payload") || {},
      notification: notification,
      attempt: attempts,
      max_attempts: job.getInt("max_attempts"),
      lease_token: leaseToken,
      lease_expires_at: leaseUntil,
    };
  });
  return e.json(200, { job: claimed });
}, $apis.bodyLimit(8 * 1024));

routerAdd("POST", "/api/leaguepilot/internal/jobs/{id}/complete", (e) => {
  const {
    audit,
    bodyOf,
    cleanText,
    enqueueJob,
    integer,
    nowIso,
    requireWorker,
    requiredText,
    setPrivateResponse,
    usage,
    validateLease,
  } = require(`${__hooks}/leaguepilot_lib.js`);
  setPrivateResponse(e);
  requireWorker(e);
  const body = bodyOf(e);
  const job = $app.findRecordById("job_runs", e.request.pathValue("id"));
  validateLease(job, cleanText(body.lease_token, 100));
  const owner = job.getString("owner");
  const workspace = job.getString("workspace");
  let snapshotId = "";

  $app.runInTransaction((txApp) => {
    if (body.snapshot && typeof body.snapshot === "object") {
      const snapshot = new Record(txApp.findCollectionByNameOrId("league_snapshots"));
      snapshot.set("owner", owner);
      snapshot.set("workspace", workspace);
      if (job.getString("connection")) snapshot.set("connection", job.getString("connection"));
      snapshot.set("week", integer(body.snapshot.week, "Snapshot week", 0, 30));
      snapshot.set("payload", body.snapshot.payload || {});
      snapshot.set("content_hash", requiredText(body.snapshot.content_hash, "Content hash", 64));
      snapshot.set("schema_version", integer(body.snapshot.schema_version || 1, "Schema version", 1, 100));
      snapshot.set("fetched_at", body.snapshot.fetched_at || nowIso());
      if (body.snapshot.expires_at) snapshot.set("expires_at", body.snapshot.expires_at);
      txApp.save(snapshot);
      snapshotId = snapshot.id;
    }

    const recommendations = Array.isArray(body.recommendations)
      ? body.recommendations.slice(0, 100)
      : [];
    const incomingKinds = {};
    recommendations.forEach((item) => {
      incomingKinds[cleanText(item.kind, 30)] = true;
    });
    // A clean sweep must retire an earlier OUT alert for the same league.
    if (job.getString("kind") === "inactive-sweep") incomingKinds["availability-alert"] = true;
    if (Object.keys(incomingKinds).length) {
      const existing = txApp.findRecordsByFilter(
        "recommendations",
        "workspace = {:workspace} && status = 'proposed'",
        "",
        500,
        0,
        { workspace: workspace },
      );
      existing.forEach((record) => {
        if (!incomingKinds[record.getString("kind")]) return;
        const oldSnapshotId = record.getString("snapshot");
        if (job.getString("connection") && oldSnapshotId) {
          const oldSnapshot = txApp.findRecordById("league_snapshots", oldSnapshotId);
          if (oldSnapshot.getString("connection") !== job.getString("connection")) return;
        }
        record.set("status", "superseded");
        record.set("reviewed_at", nowIso());
        txApp.save(record);
      });
    }
    if (recommendations.length) {
      recommendations.forEach((item) => {
        const record = new Record(txApp.findCollectionByNameOrId("recommendations"));
        record.set("owner", owner);
        record.set("workspace", workspace);
        if (snapshotId) record.set("snapshot", snapshotId);
        record.set("kind", requiredText(item.kind, "Recommendation kind", 30));
        record.set("title", requiredText(item.title, "Recommendation title", 180));
        record.set("summary", requiredText(item.summary, "Recommendation summary", 8000));
        record.set("confidence", integer(item.confidence, "Confidence", 0, 100));
        record.set("impact_points", Number(item.impact_points) || 0);
        record.set("payload", item.payload || {});
        record.set("status", "proposed");
        if (item.expires_at) record.set("expires_at", item.expires_at);
        txApp.save(record);
      });
    }

    if (body.report && typeof body.report === "object") {
      const report = new Record(txApp.findCollectionByNameOrId("reports"));
      report.set("owner", owner);
      report.set("workspace", workspace);
      if (snapshotId) report.set("snapshot", snapshotId);
      report.set("week", integer(body.report.week, "Report week", 0, 30));
      report.set("title", requiredText(body.report.title, "Report title", 180));
      report.set("body_markdown", requiredText(body.report.body_markdown, "Report body", 100000));
      report.set("metrics", body.report.metrics || {});
      report.set("narration_mode", cleanText(body.report.narration_mode, 30) || "rules");
      report.set("published_at", nowIso());
      txApp.save(report);
    }

    const jobPayload = job.get("payload") || {};
    const notificationMessage = cleanText(body.notification_message, 8000);
    if (
      job.getString("kind") !== "notification" &&
      jobPayload.notify === true &&
      notificationMessage
    ) {
      const channels = txApp.findRecordsByFilter(
        "notification_channels",
        "workspace = {:workspace} && is_active = true",
        "created",
        25,
        0,
        { workspace: workspace },
      );
      channels.forEach((channel) => {
        enqueueJob(txApp, {
          owner: owner,
          workspace: workspace,
          kind: "notification",
          priority: job.getString("kind") === "inactive-sweep" ? 100 : 60,
          idempotencyKey: "notification:" + job.id + ":" + channel.id,
          payload: { channel_id: channel.id, message: notificationMessage },
        });
      });
    }

    const connectionId = job.getString("connection");
    if (connectionId && body.connection_status !== "unchanged") {
      const connection = txApp.findRecordById("espn_connections", connectionId);
      connection.set("status", "connected");
      connection.set("last_error", "");
      connection.set("last_synced_at", nowIso());
      connection.set("sync_failures", 0);
      if (body.league_name) connection.set("league_name", cleanText(body.league_name, 160));
      txApp.save(connection);
    }

    job.set("status", "succeeded");
    job.set("completed_at", nowIso());
    job.set("lease_expires_at", "");
    job.set("lease_token_hash", "");
    job.set("result", body.result || {});
    txApp.save(job);
    if (job.getString("kind") === "notification") {
      const result = body.result || {};
      const channelId = cleanText(result.channel_id, 15);
      if (channelId) {
        const channel = txApp.findRecordById("notification_channels", channelId);
        if (
          channel.getString("owner") === owner &&
          channel.getString("workspace") === workspace
        ) {
          channel.set("last_delivered_at", nowIso());
          channel.set("failure_count", 0);
          txApp.save(channel);
        }
      }
    }
    audit(txApp, owner, workspace, "", "job.succeeded", "job_run", job.id, {
      kind: job.getString("kind"),
      attempt: job.getInt("attempts"),
    });
  });
  usage($app, owner, workspace, "analysis", 1, "job:" + job.id, { kind: job.getString("kind") });
  return e.json(200, { completed: true, job_id: job.id, snapshot_id: snapshotId || null });
}, $apis.bodyLimit(6 * 1024 * 1024));

routerAdd("POST", "/api/leaguepilot/internal/jobs/{id}/fail", (e) => {
  const {
    audit,
    bodyOf,
    cleanText,
    nowIso,
    requireWorker,
    setPrivateResponse,
    validateLease,
  } = require(`${__hooks}/leaguepilot_lib.js`);
  setPrivateResponse(e);
  requireWorker(e);
  const body = bodyOf(e);
  const job = $app.findRecordById("job_runs", e.request.pathValue("id"));
  validateLease(job, cleanText(body.lease_token, 100));
  const attempts = job.getInt("attempts");
  const retryable = body.retryable !== false && attempts < job.getInt("max_attempts");
  const delaySeconds = Math.min(900, Math.max(30, Math.pow(2, attempts) * 15));
  job.set("status", retryable ? "queued" : "dead-letter");
  job.set("last_error", cleanText(body.error, 1000) || "Worker reported a failure");
  job.set("lease_expires_at", "");
  job.set("lease_token_hash", "");
  job.set("worker_id", "");
  if (retryable) job.set("scheduled_for", new Date(Date.now() + delaySeconds * 1000).toISOString());
  else job.set("completed_at", nowIso());
  $app.save(job);
  const connectionId = job.getString("connection");
  if (connectionId) {
    const connection = $app.findRecordById("espn_connections", connectionId);
    connection.set("status", retryable ? "error" : "expired");
    connection.set("last_error", cleanText(body.error, 500));
    connection.set("sync_failures", connection.getInt("sync_failures") + 1);
    $app.save(connection);
  }
  if (job.getString("kind") === "notification") {
    const payload = job.get("payload") || {};
    const channelId = cleanText(payload.channel_id, 15);
    if (channelId) {
      const channel = $app.findRecordById("notification_channels", channelId);
      if (
        channel.getString("owner") === job.getString("owner") &&
        channel.getString("workspace") === job.getString("workspace")
      ) {
        const failures = channel.getInt("failure_count") + 1;
        channel.set("failure_count", failures);
        if (!retryable || failures >= 5) channel.set("is_active", false);
        $app.save(channel);
      }
    }
  }
  audit(
    $app,
    job.getString("owner"),
    job.getString("workspace"),
    "",
    retryable ? "job.retry_scheduled" : "job.dead_lettered",
    "job_run",
    job.id,
    { kind: job.getString("kind"), attempt: attempts },
  );
  return e.json(200, { failed: true, retry_scheduled: retryable, status: job.getString("status") });
}, $apis.bodyLimit(16 * 1024));

cronAdd("leaguepilot-requeue-expired-leases", "*/2 * * * *", () => {
  const { nowIso } = require(`${__hooks}/leaguepilot_lib.js`);
  const expired = $app.findRecordsByFilter(
    "job_runs",
    "status = 'running' && lease_expires_at != '' && lease_expires_at < {:now}",
    "lease_expires_at",
    100,
    0,
    { now: nowIso() },
  );
  expired.forEach((job) => {
    const retryable = job.getInt("attempts") < job.getInt("max_attempts");
    job.set("status", retryable ? "queued" : "dead-letter");
    job.set("last_error", "Worker lease expired");
    job.set("lease_expires_at", "");
    job.set("lease_token_hash", "");
    job.set("worker_id", "");
    if (retryable) job.set("scheduled_for", nowIso());
    else job.set("completed_at", nowIso());
    $app.save(job);
  });
});

// UTC lock windows cover both daylight- and standard-time NFL schedules.
cronAdd("leaguepilot-thursday-lock-sweeps", "45 22-23 * * 4", () => {
  const { enqueueInactiveSweeps } = require(`${__hooks}/leaguepilot_lib.js`);
  enqueueInactiveSweeps($app, new Date().toISOString().slice(0, 16));
});
cronAdd("leaguepilot-sunday-lock-sweeps", "30 15-23 * * 0", () => {
  const { enqueueInactiveSweeps } = require(`${__hooks}/leaguepilot_lib.js`);
  enqueueInactiveSweeps($app, new Date().toISOString().slice(0, 16));
});
cronAdd("leaguepilot-monday-lock-sweeps", "45 23 * * 1", () => {
  const { enqueueInactiveSweeps } = require(`${__hooks}/leaguepilot_lib.js`);
  enqueueInactiveSweeps($app, new Date().toISOString().slice(0, 16));
});
cronAdd("leaguepilot-monday-late-lock-sweeps", "45 0 * * 2", () => {
  const { enqueueInactiveSweeps } = require(`${__hooks}/leaguepilot_lib.js`);
  enqueueInactiveSweeps($app, new Date().toISOString().slice(0, 16));
});
