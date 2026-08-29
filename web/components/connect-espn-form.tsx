"use client";

import { useRef, useState } from "react";
import { ExternalLink, Loader2, ShieldCheck } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";

/**
 * First-league onboarding.
 *
 * Security notes that drive the shape of this component:
 * - ESPN cookies are held in refs, not React state, so they are never part of a render
 *   tree, a devtools snapshot, or a serialized component payload.
 * - Both fields are cleared immediately after the request settles — success or failure —
 *   so they do not linger in memory or in the DOM.
 * - autoComplete is off and the inputs are type=password so browsers do not offer to
 *   save them.
 * - Nothing is echoed back: the server never returns credentials, and this form never
 *   re-displays what was submitted.
 */
export function ConnectEspnForm({
  workspaceId,
  onConnected,
}: {
  workspaceId: string;
  onConnected: () => void;
}) {
  const [leagueId, setLeagueId] = useState("");
  const [teamId, setTeamId] = useState("");
  const [season, setSeason] = useState(String(new Date().getFullYear()));
  const [isPublic, setIsPublic] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Deliberately refs, not state — see the note above.
  const espnS2Ref = useRef<HTMLInputElement>(null);
  const swidRef = useRef<HTMLInputElement>(null);

  function clearCredentials() {
    if (espnS2Ref.current) espnS2Ref.current.value = "";
    if (swidRef.current) swidRef.current.value = "";
  }

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy) return; // guards double submission
    setError(null);
    setBusy(true);

    const espn_s2 = espnS2Ref.current?.value.trim() ?? "";
    const swid = swidRef.current?.value.trim() ?? "";

    try {
      const response = await fetch(
        `/api/leaguepilot/workspaces/${workspaceId}/connections/espn`,
        {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            league_id: leagueId,
            team_id: teamId,
            season,
            is_public: isPublic,
            ...(espn_s2 && swid ? { espn_s2, swid } : {}),
          }),
        },
      );
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(payload.message || "We couldn't save that league.");
      onConnected();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "We couldn't save that league.");
    } finally {
      // Cleared on every path, including failure.
      clearCredentials();
      setBusy(false);
    }
  }

  return (
    <form className="lp-connect-form" onSubmit={submit} noValidate>
      <div className="lp-connect-row">
        <div>
          <Label htmlFor="lp-league-id">ESPN league ID</Label>
          <Input
            id="lp-league-id" inputMode="numeric" required value={leagueId}
            onChange={(e) => setLeagueId(e.target.value)}
            placeholder="e.g. 1234567"
            aria-describedby="lp-league-hint"
          />
          <small id="lp-league-hint">
            In your ESPN league URL: <code>?leagueId=</code>
          </small>
        </div>
        <div>
          <Label htmlFor="lp-team-id">Your team ID</Label>
          <Input
            id="lp-team-id" inputMode="numeric" required value={teamId}
            onChange={(e) => setTeamId(e.target.value)}
            placeholder="e.g. 4"
            aria-describedby="lp-team-hint"
          />
          <small id="lp-team-hint">
            In your team URL: <code>?teamId=</code>
          </small>
        </div>
        <div>
          <Label htmlFor="lp-season">Season</Label>
          <Input
            id="lp-season" inputMode="numeric" required value={season}
            onChange={(e) => setSeason(e.target.value)}
          />
          <small>Between 2019 and 2100.</small>
        </div>
      </div>

      <div className="lp-connect-public">
        <Switch id="lp-public" checked={isPublic} onCheckedChange={setIsPublic} />
        <Label htmlFor="lp-public">
          This league is public
          <small>Public leagues need no cookies. Leave off for a private league.</small>
        </Label>
      </div>

      {!isPublic && (
        <div className="lp-connect-private">
          <p className="lp-connect-note">
            <ShieldCheck aria-hidden />
            <span>
              Private leagues need two ESPN cookies. They are sent once, encrypted on the
              server, and never shown again. LEAGUEPILOT reads your league — it never
              changes your lineup, waivers or trades.
            </span>
          </p>
          <div className="lp-connect-row">
            <div>
              <Label htmlFor="lp-espn-s2">espn_s2 cookie</Label>
              <Input id="lp-espn-s2" ref={espnS2Ref} type="password" autoComplete="off" spellCheck={false} />
            </div>
            <div>
              <Label htmlFor="lp-swid">SWID cookie</Label>
              <Input id="lp-swid" ref={swidRef} type="password" autoComplete="off" spellCheck={false} placeholder="{...}" />
            </div>
          </div>
          <a
            className="lp-connect-help"
            href="https://support.espn.com/hc/en-us/articles/360000064451"
            target="_blank" rel="noreferrer noopener"
          >
            Where do I find these? <ExternalLink aria-hidden />
          </a>
        </div>
      )}

      {error && <p className="lp-connect-error" role="alert">{error}</p>}

      <Button type="submit" disabled={busy || !leagueId || !teamId || !season}>
        {busy ? <><Loader2 className="lp-spin" aria-hidden /> Connecting…</> : "Connect league"}
      </Button>
      <p className="lp-connect-footnote">
        Saving queues a read-only sync. Your first analysis becomes available once it finishes.
      </p>
    </form>
  );
}
