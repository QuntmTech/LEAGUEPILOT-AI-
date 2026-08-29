const LP_VERSION = "0.4.0";
const MAX_TEXT = 1000;

function nowIso() {
  return new Date().toISOString();
}

function cleanText(value, maxLength) {
  if (typeof value !== "string") return "";
  return value.trim().slice(0, maxLength || MAX_TEXT);
}

function requiredText(value, label, maxLength) {
  const result = cleanText(value, maxLength);
  if (!result) throw new BadRequestError(label + " is required");
  return result;
}

function integer(value, label, min, max) {
  const result = Number(value);
  if (!Number.isInteger(result) || result < min || result > max) {
    throw new BadRequestError(label + " is invalid");
  }
  return result;
}

function bodyOf(e) {
  const info = e.requestInfo();
  return info && info.body ? info.body : {};
}

function authId(e) {
  if (!e.auth || e.auth.collection().name !== "users") {
    throw new UnauthorizedError("Authentication required");
  }
  return e.auth.id;
}

function findOptional(collection, filter, params, app) {
  try {
    return (app || $app).findFirstRecordByFilter(collection, filter, params || {});
  } catch (_) {
    return null;
  }
}

function ownedWorkspace(e, workspaceId) {
  const userId = authId(e);
  let workspace;
  try {
    workspace = $app.findRecordById("workspaces", workspaceId);
  } catch (_) {
    throw new NotFoundError("Workspace not found");
  }
  if (workspace.getString("owner") !== userId || workspace.getString("status") !== "active") {
    throw new NotFoundError("Workspace not found");
  }
  return workspace;
}

function ownedRecord(e, collection, id) {
  const userId = authId(e);
  let record;
  try {
    record = $app.findRecordById(collection, id);
  } catch (_) {
    throw new NotFoundError("Record not found");
  }
  if (record.getString("owner") !== userId) throw new NotFoundError("Record not found");
  return record;
}

function normalizeSecret(value) {
  let result = String(value || "").trim();
  // EnvironmentFile implementations may preserve a single layer of quotes.
  if (
    result.length >= 2 &&
    ((result[0] === '"' && result[result.length - 1] === '"') ||
      (result[0] === "'" && result[result.length - 1] === "'"))
  ) {
    result = result.slice(1, -1);
  }
  return result;
}

function configSecret(configKey, envName) {
  const environmentValue = normalizeSecret($os.getenv(envName));
  if (environmentValue) return environmentValue;
  const record = findOptional("app_config", "key = {:key}", { key: configKey });
  return record ? normalizeSecret(record.getString("secret_value")) : "";
}

function encryptionKey() {
  const key = configSecret("encryption_key", "LEAGUEPILOT_ENCRYPTION_KEY");
  if (!key || key.length !== 32) {
    throw new InternalServerError("Credential encryption is unavailable");
  }
  return key;
}

function requireWorker(e) {
  const expected = configSecret("worker_key", "LEAGUEPILOT_WORKER_KEY");
  const supplied = e.request.header.get("X-LeaguePilot-Worker-Key");
  if (!expected || expected.length < 32 || !supplied || !$security.equal(expected, supplied)) {
    throw new UnauthorizedError("Worker authentication failed");
  }
}

function setPrivateResponse(e) {
  e.response.header().set("Cache-Control", "no-store");
  e.response.header().set("X-Content-Type-Options", "nosniff");
}

function audit(app, owner, workspace, actor, action, targetType, targetId, details) {
  const record = new Record(app.findCollectionByNameOrId("audit_events"));
  record.set("owner", owner);
  if (workspace) record.set("workspace", workspace);
  if (actor) record.set("actor", actor);
  record.set("action", action);
  record.set("target_type", targetType);
  if (targetId) record.set("target_id", targetId);
  const hasDetails = details && typeof details === "object" && Object.keys(details).length > 0;
  record.set("details", hasDetails ? details : { recorded: true });
  app.save(record);
}

function usage(app, owner, workspace, kind, units, idempotencyKey, metadata) {
  if (findOptional("usage_events", "idempotency_key = {:key}", { key: idempotencyKey }, app)) {
    return;
  }
  const record = new Record(app.findCollectionByNameOrId("usage_events"));
  record.set("owner", owner);
  record.set("workspace", workspace);
  record.set("kind", kind);
  record.set("units", Math.max(0, Number(units) || 0));
  record.set("idempotency_key", idempotencyKey);
  record.set("metadata", metadata || {});
  app.save(record);
}

function enqueueJob(app, data) {
  const existing = findOptional(
    "job_runs",
    "idempotency_key = {:key}",
    { key: data.idempotencyKey },
    app,
  );
  if (existing) return existing;
  const job = new Record(app.findCollectionByNameOrId("job_runs"));
  job.set("owner", data.owner);
  job.set("workspace", data.workspace);
  if (data.connection) job.set("connection", data.connection);
  job.set("kind", data.kind);
  job.set("status", "queued");
  job.set("priority", data.priority == null ? 50 : data.priority);
  job.set("attempts", 0);
  job.set("max_attempts", data.maxAttempts || 5);
  job.set("idempotency_key", data.idempotencyKey);
  job.set("payload", data.payload || {});
  job.set("scheduled_for", data.scheduledFor || nowIso());
  app.save(job);
  return job;
}

function enqueueInactiveSweeps(app, windowId) {
  let offset = 0;
  let queued = 0;
  while (true) {
    const connections = app.findRecordsByFilter(
      "espn_connections",
      "status = 'connected'",
      "id",
      250,
      offset,
      {},
    );
    connections.forEach((connection) => {
      enqueueJob(app, {
        owner: connection.getString("owner"),
        workspace: connection.getString("workspace"),
        connection: connection.id,
        kind: "inactive-sweep",
        priority: 100,
        idempotencyKey: "inactive-sweep:" + connection.id + ":" + windowId,
        payload: { notify: true, trigger: "scheduled-lock-window" },
      });
      queued += 1;
    });
    if (connections.length < 250) break;
    offset += connections.length;
  }
  return queued;
}

function connectionView(record) {
  return {
    id: record.id,
    workspace: record.getString("workspace"),
    league_id: record.getInt("league_id"),
    team_id: record.getInt("team_id"),
    season: record.getInt("season"),
    is_public: record.getBool("is_public"),
    league_name: record.getString("league_name"),
    status: record.getString("status"),
    last_error: record.getString("last_error"),
    last_synced_at: record.getString("last_synced_at"),
    next_sync_at: record.getString("next_sync_at"),
  };
}

function validateLease(job, token) {
  if (job.getString("status") !== "running") throw new BadRequestError("Job is not running");
  if (!token || !$security.equal(job.getString("lease_token_hash"), $security.sha256(token))) {
    throw new UnauthorizedError("Invalid job lease");
  }
}

module.exports = {
  LP_VERSION,
  nowIso,
  cleanText,
  requiredText,
  integer,
  bodyOf,
  authId,
  findOptional,
  ownedWorkspace,
  ownedRecord,
  encryptionKey,
  requireWorker,
  setPrivateResponse,
  audit,
  usage,
  enqueueJob,
  enqueueInactiveSweeps,
  connectionView,
  validateLease,
};
