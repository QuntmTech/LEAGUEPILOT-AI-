"use client";

import { useMemo, useRef, useState } from "react";
import { ArrowLeft, Check, ExternalLink, Loader2, ShieldCheck } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { parseEspnLeagueLink } from "@/lib/espn-league-url";

/**
 * Consumer onboarding: paste league link → connect securely → confirm team.
 *
 * No numeric team ID is ever requested. The server reads the league's teams from ESPN and
 * either identifies the user's team from their signed-in ESPN identity, or shows a list to
 * tap. A team ID parsed out of a pasted team URL is used silently when present.
 *
 * Credential handling, unchanged from the previous form:
 * - ESPN values live in refs, never React state, so they never enter a render tree.
 * - Cleared in a finally block, so a failed attempt clears them too.
 * - type=password, autoComplete off, never echoed back by any response.
 */
type Team = { team_id: number; name: string };
type Step = "details" | "choose-team";

export function ConnectEspnForm({
  workspaceId,
  onConnected,
}: {
  workspaceId: string;
  onConnected: () => void;
}) {
  const [link, setLink] = useState("");
  const [season, setSeason] = useState(String(new Date().getFullYear()));
  const [isPublic, setIsPublic] = useState(false);
  const [step, setStep] = useState<Step>("details");
  const [teams, setTeams] = useState<Team[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const espnS2Ref = useRef<HTMLInputElement>(null);
  const swidRef = useRef<HTMLInputElement>(null);
  // Held across the two steps so the user is not asked for credentials twice. Cleared as
  // soon as the connection is saved or the flow fails.
  const heldCredentials = useRef<{ espn_s2: string; swid: string } | null>(null);

  const parsed = useMemo(() => parseEspnLeagueLink(link), [link]);
  const canSubmit = parsed.leagueId !== null && season.trim() !== "" && !busy;

  function clearCredentials() {
    if (espnS2Ref.current) espnS2Ref.current.value = "";
    if (swidRef.current) swidRef.current.value = "";
    heldCredentials.current = null;
  }

  /** Step 1 → find the league's teams. */
  async function discover(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy || parsed.leagueId === null) return;
    setBusy(true);
    setError(null);

    const espn_s2 = espnS2Ref.current?.value.trim() ?? "";
    const swid = swidRef.current?.value.trim() ?? "";
    const credentials = espn_s2 && swid ? { espn_s2, swid } : null;

    try {
      const response = await fetch("/api/leaguepilot/espn/discover", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          league_id: parsed.leagueId,
          season: Number(season),
          ...(credentials ?? {}),
        }),
      });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(payload.message || "We couldn't reach that league.");

      heldCredentials.current = credentials;
      const found: Team[] = Array.isArray(payload.teams) ? payload.teams : [];

      // A team id from a pasted team URL wins; otherwise use ESPN's identity match.
      const preselected =
        (parsed.teamId && found.some((t) => t.team_id === parsed.teamId) ? parsed.teamId : null) ??
        (typeof payload.matched_team_id === "number" ? payload.matched_team_id : null);

      if (preselected !== null) {
        await save(preselected);
        return;
      }
      setTeams(found);
      setStep("choose-team");
    } catch (cause) {
      clearCredentials();
      setError(cause instanceof Error ? cause.message : "We couldn't reach that league.");
    } finally {
      setBusy(false);
    }
  }

  /** Step 2 → persist the connection with the resolved team. */
  async function save(teamId: number) {
    setBusy(true);
    setError(null);
    try {
      const response = await fetch(
        `/api/leaguepilot/workspaces/${workspaceId}/connections/espn`,
        {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            league_id: parsed.leagueId,
            team_id: teamId,
            season: Number(season),
            is_public: isPublic,
            ...(heldCredentials.current ?? {}),
          }),
        },
      );
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(payload.message || "We couldn't save that league.");
      onConnected();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "We couldn't save that league.");
      setStep("choose-team");
    } finally {
      clearCredentials();
      setBusy(false);
    }
  }

  if (step === "choose-team") {
    return (
      <div className="lp-connect-form">
        <div className="lp-choose-head">
          <div>
            <p className="lp-app-kicker">ALMOST THERE</p>
            <h3>Which team is yours?</h3>
            <p>We found {teams.length} teams in this league. Tap yours to finish.</p>
          </div>
          <Button
            variant="ghost" type="button" disabled={busy}
            onClick={() => { setStep("details"); setError(null); }}
          >
            <ArrowLeft aria-hidden /> Back
          </Button>
        </div>
        {error && <p className="lp-connect-error" role="alert">{error}</p>}
        <ul className="lp-team-picker">
          {teams.map((team) => (
            <li key={team.team_id}>
              <button type="button" disabled={busy} onClick={() => void save(team.team_id)}>
                <span aria-hidden>{team.name.slice(0, 1).toUpperCase()}</span>
                <b>{team.name}</b>
                {busy ? <Loader2 className="lp-spin" aria-hidden /> : <Check aria-hidden />}
              </button>
            </li>
          ))}
        </ul>
      </div>
    );
  }

  return (
    <form className="lp-connect-form" onSubmit={discover} noValidate>
      <div className="lp-connect-primary">
        <Label htmlFor="lp-league-link">Your ESPN league link</Label>
        <Input
          id="lp-league-link" value={link} onChange={(e) => setLink(e.target.value)}
          placeholder="https://fantasy.espn.com/football/league?leagueId=…"
          aria-describedby="lp-link-hint" autoComplete="off" required
        />
        <small id="lp-link-hint">
          {parsed.leagueId !== null
            ? `League ${parsed.leagueId} detected${parsed.teamId ? ` · team ${parsed.teamId}` : ""}.`
            : "Paste the link from your ESPN league page, or type the league ID."}
        </small>
      </div>

      <div className="lp-connect-row two">
        <div>
          <Label htmlFor="lp-season">Season</Label>
          <Input id="lp-season" inputMode="numeric" value={season}
                 onChange={(e) => setSeason(e.target.value)} required />
        </div>
        <div className="lp-connect-public">
          <Switch id="lp-public" checked={isPublic} onCheckedChange={setIsPublic} />
          <Label htmlFor="lp-public">
            This league is public
            <small>Leave off for a private league.</small>
          </Label>
        </div>
      </div>

      {!isPublic && (
        <div className="lp-connect-private">
          <p className="lp-connect-note">
            <ShieldCheck aria-hidden />
            <span>
              Private leagues need two values from your signed-in ESPN session. They are sent
              once, encrypted on our server, and never shown again. LEAGUEPILOT only reads
              your league — it never changes your lineup, waivers or trades.
            </span>
          </p>
          <div className="lp-connect-row two">
            <div>
              <Label htmlFor="lp-espn-s2">espn_s2</Label>
              <Input id="lp-espn-s2" ref={espnS2Ref} type="password" autoComplete="off" spellCheck={false} />
            </div>
            <div>
              <Label htmlFor="lp-swid">SWID</Label>
              <Input id="lp-swid" ref={swidRef} type="password" autoComplete="off" spellCheck={false} placeholder="{…}" />
            </div>
          </div>
          <a className="lp-connect-help" href="https://support.espn.com/hc/en-us/articles/360000064451"
             target="_blank" rel="noreferrer noopener">
            Where do I find these? <ExternalLink aria-hidden />
          </a>
        </div>
      )}

      {error && <p className="lp-connect-error" role="alert">{error}</p>}

      <Button type="submit" disabled={!canSubmit}>
        {busy ? <><Loader2 className="lp-spin" aria-hidden /> Finding your league…</> : "Continue"}
      </Button>
      <p className="lp-connect-footnote">
        We read your league to find your team. Nothing is changed on ESPN.
      </p>
    </form>
  );
}
