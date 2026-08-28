const state = {
  csrf: readCookie("fcc_csrf") || sessionStorage.getItem("fcc_csrf") || "",
  me: null,
  workspace: null,
  dashboard: null,
  connections: [],
  channels: [],
  reports: [],
  activity: [],
  latestReportMarkdown: "",
};

const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];

document.addEventListener("DOMContentLoaded", () => {
  bindEvents();
  restoreSession();
});

function bindEvents() {
  $("#auth-form").addEventListener("submit", signIn);
  $("#toggle-token").addEventListener("click", () => {
    const input = $("#access-token");
    input.type = input.type === "password" ? "text" : "password";
  });
  $("#sign-out").addEventListener("click", signOut);
  $("#mobile-menu").addEventListener("click", () => $(".sidebar").classList.toggle("open"));
  $$(".nav-item[data-view]").forEach((button) => {
    button.addEventListener("click", () => showView(button.dataset.view));
  });
  $("#connect-button").addEventListener("click", openConnectionDialog);
  $("#open-settings").addEventListener("click", openConnectionDialog);
  $("#connection-form").addEventListener("submit", saveConnection);
  $("#connection-form input[name='is_public']").addEventListener("change", togglePrivateFields);
  $("#sync-button").addEventListener("click", syncEspn);
  $("#run-all-analysis").addEventListener("click", runFullAnalysis);
  $("#refresh-recommendations").addEventListener("click", loadDashboard);
  $("#create-report").addEventListener("click", createReport);
  $("#pulse-report-button").addEventListener("click", createReport);
  $("#copy-report").addEventListener("click", copyLatestReport);
  $("#add-channel-button").addEventListener("click", () => $("#channel-dialog").showModal());
  $("#channel-form").addEventListener("submit", saveChannel);
  $("#channel-kind").addEventListener("change", updateChannelHelp);
  $("#refresh-activity").addEventListener("click", loadActivity);
  $$('[data-close-dialog]').forEach((button) => {
    button.addEventListener("click", () => $(`#${button.dataset.closeDialog}`).close());
  });
  $$(".analysis-button").forEach((button) => {
    button.addEventListener("click", () => runAnalysis(button.dataset.analysis));
  });
}

async function restoreSession() {
  try {
    const me = await api("/api/me");
    if (!readCookie("fcc_csrf")) {
      const refreshed = await api("/api/session/csrf");
      rememberCsrf(refreshed.csrf_token);
    }
    await enterApp(me);
  } catch {
    $("#auth-screen").hidden = false;
  }
}

async function signIn(event) {
  event.preventDefault();
  const button = event.submitter || event.currentTarget.querySelector("button[type='submit']");
  const error = $("#auth-error");
  button.disabled = true;
  error.textContent = "";
  try {
    const result = await api("/api/session", {
      method: "POST",
      body: { token: $("#access-token").value.trim() },
      skipCsrf: true,
    });
    rememberCsrf(result.csrf_token);
    $("#access-token").value = "";
    await enterApp(await api("/api/me"));
  } catch (requestError) {
    error.textContent = requestError.message;
  } finally {
    button.disabled = false;
  }
}

async function enterApp(me) {
  state.me = me;
  state.workspace = me.workspaces[0];
  if (!state.workspace) throw new Error("Your account has no workspace");
  $("#profile-name").textContent = me.display_name;
  $("#auth-screen").hidden = true;
  $("#app-shell").hidden = false;
  await loadDashboard();
  const auxiliaryLoads = await Promise.allSettled([
    loadConnections(),
    loadReports(),
    loadChannels(),
    loadActivity(),
  ]);
  if (auxiliaryLoads.some((result) => result.status === "rejected")) {
    toast("The dashboard loaded, but one secondary panel could not refresh.", true);
  }
}

async function signOut() {
  try {
    await api("/api/session", { method: "DELETE" });
  } catch {
    // Local session state still clears if the server session has expired.
  }
  sessionStorage.removeItem("fcc_csrf");
  window.location.reload();
}

async function loadConnections() {
  state.connections = await api(`/api/workspaces/${state.workspace.id}/connections/espn`);
  const connection = state.connections[0];
  $("#sync-button").disabled = !connection;
  $("#connect-button").innerHTML = connection ? "<span>⚙</span> Edit league" : "<span>＋</span> Connect league";
}

async function loadDashboard() {
  state.dashboard = await api(`/api/workspaces/${state.workspace.id}/dashboard`);
  renderDashboard(state.dashboard);
}

function renderDashboard(data) {
  const connection = data.connection;
  const league = data.league;
  const quality = data.data_quality || {};
  const hasLeagueData = Boolean(league);
  const isDemo = Boolean(data.demo && league && !connection);
  $("#league-kicker").textContent = connection?.league_name
    ? `${connection.league_name} · ESPN`
    : `${data.workspace.name} · ESPN`;
  $("#connection-state").textContent = data.connected
    ? quality.status === "stale" ? "STALE DATA" : "LIVE DATA"
    : isDemo ? "DEMO DATA" : connection?.status?.toUpperCase() || "PREVIEW";
  $(".live-pill").classList.toggle("connected", data.connected && quality.status !== "stale");
  $("#ai-mode").textContent = String(data.intelligence_mode || "rules").toUpperCase();

  const banner = $("#truth-banner");
  banner.classList.toggle("warning", quality.status === "stale");
  banner.classList.toggle("error", connection?.status === "error");
  if (connection?.status === "error") {
    $("#truth-message").textContent = `The latest ESPN sync failed: ${connection.last_error || "unknown connector error"}`;
  } else if (data.connected && quality.status === "stale") {
    $("#truth-message").textContent = `The stored ESPN snapshot is ${formatAge(quality.snapshot_age_seconds)} old. Sync before acting.`;
  } else if (data.connected) {
    $("#truth-message").textContent = `ESPN synchronized ${formatTime(connection.last_synced_at)}. Recommendations use this stored snapshot.`;
  } else if (isDemo) {
    $("#truth-message").textContent = "Fictional demo data is active. Analyses work, but no values came from ESPN.";
  } else {
    $("#truth-message").textContent = "Preview values are clearly labeled until ESPN is connected.";
  }
  $("#quality-line").textContent = hasLeagueData
    ? `${quality.projection_coverage_percent || 0}% roster projection coverage · ${quality.free_agent_count || 0} available players captured`
    : "No synchronized projection coverage yet.";

  $("#week-chip").textContent = `WEEK ${league?.week ?? "—"}`;
  $("#my-team-name").textContent = league?.team?.name || "Your team";
  $("#my-initials").textContent = initials(league?.team?.name || "YOU");

  const matchup = league?.matchup;
  const myId = league?.team?.id;
  let mine = 0;
  let theirs = 0;
  let opponentId = null;
  if (matchup && myId) {
    const home = matchup.home_team_id === myId;
    mine = home ? matchup.home_projected : matchup.away_projected;
    theirs = home ? matchup.away_projected : matchup.home_projected;
    opponentId = home ? matchup.away_team_id : matchup.home_team_id;
  }
  const opponentRank = (data.power_rankings || []).find((row) => row.team_id === opponentId);
  mine ||= Number(league?.team?.projected_total || 0);
  theirs ||= Number(opponentRank?.projected_total || 0);
  $("#my-projection").textContent = mine ? `${mine.toFixed(1)} projected` : "— projected";
  $("#opponent-projection").textContent = theirs ? `${theirs.toFixed(1)} projected` : "— projected";
  $("#opponent-name").textContent = opponentRank?.team || "Opponent";
  $("#opponent-initials").textContent = initials(opponentRank?.team || "OPP");
  const projectionShare = mine + theirs > 0 ? Math.round((100 * mine) / (mine + theirs)) : null;
  $("#win-probability").textContent = projectionShare ? `${projectionShare}%` : "—";
  $("#projected-margin").textContent = projectionShare
    ? `${mine >= theirs ? "+" : ""}${(mine - theirs).toFixed(1)} points`
    : "Connect ESPN to calculate";

  const recommendations = data.recommendations || [];
  renderRecommendations(recommendations, $("#recommendation-list"));
  renderRankings(data.power_rankings || []);
  const byKind = (kind) => recommendations.filter((item) => item.kind === kind);
  const lineupImpact = byKind("lineup").reduce(
    (total, item) => total + Math.max(0, item.impact_points),
    0,
  );
  $("#lineup-edge").textContent = lineupImpact
    ? `+${lineupImpact.toFixed(1)}`
    : hasLeagueData ? "0.0" : "—";
  $("#lineup-note").textContent = lineupImpact ? "Projected weekly gain" : "No pending lineup gain";
  $("#waiver-count").textContent = hasLeagueData ? byKind("waiver").length : "—";
  $("#waiver-note").textContent = byKind("waiver")[0]?.title || "Run waiver scan";
  $("#trade-count").textContent = hasLeagueData ? byKind("trade").length : "—";
  $("#trade-note").textContent = byKind("trade")[0]?.title || "Run trade finder";
  const risks = league?.team?.roster?.filter((player) =>
    ["OUT", "IR", "DOUBTFUL"].includes(player.injury_status?.toUpperCase()),
  ) || [];
  $("#risk-count").textContent = hasLeagueData ? risks.length : "—";
  $("#risk-note").textContent = risks[0]
    ? `${risks[0].name}: ${risks[0].injury_status}`
    : "No major status flags";
  $("#coach-brief").textContent = recommendations[0]?.summary
    || "LEAGUEPILOT AI is ready. Sync ESPN, then run the full analysis for an evidence-backed brief.";
}

function renderRecommendations(items, container) {
  if (!items.length) {
    container.innerHTML = `<div class="empty-state compact"><span>⌁</span><strong>No league decisions yet</strong><p>Connect ESPN and run an analysis. Nothing is fabricated while data is missing.</p></div>`;
    return;
  }
  container.innerHTML = items.slice(0, 8).map((item) => `
    <article class="recommendation">
      <div class="recommendation-icon">${kindIcon(item.kind)}</div>
      <div>
        <h3>${escapeHtml(item.title)} <span class="impact-chip">${impactLabel(item)}</span></h3>
        <p>${escapeHtml(item.summary)}</p>
        ${evidenceHtml(item.payload)}
      </div>
      <div class="recommendation-actions">
        <button class="approve" data-decision="approved" data-id="${item.id}" aria-label="Approve recommendation">✓</button>
        <button data-decision="dismissed" data-id="${item.id}" aria-label="Dismiss recommendation">×</button>
      </div>
    </article>`).join("");
  bindDecisionButtons(container);
}

function renderRankings(rows) {
  const container = $("#power-rankings");
  if (!rows.length) {
    container.innerHTML = `<div class="empty-state compact"><span>◉</span><strong>Rankings unlock after sync</strong><p>Record, points and projected strength are weighted transparently.</p></div>`;
    return;
  }
  container.innerHTML = rows.slice(0, 8).map((row, index) => `
    <div class="rank-row" title="Record ${row.record_score} · Points ${row.points_score} · Projection ${row.projection_score}">
      <span class="rank-number">${index + 1}</span>
      <span class="rank-name">${escapeHtml(row.team)}</span>
      <span class="rank-score">${Number(row.score).toFixed(1)}</span>
    </div>`).join("");
}

async function runAnalysis(kind, reportErrors = true) {
  if (!state.dashboard?.league) {
    if (reportErrors) toast("Connect and sync ESPN first.", true);
    return { ok: false, error: "No synchronized league snapshot" };
  }
  const button = $(`[data-analysis='${kind}']`);
  if (button) button.disabled = true;
  try {
    const results = await api(`/api/workspaces/${state.workspace.id}/analyses/${kind}`, {
      method: "POST",
    });
    renderFocusResults(kind, results);
    toast(`${labelFor(kind)} finished: ${results.length} decision${results.length === 1 ? "" : "s"}.`);
    await Promise.all([loadDashboard(), loadActivity()]);
    return { ok: true, results };
  } catch (error) {
    if (reportErrors) toast(error.message, true);
    return { ok: false, error: error.message };
  } finally {
    if (button) button.disabled = false;
  }
}

async function runFullAnalysis(event) {
  const button = event.currentTarget;
  button.disabled = true;
  try {
    const failures = [];
    for (const kind of ["lineup", "waivers", "trades"]) {
      const result = await runAnalysis(kind, false);
      if (!result.ok) failures.push(`${labelFor(kind)}: ${result.error}`);
    }
    if (failures.length) {
      toast(`Full analysis finished with ${failures.length} failure${failures.length === 1 ? "" : "s"}. ${failures.join(" · ")}`, true);
      return;
    }
    toast("Full league analysis complete.");
  } finally {
    button.disabled = false;
  }
}

function renderFocusResults(kind, results) {
  const container = $(`#${kind}-results`);
  if (!results.length) {
    container.innerHTML = `<div class="empty-state"><span>✓</span><strong>No positive ${escapeHtml(kind)} moves found</strong><p>The latest snapshot did not support a change.</p></div>`;
    return;
  }
  container.innerHTML = results.map((item) => `
    <article class="result-card">
      <h3>${escapeHtml(item.title)}</h3>
      <p>${escapeHtml(item.summary)}</p>
      <div class="result-meta"><span>${item.confidence}% confidence</span><span>${impactLabel(item)}</span><span>approval required</span></div>
      ${evidenceHtml(item.payload)}
      <div class="recommendation-actions">
        <button class="approve small-button" data-decision="approved" data-id="${item.id}">Approve</button>
        <button class="small-button" data-decision="dismissed" data-id="${item.id}">Dismiss</button>
      </div>
    </article>`).join("");
  bindDecisionButtons(container);
}

function bindDecisionButtons(container) {
  $$('[data-decision]', container).forEach((button) => {
    button.addEventListener("click", () =>
      decideRecommendation(button.dataset.id, button.dataset.decision),
    );
  });
}

async function decideRecommendation(id, decision) {
  try {
    await api(`/api/workspaces/${state.workspace.id}/recommendations/${id}/decision`, {
      method: "POST",
      body: { decision },
    });
    toast(decision === "approved"
      ? "Approved and recorded. No ESPN action was executed."
      : "Dismissed and recorded.");
    await Promise.all([loadDashboard(), loadActivity()]);
  } catch (error) {
    toast(error.message, true);
  }
}

function openConnectionDialog() {
  const form = $("#connection-form");
  const connection = state.connections[0];
  $("#connection-error").textContent = "";
  if (connection) {
    form.elements.league_id.value = connection.league_id;
    form.elements.team_id.value = connection.team_id;
    form.elements.season.value = connection.season;
    form.elements.is_public.checked = connection.is_public;
    form.elements.espn_s2.value = "";
    form.elements.swid.value = "";
    form.elements.espn_s2.placeholder = connection.is_public ? "" : "Leave blank to keep saved cookie";
    form.elements.swid.placeholder = connection.is_public ? "" : "Leave blank to keep saved cookie";
  }
  togglePrivateFields({ target: form.elements.is_public });
  $("#connection-dialog").showModal();
}

function togglePrivateFields(event) {
  $$(".private-field").forEach((field) => {
    field.hidden = event.target.checked;
  });
}

async function saveConnection(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const submit = form.querySelector("button[type='submit']");
  const values = Object.fromEntries(new FormData(form));
  submit.disabled = true;
  $("#connection-error").textContent = "";
  try {
    await api(`/api/workspaces/${state.workspace.id}/connections/espn`, {
      method: "PUT",
      body: {
        league_id: Number(values.league_id),
        team_id: Number(values.team_id),
        season: Number(values.season),
        is_public: values.is_public === "on",
        espn_s2: values.espn_s2 || null,
        swid: values.swid || null,
      },
    });
    $("#connection-dialog").close();
    await loadConnections();
    toast("ESPN connection encrypted and saved. Synchronizing now…");
    await syncEspn();
  } catch (error) {
    $("#connection-error").textContent = error.message;
  } finally {
    submit.disabled = false;
  }
}

async function syncEspn() {
  const connection = state.connections[0];
  if (!connection) return openConnectionDialog();
  const button = $("#sync-button");
  button.disabled = true;
  try {
    const result = await api(
      `/api/workspaces/${state.workspace.id}/connections/espn/${connection.id}/sync`,
      { method: "POST" },
    );
    toast(`${result.league_name} synchronized for Week ${result.week}.`);
  } catch (error) {
    toast(error.message, true);
  } finally {
    await Promise.allSettled([loadConnections(), loadDashboard(), loadActivity()]);
    button.disabled = false;
  }
}

async function createReport() {
  if (!state.dashboard?.league) return toast("Connect and sync ESPN first.", true);
  const buttons = [$("#create-report"), $("#pulse-report-button")];
  buttons.forEach((button) => { button.disabled = true; });
  try {
    const report = await api(`/api/workspaces/${state.workspace.id}/reports/weekly`, {
      method: "POST",
    });
    state.latestReportMarkdown = report.body_markdown;
    renderReport(report.body_markdown);
    await Promise.all([loadReports(), loadActivity()]);
    showView("pulse");
    toast(report.narration_mode === "rules-fallback"
      ? "Recap created with the reliable rules fallback."
      : "League recap generated from synchronized facts.");
  } catch (error) {
    toast(error.message, true);
  } finally {
    buttons.forEach((button) => { button.disabled = false; });
  }
}

async function loadReports() {
  state.reports = await api(`/api/workspaces/${state.workspace.id}/reports`);
  const container = $("#report-history");
  if (!state.reports.length) {
    container.innerHTML = `<div class="empty-state compact"><span>◷</span><strong>No reports yet</strong><p>Generated recaps will remain available here.</p></div>`;
    return;
  }
  container.innerHTML = state.reports.map((report, index) => `
    <button class="history-item" data-report-index="${index}">
      <span><strong>${escapeHtml(report.title)}</strong><small>Week ${report.week} · ${formatTime(report.created_at)}</small></span>
      <span aria-hidden="true">→</span>
    </button>`).join("");
  $$('[data-report-index]', container).forEach((button) => {
    button.addEventListener("click", () => showStoredReport(Number(button.dataset.reportIndex)));
  });
  if (!state.latestReportMarkdown) {
    state.latestReportMarkdown = state.reports[0].body_markdown;
    renderReport(state.latestReportMarkdown);
  }
}

function showStoredReport(index) {
  const report = state.reports[index];
  if (!report) return;
  state.latestReportMarkdown = report.body_markdown;
  renderReport(report.body_markdown);
  window.scrollTo({ top: 0, behavior: "smooth" });
}

function renderReport(markdown) {
  $("#report-preview").innerHTML = markdownToSafeHtml(markdown);
  $("#copy-report").disabled = !markdown;
}

async function copyLatestReport() {
  if (!state.latestReportMarkdown) return;
  try {
    await navigator.clipboard.writeText(state.latestReportMarkdown);
    toast("League recap copied.");
  } catch {
    toast("Your browser blocked clipboard access. Select the recap and copy it manually.", true);
  }
}

async function loadChannels() {
  state.channels = await api(`/api/workspaces/${state.workspace.id}/notifications`);
  const activeChannels = state.channels.filter((channel) => channel.is_active);
  const container = $("#notification-channel-list");
  if (!activeChannels.length) {
    container.innerHTML = `<div class="empty-state compact"><span>↗</span><strong>No delivery channel</strong><p>Add Discord or GroupMe when you are ready.</p></div>`;
    return;
  }
  container.innerHTML = activeChannels.map((channel) => `
    <div class="channel-row">
      <div class="channel-icon">${channel.kind === "discord" ? "D" : "G"}</div>
      <div><strong>${escapeHtml(channel.label)}</strong><small>${escapeHtml(channel.kind)} · encrypted</small></div>
      <div class="channel-actions">
        <button class="small-button" data-test-channel="${channel.id}">Send test</button>
        <button class="small-button danger" data-disable-channel="${channel.id}">Disable</button>
      </div>
    </div>`).join("");
  $$('[data-test-channel]', container).forEach((button) => {
    button.addEventListener("click", () => testChannel(button.dataset.testChannel, button));
  });
  $$('[data-disable-channel]', container).forEach((button) => {
    button.addEventListener("click", () => disableChannel(button.dataset.disableChannel));
  });
}

async function saveChannel(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const submit = form.querySelector("button[type='submit']");
  const values = Object.fromEntries(new FormData(form));
  submit.disabled = true;
  $("#channel-error").textContent = "";
  try {
    await api(`/api/workspaces/${state.workspace.id}/notifications`, {
      method: "POST",
      body: { kind: values.kind, label: values.label, target: values.target },
    });
    form.reset();
    updateChannelHelp();
    $("#channel-dialog").close();
    await Promise.all([loadChannels(), loadActivity()]);
    toast("Encrypted delivery channel saved. No message was sent.");
  } catch (error) {
    $("#channel-error").textContent = error.message;
  } finally {
    submit.disabled = false;
  }
}

function updateChannelHelp() {
  const isDiscord = $("#channel-kind").value === "discord";
  $("#channel-target-label").textContent = isDiscord ? "Discord webhook URL" : "GroupMe bot ID";
  $("#channel-form").elements.target.placeholder = isDiscord
    ? "https://discord.com/api/webhooks/…"
    : "Paste the GroupMe bot ID";
  $("#channel-help").textContent = isDiscord
    ? "Create a webhook in your Discord channel settings, then paste its URL here."
    : "Create a GroupMe bot for the league group, then paste its bot ID here.";
}

async function testChannel(channelId, button) {
  if (!window.confirm("Send one LEAGUEPILOT AI test message to this channel?")) return;
  button.disabled = true;
  try {
    await api(`/api/workspaces/${state.workspace.id}/notifications/${channelId}/test`, {
      method: "POST",
    });
    toast("Test message delivered.");
    await loadActivity();
  } catch (error) {
    toast(error.message, true);
  } finally {
    button.disabled = false;
  }
}

async function disableChannel(channelId) {
  if (!window.confirm("Disable this delivery channel and remove its stored encrypted target?")) return;
  try {
    await api(`/api/workspaces/${state.workspace.id}/notifications/${channelId}`, {
      method: "DELETE",
    });
    await Promise.all([loadChannels(), loadActivity()]);
    toast("Delivery channel disabled.");
  } catch (error) {
    toast(error.message, true);
  }
}

async function loadActivity() {
  state.activity = await api(`/api/workspaces/${state.workspace.id}/activity?limit=12`);
  const container = $("#activity-list");
  if (!state.activity.length) {
    container.innerHTML = `<div class="empty-state compact"><span>✓</span><strong>No activity yet</strong></div>`;
    return;
  }
  container.innerHTML = state.activity.map((event) => `
    <div class="activity-row">
      <span class="activity-dot"></span>
      <span><strong>${escapeHtml(humanizeAction(event.action))}</strong><small>${escapeHtml(event.target_type)}</small></span>
      <small>${formatTime(event.created_at)}</small>
    </div>`).join("");
}

function showView(name) {
  $$("[data-view-panel]").forEach((panel) => {
    panel.classList.toggle("active", panel.dataset.viewPanel === name);
  });
  $$(".nav-item[data-view]").forEach((button) => {
    button.classList.toggle("active", button.dataset.view === name);
  });
  const titles = {
    command: "Command Center",
    lineup: "Lineup Lab",
    waivers: "Waiver Radar",
    trades: "Trade Finder",
    pulse: "League Pulse",
    automation: "Automation Control",
  };
  $("#view-title").textContent = titles[name] || "Command Center";
  $(".sidebar").classList.remove("open");
  if (["lineup", "waivers", "trades"].includes(name) && state.dashboard) {
    const kindByView = { lineup: "lineup", waivers: "waiver", trades: "trade" };
    const stored = state.dashboard.recommendations.filter((item) =>
      item.kind === kindByView[name],
    );
    if (stored.length) renderFocusResults(name, stored);
  }
  if (name === "automation") Promise.allSettled([loadChannels(), loadActivity()]);
  if (name === "pulse") loadReports().catch((error) => toast(error.message, true));
  window.scrollTo({ top: 0, behavior: "smooth" });
}

async function api(path, options = {}) {
  const method = options.method || "GET";
  const headers = { Accept: "application/json" };
  if (options.body) headers["Content-Type"] = "application/json";
  const cookieCsrf = readCookie("fcc_csrf");
  if (cookieCsrf) rememberCsrf(cookieCsrf);
  if (state.csrf && !options.skipCsrf && !["GET", "HEAD", "OPTIONS"].includes(method)) {
    headers["X-CSRF-Token"] = state.csrf;
  }
  const response = await fetch(path, {
    method,
    headers,
    credentials: "same-origin",
    body: options.body ? JSON.stringify(options.body) : undefined,
  });
  if (
    response.status === 401
    && !options.skipCsrf
    && !options.retriedCsrf
    && !["GET", "HEAD", "OPTIONS"].includes(method)
  ) {
    const refreshed = await fetch("/api/session/csrf", {
      headers: { Accept: "application/json" },
      credentials: "same-origin",
    });
    if (refreshed.ok) {
      rememberCsrf((await refreshed.json()).csrf_token);
      return api(path, { ...options, retriedCsrf: true });
    }
  }
  if (!response.ok) {
    let detail = `Request failed (${response.status})`;
    try {
      const payload = await response.json();
      detail = typeof payload.detail === "string"
        ? payload.detail
        : payload.detail?.[0]?.msg || detail;
    } catch {
      // Preserve the status-based fallback.
    }
    throw new Error(detail);
  }
  return response.status === 204 ? null : response.json();
}

function rememberCsrf(value) {
  state.csrf = value || "";
  if (state.csrf) sessionStorage.setItem("fcc_csrf", state.csrf);
}

function readCookie(name) {
  const prefix = `${name}=`;
  const match = document.cookie.split(";").map((value) => value.trim()).find((value) =>
    value.startsWith(prefix),
  );
  return match ? decodeURIComponent(match.slice(prefix.length)) : "";
}

function toast(message, error = false) {
  const element = document.createElement("div");
  element.className = `toast${error ? " error" : ""}`;
  element.textContent = message;
  $("#toast-region").append(element);
  setTimeout(() => element.remove(), 4500);
}

function evidenceHtml(payload = {}) {
  const allowed = [
    "evidence_source",
    "risk_flags",
    "suggested_faab_percent",
    "fairness_score",
    "mutual_fit_score",
    "my_estimated_lineup_gain",
    "partner_estimated_lineup_gain",
  ];
  const rows = allowed
    .filter((key) => payload[key] !== undefined && payload[key] !== null)
    .map((key) => {
      const raw = Array.isArray(payload[key]) ? payload[key].join("; ") || "none" : payload[key];
      return `<span class="evidence-chip"><b>${escapeHtml(humanizeAction(key))}:</b> ${escapeHtml(raw)}</span>`;
    });
  if (!rows.length) return "";
  return `<details class="evidence-details"><summary>View evidence</summary><div class="evidence-grid">${rows.join("")}</div></details>`;
}

function impactLabel(item) {
  if (item.kind === "trade" && item.payload?.mutual_fit_score !== undefined) {
    return `${Number(item.payload.mutual_fit_score).toFixed(1)} fit`;
  }
  return `${item.impact_points > 0 ? "+" : ""}${Number(item.impact_points).toFixed(1)} pts`;
}

function formatTime(value) {
  if (!value) return "recently";
  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(new Date(value));
}

function formatAge(seconds) {
  const value = Number(seconds || 0);
  if (value < 60) return "less than a minute";
  if (value < 3600) return `${Math.round(value / 60)} minutes`;
  if (value < 86400) return `${Math.round(value / 3600)} hours`;
  return `${Math.round(value / 86400)} days`;
}

function initials(value) {
  return String(value).split(/\s+/).map((part) => part[0]).join("").slice(0, 3).toUpperCase();
}

function labelFor(kind) {
  return ({ lineup: "Lineup analysis", waivers: "Waiver scan", trades: "Trade finder" })[kind] || kind;
}

function kindIcon(kind) {
  return ({ lineup: "↕", waiver: "+", trade: "⇄" })[kind] || "✦";
}

function humanizeAction(value) {
  return String(value || "").replace(/[._-]+/g, " ").replace(/\b\w/g, (letter) =>
    letter.toUpperCase(),
  );
}

function escapeHtml(value) {
  const node = document.createElement("div");
  node.textContent = String(value ?? "");
  return node.innerHTML;
}

function markdownToSafeHtml(markdown) {
  const lines = String(markdown).split("\n");
  const output = [];
  let inList = false;
  for (const line of lines) {
    if (!line.trim()) continue;
    const safe = escapeHtml(line).replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
    if (safe.startsWith("- ") || safe.startsWith("• ")) {
      if (!inList) output.push("<ul>");
      inList = true;
      output.push(`<li>${safe.slice(2)}</li>`);
      continue;
    }
    if (inList) {
      output.push("</ul>");
      inList = false;
    }
    if (safe.startsWith("## ")) output.push(`<h2>${safe.slice(3)}</h2>`);
    else if (safe.startsWith("### ")) output.push(`<h3>${safe.slice(4)}</h3>`);
    else output.push(`<p>${safe}</p>`);
  }
  if (inList) output.push("</ul>");
  return output.join("");
}
