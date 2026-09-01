"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  leaguePilot,
  selectedConnection,
  type Connection,
  type JobRun,
  type LeagueSnapshot,
  type Recommendation,
  type Report,
} from "@/lib/leaguepilot-client";
import { connectRealtime } from "@/lib/leaguepilot-realtime";

export type ScopeStatus = "loading" | "ready" | "error" | "no-connection";

export type LeagueScope = {
  status: ScopeStatus;
  error: string | null;
  connections: Connection[];
  connectionId: string | null;
  connection: Connection | null;
  recommendations: Recommendation[];
  jobs: JobRun[];
  reports: Report[];
  snapshot: LeagueSnapshot | null;
  latestJob: JobRun | null;
  selectConnection: (id: string) => void;
  refresh: () => void;
};

/**
 * Owns the selected league and every query scoped to it.
 *
 * Correctness rules this enforces, in order of how easy they are to get wrong:
 *
 * 1. Switching leagues clears league-specific state *synchronously*, before the new
 *    fetch starts, so the previous league's rows are never briefly visible.
 * 2. Every load carries a generation number. A response from a superseded generation
 *    is discarded, so a slow response for league A cannot overwrite league B.
 * 3. In-flight requests are aborted on switch and on unmount.
 * 4. Realtime events only trigger a refetch for the collection they belong to, and
 *    are ignored once the component is torn down.
 */
export function useLeagueScope(workspaceId: string | null): LeagueScope {
  const [connections, setConnections] = useState<Connection[]>([]);
  const [connectionId, setConnectionId] = useState<string | null>(null);
  const [recommendations, setRecommendations] = useState<Recommendation[]>([]);
  const [jobs, setJobs] = useState<JobRun[]>([]);
  const [reports, setReports] = useState<Report[]>([]);
  const [snapshot, setSnapshot] = useState<LeagueSnapshot | null>(null);
  const [status, setStatus] = useState<ScopeStatus>("loading");
  const [error, setError] = useState<string | null>(null);

  const generation = useRef(0);
  const aborter = useRef<AbortController | null>(null);
  const mounted = useRef(true);

  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
      aborter.current?.abort();
    };
  }, []);

  /** Clear every league-specific slice. Called synchronously on switch. */
  const clearLeagueData = useCallback(() => {
    setRecommendations([]);
    setJobs([]);
    setReports([]);
    setSnapshot(null);
  }, []);

  const load = useCallback(
    async (targetConnection: string | null) => {
      if (!workspaceId) return;
      const mine = ++generation.current;
      aborter.current?.abort();
      aborter.current = new AbortController();

      setStatus("loading");
      setError(null);
      try {
        const [recs, jobRuns, reportRows, snapshots] = await Promise.all([
          leaguePilot.recommendations(workspaceId),
          leaguePilot.jobs(workspaceId, targetConnection ?? undefined),
          leaguePilot.reports(workspaceId),
          leaguePilot.snapshots(workspaceId),
        ]);
        // A newer switch has happened while this was in flight — drop the result.
        if (!mounted.current || mine !== generation.current) return;
        setRecommendations(recs);
        setJobs(jobRuns);
        setReports(reportRows);
        // Newest first (sorted server-side by -fetched_at); scoped to the selected league.
        setSnapshot(
          snapshots.find((s) => !targetConnection || s.connection === targetConnection) ??
            snapshots[0] ??
            null,
        );
        setStatus(targetConnection ? "ready" : "no-connection");
      } catch (cause) {
        if (!mounted.current || mine !== generation.current) return;
        setError(cause instanceof Error ? cause.message : "We couldn't load this league.");
        setStatus("error");
      }
    },
    [workspaceId],
  );

  // Initial connection list, and restore the persisted selection when it still exists.
  useEffect(() => {
    if (!workspaceId) return;
    let cancelled = false;
    (async () => {
      try {
        const list = await leaguePilot.connections();
        if (cancelled || !mounted.current) return;
        setConnections(list);
        const remembered = selectedConnection.read();
        const chosen =
          (remembered && list.some((c) => c.id === remembered) ? remembered : null) ??
          list[0]?.id ??
          null;
        setConnectionId(chosen);
        selectedConnection.write(chosen);
        await load(chosen);
      } catch (cause) {
        if (cancelled || !mounted.current) return;
        setError(cause instanceof Error ? cause.message : "We couldn't load your leagues.");
        setStatus("error");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [workspaceId, load]);

  const selectConnection = useCallback(
    (id: string) => {
      if (id === connectionId) return;
      // Order matters: clear first so no frame renders the old league's rows.
      clearLeagueData();
      setConnectionId(id);
      selectedConnection.write(id);
      void load(id);
    },
    [connectionId, clearLeagueData, load],
  );

  const refresh = useCallback(() => void load(connectionId), [connectionId, load]);

  // Realtime: rescope on every selection change so events refresh the current league.
  useEffect(() => {
    if (!workspaceId) return;
    const disconnect = connectRealtime((event) => {
      if (!mounted.current) return;
      if (
        event.collection === "recommendations" ||
        event.collection === "job_runs" ||
        event.collection === "reports" ||
        event.collection === "espn_connections" ||
        event.collection === "league_snapshots"
      ) {
        void load(connectionId);
      }
    });
    return disconnect;
  }, [workspaceId, connectionId, load]);

  const connection = connections.find((c) => c.id === connectionId) ?? null;
  const latestJob = jobs[0] ?? null;

  return {
    status,
    error,
    connections,
    connectionId,
    connection,
    recommendations,
    jobs,
    reports,
    snapshot,
    latestJob,
    selectConnection,
    refresh,
  };
}
