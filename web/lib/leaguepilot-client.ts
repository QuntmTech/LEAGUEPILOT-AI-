"use client";

/**
 * Browser-side API layer.
 *
 * Every call goes to a same-origin /api/leaguepilot/* route that attaches the
 * PocketBase bearer token server-side. The browser holds no token, so nothing here
 * ever sends an Authorization header.
 */

export type JobStatus =
  | "queued"
  | "running"
  | "succeeded"
  | "failed"
  | "cancelled"
  | "dead-letter";

/** Terminal states must never be rendered as success. */
export const TERMINAL_FAILURE: readonly JobStatus[] = ["failed", "cancelled", "dead-letter"];

export function isTerminal(status: JobStatus): boolean {
  return status === "succeeded" || TERMINAL_FAILURE.includes(status);
}

export type Connection = {
  id: string;
  workspace: string;
  league_id?: string;
  season?: string;
  label?: string;
  visibility?: string;
  status?: string;
  last_synced_at?: string;
  last_error?: string;
};

export type Recommendation = {
  id: string;
  workspace: string;
  kind: "lineup" | "waiver" | "trade" | "availability-alert";
  title: string;
  summary: string;
  confidence: number;
  impact_points?: number;
  payload?: unknown;
  status: "proposed" | "approved" | "dismissed" | "superseded" | "expired";
  expires_at?: string;
  reviewed_at?: string;
};

export type JobRun = {
  id: string;
  workspace: string;
  connection?: string;
  kind: string;
  status: JobStatus;
  scheduled_for?: string;
  started_at?: string;
  completed_at?: string;
  last_error?: string;
};


/** Normalized league data inside a snapshot payload. Shapes verified against production. */
export type SnapshotTeam = {
  id: number;
  name: string;
  owner?: string;
  wins: number;
  losses: number;
  ties?: number;
  points_for?: number;
  projected_total?: number;
  roster?: SnapshotPlayer[];
};

export type SnapshotPlayer = {
  id?: string;
  name?: string;
  position?: string;
  slot?: string;
  team?: string;
  status?: string;
  projected_points?: number;
};

export type SnapshotMatchup = {
  week: number;
  home_team_id: number;
  away_team_id: number;
  home_score?: number;
  away_score?: number;
  home_projected?: number;
  away_projected?: number;
};

export type SnapshotPayload = {
  league_id?: number;
  league_name?: string;
  season?: string | number;
  week?: number;
  my_team_id?: number;
  scoring_format?: string;
  roster_slots?: string[];
  teams?: SnapshotTeam[];
  matchups?: SnapshotMatchup[];
  free_agents?: SnapshotPlayer[];
  data_quality_warnings?: string[];
};

export type LeagueSnapshot = {
  id: string;
  workspace: string;
  connection?: string;
  week?: number;
  payload?: SnapshotPayload;
  fetched_at?: string;
  content_hash?: string;
};

/** Recommendation payloads differ by kind. Fields verified against production records. */
export type LineupPayload = {
  start_player?: string;
  start_value?: number;
  sit_player?: string;
  sit_value?: number;
  evidence_source?: string;
  execution_capability?: string;
  risk_flags?: string[];
};

export type WaiverPayload = {
  add_player?: string;
  add_value?: number;
  drop_player?: string;
  drop_value?: number;
  suggested_faab_percent?: number;
  evidence_source?: string;
  execution_capability?: string;
  risk_flags?: string[];
};

export type TradePayload = {
  partner_team?: string;
  partner_team_id?: number;
  offer_player?: string;
  target_player?: string;
  fairness_score?: number;
  mutual_fit_score?: number;
  my_estimated_lineup_gain?: number;
  partner_estimated_lineup_gain?: number;
  copy_paste_pitch?: string;
  evidence_source?: string;
  execution_capability?: string;
  risk_flags?: string[];
};

export type Report = {
  id: string;
  week?: number;
  title?: string;
  body_markdown?: string;
  metrics?: Record<string, unknown>;
  narration_mode?: string;
  published_at?: string;
};

export class ApiError extends Error {
  constructor(readonly status: number, message: string) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    ...init,
    headers: { Accept: "application/json", ...(init?.headers ?? {}) },
  });
  const text = await response.text();
  const payload = text ? safeParse(text) : null;
  if (!response.ok) {
    const message =
      payload && typeof payload === "object" && typeof (payload as { message?: unknown }).message === "string"
        ? (payload as { message: string }).message
        : "Something went wrong. Please try again.";
    throw new ApiError(response.status, message);
  }
  return payload as T;
}

function safeParse(text: string): unknown {
  try {
    return JSON.parse(text);
  } catch {
    return { message: text };
  }
}

type ListResult<T> = { items?: T[]; totalItems?: number };

/** Collections are read through the server proxy; sorts are pinned server-side. */
async function list<T>(
  collection: string,
  scope: { workspace?: string; connection?: string; perPage?: number } = {},
): Promise<T[]> {
  const query = new URLSearchParams({ collection });
  if (scope.workspace) query.set("workspace", scope.workspace);
  if (scope.connection) query.set("connection", scope.connection);
  if (scope.perPage) query.set("perPage", String(scope.perPage));
  const result = await request<ListResult<T>>(`/api/leaguepilot/records?${query.toString()}`);
  return result?.items ?? [];
}

export const leaguePilot = {
  session: () => request<{ user?: unknown }>("/api/auth/session"),

  bootstrap: () => request<Record<string, unknown>>("/api/leaguepilot/bootstrap", { method: "POST", body: "{}" }),

  connections: async (): Promise<Connection[]> => {
    const result = await request<ListResult<Connection>>("/api/leaguepilot/connections");
    return result?.items ?? [];
  },

  recommendations: (workspace: string) =>
    list<Recommendation>("recommendations", { workspace, perPage: 100 }),

  reports: (workspace: string) => list<Report>("reports", { workspace, perPage: 50 }),

  jobs: (workspace: string, connection?: string) =>
    list<JobRun>("job_runs", { workspace, connection, perPage: 25 }),

  snapshots: (workspace: string) =>
    list<LeagueSnapshot>("league_snapshots", { workspace, perPage: 10 }),

  /**
   * Records a human decision. The backend rejects anything not currently "proposed",
   * so a duplicate submit returns 400 instead of silently re-reviewing.
   * This never executes the move on ESPN.
   */
  review: (id: string, decision: "approved" | "dismissed") =>
    request<Record<string, unknown>>(`/api/leaguepilot/recommendations/${id}/review`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ decision }),
    }),

  sync: (connectionId: string) =>
    request<Record<string, unknown>>(`/api/leaguepilot/connections/${connectionId}/sync`, {
      method: "POST",
    }),

  analysis: (workspaceId: string, kind = "full", connectionId?: string) =>
    request<Record<string, unknown>>(`/api/leaguepilot/workspaces/${workspaceId}/analysis`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ kind, notify: false, ...(connectionId ? { connection_id: connectionId } : {}) }),
    }),

  logout: () => request<{ ok: boolean }>("/api/auth/logout", { method: "POST" }),
};

const SELECTED_CONNECTION_KEY = "leaguepilot.selectedConnection";

/**
 * The selected league is a per-client display preference, not durable product data —
 * it stays in localStorage and is never written to PocketBase. Only the non-secret
 * record id is stored. Reads are guarded: storage throws in some privacy modes.
 */
export const selectedConnection = {
  read(): string | null {
    try {
      return window.localStorage.getItem(SELECTED_CONNECTION_KEY);
    } catch {
      return null;
    }
  },
  write(id: string | null) {
    try {
      if (id) window.localStorage.setItem(SELECTED_CONNECTION_KEY, id);
      else window.localStorage.removeItem(SELECTED_CONNECTION_KEY);
    } catch {
      /* storage unavailable — selection is best-effort */
    }
  },
};
