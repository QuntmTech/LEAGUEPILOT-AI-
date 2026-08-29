"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import {
  Activity, AlertTriangle, ArrowRight, Bell, BookOpen, Bot, CalendarDays, Check,
  ChevronDown, CircleAlert, Clock3, FileText, Gauge, ListChecks,
  Loader2, LogOut, Menu, Play, Radar, RefreshCw, SearchCheck,
  ShieldCheck, Sparkles, Trophy, UserRound, Users, XCircle,
} from "lucide-react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuLabel, DropdownMenuSeparator, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { Progress } from "@/components/ui/progress";
import {
  Sidebar, SidebarContent, SidebarFooter, SidebarGroup, SidebarGroupContent,
  SidebarGroupLabel, SidebarHeader, SidebarInset, SidebarMenu, SidebarMenuBadge,
  SidebarMenuButton, SidebarMenuItem, SidebarProvider, SidebarRail, SidebarTrigger,
  useSidebar,
} from "@/components/ui/sidebar";
import { Skeleton } from "@/components/ui/skeleton";
import { Switch } from "@/components/ui/switch";
import { Toaster } from "@/components/ui/sonner";
import { LeagueContextBar } from "@/components/league-context-bar";
import { ConnectEspnForm } from "@/components/connect-espn-form";
import { NAV_SECTIONS, type SectionId } from "@/lib/leaguepilot-nav";
import { useLeagueScope } from "@/lib/use-league-scope";

type Item = Record<string, unknown>;

// Navigation is defined once in lib/leaguepilot-nav so the sidebar, the mobile bar and
// any future route mapping cannot drift apart.
const navigation = NAV_SECTIONS;

const previewData = {
  workspace: { id: "preview-workspace", name: "Sunday Strategists" },
  league: {
    name: "Fourth & Forever",
    season: "2026",
    current_week: "4",
    team_count: 12,
    last_synced_at: "2026-08-28T13:42:00.000Z",
    roster: [
      { id: "p1", position: "QB", name: "Lamar Jackson", team: "BAL", status: "Active" },
      { id: "p2", position: "RB", name: "Bijan Robinson", team: "ATL", status: "Active" },
      { id: "p3", position: "WR", name: "Amon-Ra St. Brown", team: "DET", status: "Active" },
      { id: "p4", position: "TE", name: "Trey McBride", team: "ARI", status: "Active" },
      { id: "p5", position: "FLEX", name: "Jaylen Waddle", team: "MIA", status: "Questionable" },
      { id: "p6", position: "K", name: "Brandon Aubrey", team: "DAL", status: "Active" },
    ],
  },
  espn_connected: true,
  recommendations: [
    { id: "r1", kind: "Lineup", title: "Move Waddle to the bench until warmups", summary: "His questionable tag and a late kickoff create avoidable lineup risk.", confidence: "91%", impact: "+4.8 pts", risk: "Low", evidence: "Practice participation, kickoff timing, and your available early-window replacement support the safer start." },
    { id: "r2", kind: "Waiver", title: "Place a priority claim on Trey Benson", summary: "Usage is rising and your RB depth drops sharply after your starters.", confidence: "84%", impact: "+6 ROS", risk: "Medium", evidence: "Snap share and route participation increased in consecutive games while your bench lacks a second playable running back." },
    { id: "r3", kind: "Trade", title: "Shop your second quarterback for WR depth", summary: "One league mate has the clearest need and enough receiver surplus.", confidence: "76%", impact: "Roster balance", risk: "Medium", evidence: "Roster construction and recent transaction history identify the most realistic trade partner." },
  ],
  reports: [
    { id: "rep1", status: "Ready", kind: "Weekly report", title: "Week 4 league intelligence brief", summary: "Three contenders separated themselves, two waiver trends matter, and one matchup has real upset potential.", created_at: "2026-08-28T13:47:00.000Z" },
    { id: "rep2", status: "Ready", kind: "Power rankings", title: "The middle tier is tightening", summary: "Teams four through eight are separated by less than five projected points.", created_at: "2026-08-21T13:47:00.000Z" },
  ],
  jobs: [
    { id: "j1", status: "succeeded", kind: "Full analysis", message: "Lineup, waiver, trade, and reporting analysis completed.", updated_at: "2026-08-28T13:47:00.000Z" },
    { id: "j2", status: "succeeded", kind: "Weekly sync", message: "League snapshot synchronized successfully.", updated_at: "2026-08-28T13:42:00.000Z" },
  ],
  data_quality_warnings: ["One player has a questionable injury designation; verify active status before kickoff."],
};

const obj = (value: unknown): Item => value && typeof value === "object" && !Array.isArray(value) ? value as Item : {};
const list = (value: unknown): Item[] => Array.isArray(value) ? value.filter((item) => item && typeof item === "object") as Item[] : [];
const text = (record: Item, keys: string[], fallback = "") => {
  for (const key of keys) if (typeof record[key] === "string" && String(record[key]).trim()) return String(record[key]);
  return fallback;
};
const count = (record: Item, keys: string[], fallback = 0) => {
  for (const key of keys) if (typeof record[key] === "number") return Number(record[key]);
  return fallback;
};
const dateLabel = (value: string) => {
  if (!value) return "Not synced yet";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : new Intl.DateTimeFormat("en-US", { month: "short", day: "numeric", hour: "numeric", minute: "2-digit", timeZone: "UTC", timeZoneName: "short" }).format(date);
};

function normalize(raw: unknown) {
  const outer = obj(raw);
  const root = Object.keys(obj(outer.data)).length ? obj(outer.data) : outer;
  const workspace = Object.keys(obj(root.workspace)).length ? obj(root.workspace) : list(root.workspaces)[0] ?? {};
  const league = Object.keys(obj(root.league)).length ? obj(root.league) : Object.keys(obj(workspace.league)).length ? obj(workspace.league) : list(root.leagues)[0] ?? {};
  return {
    root, workspace, league,
    recommendations: list(root.recommendations).length ? list(root.recommendations) : list(workspace.recommendations),
    reports: list(root.reports).length ? list(root.reports) : list(workspace.reports),
    jobs: list(root.jobs).length ? list(root.jobs) : list(root.activity),
    roster: list(root.roster).length ? list(root.roster) : list(league.roster),
    warnings: Array.isArray(root.data_quality_warnings) ? root.data_quality_warnings.map(String) : Array.isArray(root.warnings) ? root.warnings.map(String) : [],
  };
}

function workspaceIdOf(data: { workspace: Item }): string | null {
  const id = data.workspace?.id;
  return typeof id === "string" && id ? id : null;
}

function Brand() {
  return <Link href="/" className="lp-dash-brand" aria-label="LEAGUEPILOT AI homepage"><span>LP<small>AI</small></span><b>LEAGUEPILOT <em>AI</em></b></Link>;
}

function AppSidebar({ active, onChange, recommendationCount }: { active: SectionId; onChange: (value: SectionId) => void; recommendationCount: number }) {
  const { setOpenMobile } = useSidebar();
  const choose = (value: SectionId) => { onChange(value); setOpenMobile(false); };
  return <Sidebar collapsible="icon" className="lp-dashboard-sidebar">
    <SidebarHeader><Brand /></SidebarHeader>
    <SidebarContent><SidebarGroup><SidebarGroupLabel>Command center</SidebarGroupLabel><SidebarGroupContent><SidebarMenu>
      {navigation.map(({ id, label, icon: Icon }) => <SidebarMenuItem key={id}><SidebarMenuButton isActive={active === id} tooltip={label} onClick={() => choose(id)}><Icon /><span>{label}</span></SidebarMenuButton>{id === "moves" && recommendationCount > 0 && <SidebarMenuBadge>{recommendationCount}</SidebarMenuBadge>}</SidebarMenuItem>)}
    </SidebarMenu></SidebarGroupContent></SidebarGroup>
      <SidebarGroup><SidebarGroupLabel>Connection</SidebarGroupLabel><SidebarGroupContent><div className="lp-backend-status"><span /><p><b>PocketBase</b><small>Shared source of truth</small></p></div></SidebarGroupContent></SidebarGroup>
    </SidebarContent>
    <SidebarFooter><div className="lp-sidebar-security"><ShieldCheck /><span><b>Approval controlled</b><small>No silent ESPN changes</small></span></div></SidebarFooter>
    <SidebarRail />
  </Sidebar>;
}

function EmptyState({ icon: Icon, title, copy, action }: { icon: typeof Trophy; title: string; copy: string; action?: React.ReactNode }) {
  return <div className="lp-empty"><span><Icon /></span><h3>{title}</h3><p>{copy}</p>{action}</div>;
}

function StatusBadge({ status }: { status: string }) {
  const normalized = status.toLowerCase();
  return <Badge className={`lp-job-badge ${["queued", "pending"].includes(normalized) ? "queued" : normalized}`}>
    {["queued", "pending", "running"].includes(normalized) && <Loader2 className="lp-spin" />}{normalized === "succeeded" && <Check />}{normalized === "failed" && <XCircle />}{status || "Unknown"}
  </Badge>;
}

export function LeaguePilotDashboard({ previewMode = false }: { previewMode?: boolean }) {
  const [active, setActive] = useState<SectionId>("overview");
  const [user, setUser] = useState<Item>(previewMode ? { name: "Alex Morgan", email: "alex@example.com" } : {});
  const [raw, setRaw] = useState<unknown>(previewMode ? previewData : {});
  const [loading, setLoading] = useState(!previewMode);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState("");
  const [analysisJob, setAnalysisJob] = useState<Item>({});
  const [selectedRecommendation, setSelectedRecommendation] = useState<Item | null>(null);
  const data = useMemo(() => normalize(raw), [raw]);
  // Live mode only: preview runs on fictional records and must not hit the backend.
  const scope = useLeagueScope(previewMode ? null : (workspaceIdOf(data) ?? null));
  // Both lists come straight from backend recommendations — nothing is synthesised.
  const tradeRecommendations = useMemo(
    () => scope.recommendations.filter((item) => item.kind === "trade"),
    [scope.recommendations],
  );
  const alertRecommendations = useMemo(
    () => scope.recommendations.filter((item) => item.kind === "availability-alert"),
    [scope.recommendations],
  );

  const loadBootstrap = useCallback(async (quiet = false) => {
    if (previewMode) {
      if (!quiet) toast.message("Preview data refreshed", { description: "This demo uses fictional records and never writes to PocketBase." });
      setRefreshing(false);
      return;
    }
    if (!quiet) setRefreshing(true);
    try {
      const response = await fetch("/api/leaguepilot/bootstrap", { method: "POST" });
      if (response.status === 401) { window.location.assign("/sign-in"); return; }
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(payload.message || "The dashboard could not load your PocketBase records.");
      setRaw(payload); setError("");
      const root = Object.keys(obj(obj(payload).data)).length ? obj(obj(payload).data) : obj(payload);
      const latestJob = list(root.jobs)[0] ?? list(root.activity)[0];
      if (latestJob) setAnalysisJob(latestJob);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "The dashboard could not load.");
    } finally {
      setLoading(false); setRefreshing(false);
    }
  }, [previewMode]);

  useEffect(() => {
    if (previewMode) return;
    async function start() {
      const session = await fetch("/api/auth/session");
      if (!session.ok) { window.location.assign("/sign-in"); return; }
      const payload = await session.json().catch(() => ({}));
      setUser(obj(payload.user));
      await loadBootstrap();
    }
    void start();
  }, [loadBootstrap, previewMode]);

  const jobStatus = text(analysisJob, ["status", "state"]);
  useEffect(() => {
    if (!["queued", "pending", "running"].includes(jobStatus.toLowerCase())) return;
    const timer = window.setInterval(() => void loadBootstrap(true), 4000);
    return () => window.clearInterval(timer);
  }, [jobStatus, loadBootstrap]);

  const workspaceId = text(data.workspace, ["id", "workspace_id"]);
  const workspaceName = text(data.workspace, ["name", "workspace_name"], "Workspace not created yet");
  const leagueName = text(data.league, ["name", "league_name"], "No ESPN league connected");
  const season = text(data.league, ["season", "year"], text(data.root, ["season"], "—"));
  const week = text(data.league, ["week", "current_week"], text(data.root, ["week", "current_week"], "—"));
  const lastSync = text(data.league, ["last_sync", "last_synced_at", "synced"], text(data.workspace, ["last_sync", "last_synced_at"]));
  const connected = Boolean(Object.keys(data.league).length || data.root.espn_connected === true);
  const activeJobs = data.jobs.filter((job) => ["queued", "pending", "running"].includes(text(job, ["status", "state"]).toLowerCase()));
  const currentJob = Object.keys(analysisJob).length ? analysisJob : activeJobs[0] ?? data.jobs[0] ?? {};
  const currentStatus = text(currentJob, ["status", "state"]);
  const userName = text(user, ["name", "username"], text(user, ["email"], "Manager"));
  const userEmail = text(user, ["email"]);

  async function runAnalysis() {
    if (!workspaceId) return;
    setAnalysisJob({ status: "queued", kind: "full" });
    if (previewMode) {
      toast.success("Preview analysis queued", { description: "Simulating the same live status flow used by the authenticated dashboard." });
      setActive("activity");
      window.setTimeout(() => setAnalysisJob({ status: "running", kind: "Full analysis", message: "Evaluating lineup, waivers, trades, and reports…" }), 650);
      window.setTimeout(() => {
        setAnalysisJob({ status: "succeeded", kind: "Full analysis", message: "Fictional preview analysis completed." });
        toast.success("Preview analysis complete", { description: "No backend records were changed." });
      }, 2200);
      return;
    }
    try {
      const response = await fetch(`/api/leaguepilot/workspaces/${encodeURIComponent(workspaceId)}/analysis`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ kind: "full", notify: false }) });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(payload.message || "Full analysis could not be started.");
      setAnalysisJob(obj(payload.job ?? payload));
      toast.success("Full analysis queued", { description: "Live status will refresh automatically." });
      setActive("activity");
    } catch (cause) {
      const message = cause instanceof Error ? cause.message : "Analysis failed.";
      setAnalysisJob({ status: "failed", message });
      toast.error("Analysis did not start", { description: message });
    }
  }

  async function signOut() {
    if (!previewMode) await fetch("/api/auth/logout", { method: "POST" });
    window.location.assign("/sign-in");
  }

  if (loading) return <div className="lp-dashboard-loading"><Brand /><div><Skeleton className="h-4 w-48" /><Skeleton className="h-10 w-80" /><Skeleton className="h-40 w-full" /></div></div>;

  return <SidebarProvider style={{ "--sidebar-width": "248px", "--sidebar-width-icon": "72px" } as React.CSSProperties} className="lp-dashboard">
    <AppSidebar active={active} onChange={setActive} recommendationCount={data.recommendations.length} />
    <SidebarInset className="lp-dashboard-main">
      <header className="lp-dashboard-topbar"><div><SidebarTrigger className="lp-sidebar-trigger" /><span className="lp-topbar-divider" /><p><small>LEAGUEPILOT AI</small><b>{navigation.find((item) => item.id === active)?.label}</b></p></div><div className="lp-topbar-actions"><span className={previewMode ? "lp-api-status preview" : "lp-api-status"}><i /> {previewMode ? "Fictional preview" : "PocketBase live"}</span><Button variant="outline" size="icon" aria-label="Notifications"><Bell /></Button><DropdownMenu><DropdownMenuTrigger asChild><Button variant="outline" className="lp-account-button"><span>{userName.slice(0, 1).toUpperCase()}</span><p><b>{userName}</b><small>{userEmail}</small></p><ChevronDown /></Button></DropdownMenuTrigger><DropdownMenuContent align="end" className="lp-account-menu"><DropdownMenuLabel>My account</DropdownMenuLabel><DropdownMenuSeparator /><DropdownMenuItem onClick={() => setActive("settings")}><UserRound /> Account settings</DropdownMenuItem><DropdownMenuItem onClick={signOut} variant="destructive"><LogOut /> {previewMode ? "Open sign in" : "Sign out"}</DropdownMenuItem></DropdownMenuContent></DropdownMenu></div></header>

      <div className="lp-dashboard-workspace">
        {previewMode && <div className="lp-preview-banner"><Sparkles /><p><b>Interactive product preview</b><span>Every league, player, recommendation, and job shown here is fictional. Your protected <Link href="/app">/app dashboard</Link> reads only your PocketBase records.</span></p><Link href="/create-account">Create account <ArrowRight /></Link></div>}
        {error && <div className="lp-dashboard-error"><AlertTriangle /><span><b>Backend connection issue</b>{error}</span><Button variant="outline" onClick={() => loadBootstrap()}>Retry</Button></div>}

        {!previewMode && (
          <LeagueContextBar
            workspaceName={typeof data.workspace?.name === "string" ? data.workspace.name : null}
            connections={scope.connections}
            connectionId={scope.connectionId}
            connection={scope.connection}
            latestJob={scope.latestJob}
            busy={scope.status === "loading" || refreshing}
            onSelect={scope.selectConnection}
            onSync={() => {
              const id = scope.connectionId;
              if (!id) return;
              void fetch(`/api/leaguepilot/connections/${id}/sync`, { method: "POST" })
                .then((r) => r.json().catch(() => ({})))
                .then((payload) => {
                  if (payload?.message) toast.error(payload.message);
                  else toast.success("Sync queued.");
                  scope.refresh();
                })
                .catch(() => toast.error("We couldn't start that sync."));
            }}
            onRunAnalysis={runAnalysis}
          />
        )}

        {active === "overview" && <section className="lp-view">
          <div className="lp-view-heading"><div><p className="lp-app-kicker">WEEKLY COMMAND CENTER</p><h1>{leagueName}</h1><p>{workspaceName} · {season === "—" ? "Season not synchronized" : `${season} season`} · Week {week}</p></div><div className="lp-heading-actions"><Button variant="outline" onClick={() => loadBootstrap()} disabled={refreshing}><RefreshCw className={refreshing ? "lp-spin" : ""} /> Refresh</Button><Button onClick={runAnalysis} disabled={!workspaceId || ["queued", "pending", "running"].includes(currentStatus.toLowerCase())}><Play /> Run Full Analysis</Button></div></div>
          {!connected && <div className="lp-first-run"><div><span><Radar /></span><p className="lp-app-kicker">FIRST RUN</p><h2>Connect your ESPN league to activate the command center.</h2><p>Your account is ready. The dashboard stays honestly empty until the backend returns a synchronized league snapshot.</p></div><div className="lp-first-run-steps"><span className="done"><b>01</b><p><strong>Account created</strong><small>PocketBase authentication is active</small></p><Check /></span><span><b>02</b><p><strong>Connect ESPN</strong><small>Add your league below</small></p><Clock3 /></span><span><b>03</b><p><strong>Run first analysis</strong><small>Lineup, waivers, trades, and reports</small></p><Gauge /></span></div>
            {!previewMode && workspaceId && <ConnectEspnForm workspaceId={workspaceId} onConnected={() => { toast.success("League saved. A read-only sync is queued."); void loadBootstrap(true); scope.refresh(); }} />}
          </div>}
          <div className="lp-status-grid">
            <article><span className={connected ? "good" : "warn"}>{connected ? <Check /> : <CircleAlert />}</span><p><small>ESPN CONNECTION</small><b>{connected ? "Connected" : "Action required"}</b><em>{connected ? leagueName : "No league snapshot"}</em></p></article>
            <article><span><CalendarDays /></span><p><small>LAST SUCCESSFUL SYNC</small><b>{dateLabel(lastSync)}</b><em>{lastSync ? "PocketBase snapshot" : "Waiting for first sync"}</em></p></article>
            <article><span className={currentStatus === "failed" ? "bad" : ""}><Activity /></span><p><small>ANALYSIS JOB</small><b>{currentStatus ? <StatusBadge status={currentStatus} /> : "No active job"}</b><em>{text(currentJob, ["kind", "type"], "Full analysis")}</em></p></article>
            <article><span><SearchCheck /></span><p><small>DATA QUALITY</small><b>{data.warnings.length ? `${data.warnings.length} warning${data.warnings.length === 1 ? "" : "s"}` : connected ? "No reported warnings" : "Not available"}</b><em>{data.warnings[0] ?? "Checked with each snapshot"}</em></p></article>
          </div>
          <div className="lp-overview-grid">
            <article className="lp-panel lp-recommendation-panel"><div className="lp-panel-head"><div><p className="lp-app-kicker">TOP RECOMMENDATIONS</p><h2>What needs your attention</h2></div><Button variant="ghost" onClick={() => setActive("moves")}>View all <ArrowRight /></Button></div>
              {data.recommendations.length ? <div className="lp-rec-list">{data.recommendations.slice(0, 3).map((rec, index) => <button key={text(rec, ["id"], String(index))} onClick={() => setSelectedRecommendation(rec)}><span className="lp-rec-rank">0{index + 1}</span><div><small>{text(rec, ["kind", "type", "category"], "RECOMMENDATION").toUpperCase()}</small><b>{text(rec, ["title", "headline", "recommendation"], "Review recommendation")}</b><p>{text(rec, ["summary", "reason", "description"], "Open this recommendation to inspect the verified evidence.")}</p></div><Badge>{text(rec, ["confidence"], "Review")}</Badge><ArrowRight /></button>)}</div>
              : <EmptyState icon={ListChecks} title="No recommendations yet" copy={connected ? "Run Full Analysis to generate recommendations from the current league snapshot." : "Recommendations appear after your ESPN league is connected and analyzed."} action={workspaceId && <Button onClick={runAnalysis}><Play /> Run Full Analysis</Button>} />}
            </article>
            <article className="lp-panel lp-report-panel"><div className="lp-panel-head"><div><p className="lp-app-kicker">LATEST WEEKLY REPORT</p><h2>League intelligence brief</h2></div></div>
              {data.reports.length ? <div className="lp-latest-report"><span><FileText /></span><Badge>{text(data.reports[0], ["status"], "Ready")}</Badge><h3>{text(data.reports[0], ["title", "name"], "Weekly league report")}</h3><p>{text(data.reports[0], ["summary", "excerpt", "content"], "Open the report to review this week’s league-wide findings.")}</p><Button variant="outline" onClick={() => setActive("reports")}>Open report <ArrowRight /></Button></div>
              : <EmptyState icon={FileText} title="No weekly report yet" copy="The latest verified report will appear here after analysis succeeds." />}
            </article>
          </div>
          {data.warnings.length > 0 && <div className="lp-quality-warning"><AlertTriangle /><div><b>Data-quality warning</b><p>{data.warnings.join(" · ")}</p></div></div>}
        </section>}

        {active === "league" && <section className="lp-view"><div className="lp-view-heading"><div><p className="lp-app-kicker">MY LEAGUE</p><h1>{leagueName}</h1><p>Live league details from the shared PocketBase snapshot.</p></div></div>
          {!connected ? <EmptyState icon={Trophy} title="No ESPN league connected" copy="Once the backend returns a league snapshot, this section will show real scoring settings, roster information, standings, and sync health." /> : <><div className="lp-league-hero"><div><span><Trophy /></span><div className="lp-league-title"><small>ACTIVE LEAGUE</small><h2>{leagueName}</h2><b>{season} season · Week {week}</b></div></div><div><span><small>TEAMS</small><b>{count(data.league, ["team_count", "teams"], list(data.league.teams).length) || "—"}</b></span><span><small>ROSTERED PLAYERS</small><b>{data.roster.length || "—"}</b></span><span><small>LAST SYNC</small><b>{dateLabel(lastSync)}</b></span></div></div><div className="lp-panel"><div className="lp-panel-head"><div><p className="lp-app-kicker">YOUR ROSTER</p><h2>Current synchronized players</h2></div></div>{data.roster.length ? <div className="lp-roster-grid">{data.roster.map((player, index) => <article key={text(player, ["id"], String(index))}><span>{text(player, ["position"], "—")}</span><p><b>{text(player, ["name", "full_name", "player_name"], "Unnamed player")}</b><small>{text(player, ["team", "pro_team"], "Team unavailable")}</small></p><em>{text(player, ["status"], "Active")}</em></article>)}</div> : <EmptyState icon={Users} title="Roster data has not arrived" copy="The connected backend has not returned roster records for this league." />}</div></>}
        </section>}

        {active === "moves" && <section className="lp-view"><div className="lp-view-heading"><div><p className="lp-app-kicker">DECISION QUEUE</p><h1>Recommendations</h1><p>Review impact, confidence, evidence, and risks before deciding.</p></div><Button onClick={runAnalysis} disabled={!workspaceId || ["queued", "pending", "running"].includes(currentStatus.toLowerCase())}><Play /> Run Full Analysis</Button></div>
          {data.recommendations.length ? <div className="lp-recommendations-grid">{data.recommendations.map((rec, index) => <article key={text(rec, ["id"], String(index))}><div><span>0{index + 1}</span><Badge>{text(rec, ["kind", "type"], "Decision")}</Badge></div><h2>{text(rec, ["title", "headline", "recommendation"], "Review recommendation")}</h2><p>{text(rec, ["summary", "reason", "description"], "Evidence is available in the recommendation record.")}</p><div className="lp-rec-meta"><span><small>CONFIDENCE</small><b>{text(rec, ["confidence"], "Not supplied")}</b></span><span><small>EST. IMPACT</small><b>{text(rec, ["impact", "estimated_impact"], "Not supplied")}</b></span><span><small>RISK</small><b>{text(rec, ["risk", "risk_level"], "Not supplied")}</b></span></div><Button variant="outline" onClick={() => setSelectedRecommendation(rec)}><SearchCheck /> Review evidence</Button></article>)}</div> : <EmptyState icon={ListChecks} title="Your decision queue is empty" copy={connected ? "Run Full Analysis to build a fresh queue from the latest snapshot." : "Connect and synchronize an ESPN league before requesting analysis."} action={workspaceId && <Button onClick={runAnalysis}><Play /> Run Full Analysis</Button>} />}
        </section>}

        {active === "trades" && <section className="lp-view"><div className="lp-view-heading"><div><p className="lp-app-kicker">TRADE LAB</p><h1>Trade opportunities</h1><p>Realistic partners and pitches, generated from analysed opponent rosters.</p></div></div>
          {scope.status === "loading" ? <div className="lp-skeleton-grid"><Skeleton className="lp-skeleton-card" /><Skeleton className="lp-skeleton-card" /><Skeleton className="lp-skeleton-card" /></div>
            : scope.status === "error" ? <EmptyState icon={CircleAlert} title="We couldn't load trades" copy={scope.error ?? "The backend did not respond."} action={<Button variant="outline" onClick={scope.refresh}><RefreshCw /> Try again</Button>} />
            : scope.status === "no-connection" ? <EmptyState icon={Users} title="Connect a league first" copy="Trade Lab compares your roster against every other team in your league. Connect an ESPN league to begin." action={<Button variant="outline" onClick={() => setActive("settings")}>Open settings <ArrowRight /></Button>} />
            : tradeRecommendations.length === 0 ? <EmptyState icon={Users} title="No trade opportunities yet" copy="Trade analysis runs as part of a full analysis. Once it completes, realistic partners and copyable pitches appear here." action={<Button onClick={runAnalysis} disabled={!workspaceId}><Play /> Run analysis</Button>} />
            : <div className="lp-recommendations-grid">{tradeRecommendations.map((item) => <article key={String(item.id)}><div><span>{String(item.kind ?? "trade").toUpperCase()}</span><Badge>{typeof item.confidence === "number" ? `${item.confidence}%` : "—"}</Badge></div><h2>{String(item.title ?? "Trade opportunity")}</h2><p>{String(item.summary ?? "")}</p><Button variant="outline" onClick={() => setSelectedRecommendation(item as Item)}>Review <ArrowRight /></Button></article>)}</div>}
        </section>}

        {active === "alerts" && <section className="lp-view"><div className="lp-view-heading"><div><p className="lp-app-kicker">DEADLINE CENTER</p><h1>Alerts</h1><p>Availability risks and deadlines detected from real league data.</p></div></div>
          {scope.status === "loading" ? <div className="lp-skeleton-grid"><Skeleton className="lp-skeleton-card" /><Skeleton className="lp-skeleton-card" /></div>
            : scope.status === "error" ? <EmptyState icon={CircleAlert} title="We couldn't load alerts" copy={scope.error ?? "The backend did not respond."} action={<Button variant="outline" onClick={scope.refresh}><RefreshCw /> Try again</Button>} />
            : scope.status === "no-connection" ? <EmptyState icon={Bell} title="Connect a league first" copy="Alerts watch your starters for inactive tags, lineup locks and waiver deadlines. Connect an ESPN league to begin." action={<Button variant="outline" onClick={() => setActive("settings")}>Open settings <ArrowRight /></Button>} />
            : alertRecommendations.length === 0 ? <EmptyState icon={Bell} title="No alerts right now" copy="Nothing needs your attention in this league. Availability alerts appear here as soon as the backend reports one." />
            : <div className="lp-recommendations-grid">{alertRecommendations.map((item) => <article key={String(item.id)}><div><span>ALERT</span><Badge>{typeof item.confidence === "number" ? `${item.confidence}%` : "—"}</Badge></div><h2>{String(item.title ?? "Availability alert")}</h2><p>{String(item.summary ?? "")}</p><Button variant="outline" onClick={() => setSelectedRecommendation(item as Item)}>Review <ArrowRight /></Button></article>)}</div>}
        </section>}

        {active === "reports" && <section className="lp-view"><div className="lp-view-heading"><div><p className="lp-app-kicker">LEAGUE INTELLIGENCE</p><h1>Reports</h1><p>Weekly recaps, power rankings, matchup stories, and commissioner-ready copy.</p></div></div>
          {data.reports.length ? <div className="lp-reports-grid">{data.reports.map((report, index) => <article key={text(report, ["id"], String(index))}><div><span><FileText /></span><Badge>{text(report, ["status"], "Ready")}</Badge></div><p className="lp-app-kicker">{text(report, ["kind", "type"], "WEEKLY REPORT")}</p><h2>{text(report, ["title", "name"], "League report")}</h2><p>{text(report, ["summary", "excerpt"], "This report record does not include a summary.")}</p><footer><span><Clock3 /> {dateLabel(text(report, ["created", "created_at", "date"]))}</span><Button variant="outline">Open report <ArrowRight /></Button></footer></article>)}</div> : <EmptyState icon={BookOpen} title="No reports have been generated" copy="Reports will appear after a full analysis successfully completes." />}
        </section>}

        {active === "activity" && <section className="lp-view"><div className="lp-view-heading"><div><p className="lp-app-kicker">LIVE OPERATIONS</p><h1>Activity</h1><p>Queued, running, succeeded, and failed jobs from the backend.</p></div><Button variant="outline" onClick={() => loadBootstrap()} disabled={refreshing}><RefreshCw className={refreshing ? "lp-spin" : ""} /> Refresh status</Button></div>
          {Object.keys(currentJob).length > 0 && <div className="lp-live-job"><div><span><Bot /></span><div className="lp-live-job-copy"><small>CURRENT ANALYSIS JOB</small><h2>{text(currentJob, ["kind", "type"], "Full analysis")}</h2><b>{text(currentJob, ["message", "summary"], "The backend is reporting live job state.")}</b></div><StatusBadge status={currentStatus || "Queued"} /></div><Progress value={currentStatus === "succeeded" ? 100 : currentStatus === "running" ? 62 : currentStatus === "failed" ? 100 : 18} /><footer><span>Queued</span><span>Running</span><span>Complete</span></footer></div>}
          {data.jobs.length ? <div className="lp-activity-list">{data.jobs.map((job, index) => <article key={text(job, ["id"], String(index))}><span className={text(job, ["status", "state"]).toLowerCase()}><Activity /></span><p><b>{text(job, ["kind", "type", "title"], "Analysis job")}</b><small>{text(job, ["message", "summary"], "No additional job detail was supplied.")}</small></p><StatusBadge status={text(job, ["status", "state"], "Unknown")} /><time>{dateLabel(text(job, ["updated", "updated_at", "created", "created_at"]))}</time></article>)}</div> : <EmptyState icon={Activity} title="No job history yet" copy="Run Full Analysis to create the first live activity record." action={workspaceId && <Button onClick={runAnalysis}><Play /> Run Full Analysis</Button>} />}
        </section>}

        {active === "settings" && <section className="lp-view"><div className="lp-view-heading"><div><p className="lp-app-kicker">ACCOUNT & WORKSPACE</p><h1>Settings</h1><p>Security, account identity, notification readiness, and backend connection.</p></div></div><div className="lp-settings-grid">
          <article className="lp-panel"><div className="lp-panel-head"><div><p className="lp-app-kicker">ACCOUNT</p><h2>Your identity</h2></div></div><div className="lp-account-profile"><span>{userName.slice(0, 1).toUpperCase()}</span><p><b>{userName}</b><small>{userEmail || "Email unavailable"}</small></p></div><Button variant="outline" onClick={signOut}><LogOut /> Sign out</Button></article>
          <article className="lp-panel"><div className="lp-panel-head"><div><p className="lp-app-kicker">NOTIFICATIONS</p><h2>Delivery controls</h2></div></div><div className="lp-setting-row"><p><b>Analysis completion alerts</b><small>Requires a settings update endpoint.</small></p><Switch disabled aria-label="Analysis completion alerts" /></div><div className="lp-setting-row"><p><b>Weekly report delivery</b><small>Only sends to a channel you configure.</small></p><Switch disabled aria-label="Weekly report delivery" /></div><p className="lp-settings-honesty"><CircleAlert /> Disabled because a settings-write endpoint was not included in the supplied backend contract.</p></article>
          <article className="lp-panel lp-security-panel"><div className="lp-panel-head"><div><p className="lp-app-kicker">SECURITY</p><h2>Protected by design</h2></div><ShieldCheck /></div><ul><li><Check /> Session stored in a secure HttpOnly cookie</li><li><Check /> Superuser credentials never enter the browser</li><li><Check /> ESPN cookies and encryption keys stay server-side</li><li><Check /> Web and mobile use the same backend records</li></ul></article>
          <article className="lp-panel"><div className="lp-panel-head"><div><p className="lp-app-kicker">BACKEND</p><h2>Shared source of truth</h2></div></div><div className="lp-backend-card"><span><i /> LIVE</span><b>leaguepilot-ai.cloudpod.pro</b><p>PocketBase powers authentication and synchronized records for both web and mobile.</p></div></article>
        </div></section>}
      </div>

      <nav className="lp-mobile-nav" aria-label="Dashboard sections">
        {/* Eight sections do not fit a bottom bar. The four highest-frequency ones stay
            reachable in one tap; the rest live behind More, which opens the same sidebar
            used on desktop so there is only one navigation model to maintain. */}
        {navigation.slice(0, 4).map(({ id, short, icon: Icon }) => (
          <button
            key={id}
            type="button"
            className={active === id ? "active" : ""}
            aria-current={active === id ? "page" : undefined}
            onClick={() => setActive(id)}
          >
            <Icon aria-hidden /><span>{short}</span>
          </button>
        ))}
        <SidebarTrigger className="lp-mobile-more" aria-label="More sections">
          <Menu aria-hidden /><span>More</span>
        </SidebarTrigger>
      </nav>
    </SidebarInset>

    <Dialog open={Boolean(selectedRecommendation)} onOpenChange={(open) => !open && setSelectedRecommendation(null)}><DialogContent className="lp-evidence-dialog"><DialogHeader><Badge>RECOMMENDATION EVIDENCE</Badge><DialogTitle>{selectedRecommendation ? text(selectedRecommendation, ["title", "headline", "recommendation"], "Recommendation") : ""}</DialogTitle><DialogDescription>Read-only evidence from the current PocketBase record.</DialogDescription></DialogHeader>{selectedRecommendation && <div className="lp-evidence-content"><div className="lp-rec-meta"><span><small>CONFIDENCE</small><b>{text(selectedRecommendation, ["confidence"], "Not supplied")}</b></span><span><small>EST. IMPACT</small><b>{text(selectedRecommendation, ["impact", "estimated_impact"], "Not supplied")}</b></span><span><small>RISK</small><b>{text(selectedRecommendation, ["risk", "risk_level"], "Not supplied")}</b></span></div><section><h3>Why this is recommended</h3><p>{text(selectedRecommendation, ["reason", "summary", "description"], "The backend record did not supply an explanation.")}</p></section><section><h3>Evidence</h3><p>{text(selectedRecommendation, ["evidence", "evidence_summary"], "No evidence summary was supplied in this record.")}</p></section><p className="lp-settings-honesty"><ShieldCheck /> Review only. No ESPN action is submitted from this dialog.</p></div>}</DialogContent></Dialog>
    <Toaster position="top-right" richColors />
  </SidebarProvider>;
}
