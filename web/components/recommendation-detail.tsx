"use client";

import { useState } from "react";
import { ArrowRight, Check, Copy, ShieldCheck, TriangleAlert } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import type {
  LineupPayload,
  Recommendation,
  TradePayload,
  WaiverPayload,
} from "@/lib/leaguepilot-client";

/**
 * Recommendation detail.
 *
 * Renders only fields the backend supplied — an absent value shows an explicit dash, never
 * a filled-in guess. Every variant states plainly that LEAGUEPILOT does not execute the
 * move on ESPN; approving records a human decision and nothing more.
 */

function Num({ value, suffix = "" }: { value?: number; suffix?: string }) {
  if (value == null || Number.isNaN(value)) return <b className="lp-unknown">—</b>;
  return <b>{Math.round(value * 100) / 100}{suffix}</b>;
}

function Evidence({ source, risks }: { source?: string; risks?: string[] }) {
  return (
    <div className="lp-rec-evidence">
      <p>
        <small>EVIDENCE</small>
        <b>{source ? source.replace(/_/g, " ") : "Not reported"}</b>
      </p>
      <p>
        <small>RISK</small>
        {risks && risks.length > 0 ? (
          <span className="lp-risk-flags">
            {risks.map((r) => (
              <Badge key={r} className="lp-risk">
                <TriangleAlert aria-hidden /> {r.replace(/_/g, " ")}
              </Badge>
            ))}
          </span>
        ) : (
          <b>None reported</b>
        )}
      </p>
    </div>
  );
}

function Swap({
  inLabel, inName, inValue, outLabel, outName, outValue,
}: {
  inLabel: string; inName?: string; inValue?: number;
  outLabel: string; outName?: string; outValue?: number;
}) {
  const delta =
    inValue != null && outValue != null ? Math.round((inValue - outValue) * 100) / 100 : null;
  return (
    <div className="lp-swap">
      <div className="lp-swap-side">
        <small>{inLabel}</small>
        <b>{inName ?? "—"}</b>
        <span>proj <Num value={inValue} /></span>
      </div>
      <ArrowRight aria-hidden />
      <div className="lp-swap-side out">
        <small>{outLabel}</small>
        <b>{outName ?? "—"}</b>
        <span>proj <Num value={outValue} /></span>
      </div>
      {delta !== null && (
        <div className={`lp-swap-delta ${delta >= 0 ? "up" : "down"}`}>
          <small>PROJECTED CHANGE</small>
          <b>{delta >= 0 ? "+" : ""}{delta}</b>
        </div>
      )}
    </div>
  );
}

export function RecommendationDetail({
  recommendation,
  onReview,
  reviewing,
}: {
  recommendation: Recommendation;
  onReview?: (decision: "approved" | "dismissed") => void;
  reviewing?: boolean;
}) {
  const [copied, setCopied] = useState(false);
  const payload = (recommendation.payload ?? {}) as Record<string, unknown>;
  const kind = recommendation.kind;

  async function copyPitch(text: string) {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 2000);
    } catch {
      /* clipboard unavailable — the text stays selectable on screen */
    }
  }

  return (
    <div className="lp-rec-detail">
      <div className="lp-rec-detail-head">
        <div>
          <p className="lp-app-kicker">{kind.replace(/-/g, " ").toUpperCase()}</p>
          <h2>{recommendation.title}</h2>
          <p className="lp-rec-summary">{recommendation.summary}</p>
        </div>
        <div className="lp-rec-scores">
          <span><small>CONFIDENCE</small><Num value={recommendation.confidence} suffix="%" /></span>
          <span><small>IMPACT</small><Num value={recommendation.impact_points} /></span>
        </div>
      </div>

      {kind === "lineup" && (() => {
        const p = payload as LineupPayload;
        return (
          <>
            <Swap
              inLabel="START" inName={p.start_player} inValue={p.start_value}
              outLabel="BENCH" outName={p.sit_player} outValue={p.sit_value}
            />
            <Evidence source={p.evidence_source} risks={p.risk_flags} />
          </>
        );
      })()}

      {kind === "waiver" && (() => {
        const p = payload as WaiverPayload;
        return (
          <>
            <Swap
              inLabel="ADD" inName={p.add_player} inValue={p.add_value}
              outLabel="DROP" outName={p.drop_player} outValue={p.drop_value}
            />
            {p.suggested_faab_percent != null && (
              <p className="lp-faab">
                <small>SUGGESTED FAAB</small>
                <b>{p.suggested_faab_percent}%</b> of remaining budget
              </p>
            )}
            <Evidence source={p.evidence_source} risks={p.risk_flags} />
          </>
        );
      })()}

      {kind === "trade" && (() => {
        const p = payload as TradePayload;
        return (
          <>
            <div className="lp-trade-grid">
              <span><small>PARTNER</small><b>{p.partner_team ?? "—"}</b></span>
              <span><small>YOU OFFER</small><b>{p.offer_player ?? "—"}</b></span>
              <span><small>YOU RECEIVE</small><b>{p.target_player ?? "—"}</b></span>
              <span><small>FAIRNESS</small><Num value={p.fairness_score} /></span>
              <span><small>MUTUAL FIT</small><Num value={p.mutual_fit_score} /></span>
              <span><small>YOUR GAIN</small><Num value={p.my_estimated_lineup_gain} /></span>
              <span><small>THEIR GAIN</small><Num value={p.partner_estimated_lineup_gain} /></span>
            </div>
            {p.copy_paste_pitch && (
              <div className="lp-pitch">
                <div className="lp-pitch-head">
                  <small>COPYABLE PITCH</small>
                  <Button variant="outline" size="sm" onClick={() => void copyPitch(p.copy_paste_pitch!)}>
                    {copied ? <><Check aria-hidden /> Copied</> : <><Copy aria-hidden /> Copy</>}
                  </Button>
                </div>
                <p>{p.copy_paste_pitch}</p>
              </div>
            )}
            <Evidence source={p.evidence_source} risks={p.risk_flags} />
          </>
        );
      })()}

      <p className="lp-no-execute">
        <ShieldCheck aria-hidden />
        LEAGUEPILOT never changes your ESPN team. Approving records your decision so you can
        act on it yourself in ESPN.
      </p>

      {recommendation.status === "proposed" && onReview ? (
        <div className="lp-rec-actions">
          <Button onClick={() => onReview("approved")} disabled={reviewing}>
            <Check aria-hidden /> Approve
          </Button>
          <Button variant="outline" onClick={() => onReview("dismissed")} disabled={reviewing}>
            Dismiss
          </Button>
        </div>
      ) : (
        <p className="lp-rec-decided">
          Decision recorded: <b>{recommendation.status}</b>
          {recommendation.reviewed_at ? ` · ${new Date(recommendation.reviewed_at).toLocaleString()}` : ""}
        </p>
      )}
    </div>
  );
}
