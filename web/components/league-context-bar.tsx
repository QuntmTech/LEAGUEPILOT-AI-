"use client";

import { AlertTriangle, Loader2, Play, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import type { Connection, JobRun } from "@/lib/leaguepilot-client";

/**
 * Global league context bar.
 *
 * Every value here is rendered only when the backend actually supplied it. Nothing
 * is inferred, defaulted to a plausible-looking number, or filled in from the
 * previous league — an absent field renders an explicit unknown state instead.
 */

function relativeTime(iso?: string): string | null {
  if (!iso) return null;
  const then = Date.parse(iso);
  if (Number.isNaN(then)) return null;
  const seconds = Math.round((Date.now() - then) / 1000);
  if (seconds < 60) return "just now";
  if (seconds < 3_600) return `${Math.floor(seconds / 60)}m ago`;
  if (seconds < 86_400) return `${Math.floor(seconds / 3_600)}h ago`;
  return `${Math.floor(seconds / 86_400)}d ago`;
}

const RUNNING = new Set(["queued", "running"]);

function jobLabel(job: JobRun | null): { text: string; tone: "idle" | "busy" | "bad" } {
  if (!job) return { text: "No analysis yet", tone: "idle" };
  switch (job.status) {
    case "queued":
      return { text: "Analysis queued", tone: "busy" };
    case "running":
      return { text: "Analysis running", tone: "busy" };
    case "succeeded":
      return { text: `Analysis complete ${relativeTime(job.completed_at) ?? ""}`.trim(), tone: "idle" };
    case "failed":
      return { text: "Last analysis failed", tone: "bad" };
    case "cancelled":
      return { text: "Last analysis cancelled", tone: "bad" };
    case "dead-letter":
      return { text: "Analysis needs attention", tone: "bad" };
    default:
      return { text: "Unknown state", tone: "bad" };
  }
}

export function LeagueContextBar({
  workspaceName,
  connections,
  connectionId,
  connection,
  latestJob,
  busy,
  onSelect,
  onSync,
  onRunAnalysis,
}: {
  workspaceName: string | null;
  connections: Connection[];
  connectionId: string | null;
  connection: Connection | null;
  latestJob: JobRun | null;
  busy: boolean;
  onSelect: (id: string) => void;
  onSync: () => void;
  onRunAnalysis: () => void;
}) {
  const job = jobLabel(latestJob);
  const synced = relativeTime(connection?.last_synced_at);
  const analysisBusy = busy || (latestJob ? RUNNING.has(latestJob.status) : false);

  return (
    <div className="lp-context-bar" role="region" aria-label="League context">
      <div className="lp-context-identity">
        <small>WORKSPACE</small>
        <b>{workspaceName ?? "—"}</b>
      </div>

      <div className="lp-context-league">
        <small>LEAGUE</small>
        {connections.length === 0 ? (
          <b className="lp-context-muted">No league connected</b>
        ) : connections.length === 1 ? (
          <b>{connection?.label || connection?.league_id || "Connected league"}</b>
        ) : (
          <Select value={connectionId ?? undefined} onValueChange={onSelect}>
            <SelectTrigger className="lp-league-select" aria-label="Select league">
              <SelectValue placeholder="Select a league" />
            </SelectTrigger>
            <SelectContent>
              {connections.map((item) => (
                <SelectItem key={item.id} value={item.id}>
                  {item.label || item.league_id || item.id}
                  {item.season ? ` · ${item.season}` : ""}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        )}
      </div>

      <div className="lp-context-facts">
        <span>
          <small>SEASON</small>
          <b>{connection?.season ?? "—"}</b>
        </span>
        <span>
          <small>CONNECTION</small>
          <b className={connection?.status === "active" ? "lp-ok" : "lp-context-muted"}>
            {connection?.status ?? "Not connected"}
          </b>
        </span>
        <span>
          <small>LAST SYNC</small>
          <b>{synced ?? "Never"}</b>
        </span>
        <span>
          <small>ANALYSIS</small>
          <b className={job.tone === "bad" ? "lp-bad" : undefined}>
            {job.tone === "bad" && <AlertTriangle aria-hidden />} {job.text}
          </b>
        </span>
      </div>

      <div className="lp-context-actions">
        <Button variant="outline" onClick={onSync} disabled={!connectionId || busy}>
          <RefreshCw aria-hidden /> Sync
        </Button>
        <Button onClick={onRunAnalysis} disabled={!connectionId || analysisBusy}>
          {analysisBusy ? <Loader2 className="lp-spin" aria-hidden /> : <Play aria-hidden />}
          {analysisBusy ? "Running…" : "Run Analysis"}
        </Button>
      </div>

      {connection?.last_error ? (
        <p className="lp-context-error" role="status">
          <AlertTriangle aria-hidden /> Last sync reported a problem. Open Settings for details.
        </p>
      ) : null}
    </div>
  );
}
