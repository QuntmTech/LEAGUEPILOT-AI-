"use client";

/**
 * Client half of the realtime pipeline.
 *
 * Connects to the same-origin SSE proxy — never to PocketBase directly, because the
 * bearer token lives in an HttpOnly cookie the browser cannot read.
 *
 * Handles: bounded-backoff reconnect, duplicate suppression, session expiry (a 401
 * stops retrying rather than hammering the server), and cleanup on teardown.
 */

export type RealtimeEvent = {
  collection: string;
  action: "create" | "update" | "delete";
  recordId: string;
};

type Handler = (event: RealtimeEvent) => void;

const WATCHED = new Set([
  "espn_connections",
  "job_runs",
  "recommendations",
  "reports",
  "league_snapshots",
  "audit_events",
]);

const BASE_DELAY_MS = 1_000;
const MAX_DELAY_MS = 30_000;
/** Remember recent event ids so a reconnect replaying a frame does not double-refetch. */
const DEDUPE_LIMIT = 200;

export function connectRealtime(onEvent: Handler): () => void {
  let source: EventSource | null = null;
  let attempt = 0;
  let timer: ReturnType<typeof setTimeout> | null = null;
  let stopped = false;
  const seen = new Set<string>();
  const order: string[] = [];

  function remember(key: string): boolean {
    if (seen.has(key)) return false;
    seen.add(key);
    order.push(key);
    if (order.length > DEDUPE_LIMIT) {
      const oldest = order.shift();
      if (oldest) seen.delete(oldest);
    }
    return true;
  }

  function scheduleReconnect() {
    if (stopped) return;
    // Exponential backoff with jitter, capped. Jitter avoids a thundering herd when
    // many tabs reconnect after the same outage.
    const delay = Math.min(BASE_DELAY_MS * 2 ** attempt, MAX_DELAY_MS);
    const jittered = delay * (0.5 + Math.random() * 0.5);
    attempt += 1;
    timer = setTimeout(open, jittered);
  }

  function open() {
    if (stopped) return;
    source = new EventSource("/api/leaguepilot/realtime");

    source.onopen = () => {
      attempt = 0; // a clean open resets backoff
    };

    source.onmessage = (message) => {
      if (!message.data) return;
      let parsed: unknown;
      try {
        parsed = JSON.parse(message.data);
      } catch {
        return; // PB_CONNECT and heartbeats are not record events
      }
      const payload = parsed as {
        action?: string;
        record?: { id?: string; collectionName?: string };
      };
      const collection = payload.record?.collectionName;
      const recordId = payload.record?.id;
      const action = payload.action;
      if (!collection || !recordId || !action) return;
      if (!WATCHED.has(collection)) return;
      if (action !== "create" && action !== "update" && action !== "delete") return;
      if (!remember(`${collection}:${recordId}:${action}:${message.lastEventId}`)) return;
      onEvent({ collection, action, recordId });
    };

    source.onerror = () => {
      source?.close();
      source = null;
      // EventSource cannot read the status code. The session route is cheap and
      // authoritative: if the session is gone, stop rather than reconnect forever.
      void fetch("/api/auth/session")
        .then((r) => {
          if (r.status === 401) {
            stopped = true;
            return;
          }
          scheduleReconnect();
        })
        .catch(() => scheduleReconnect());
    };
  }

  open();

  return () => {
    stopped = true;
    if (timer) clearTimeout(timer);
    source?.close();
    source = null;
  };
}
