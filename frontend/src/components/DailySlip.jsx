import React, { useState } from "react";
import { Copy, ExternalLink, CheckCircle2, AlertCircle, Lock, Calendar, Clock, MapPin, Shield, TrendingUp, Zap } from "lucide-react";
import { toast } from "sonner";

function StatusBadge({ count, status }) {
  const map = {
    won: ["co-tag-pos", "Won"],
    lost: ["co-tag-neg", "Lost"],
    void: ["", "Void"],
    pending: ["co-tag-warn", "Pending"],
  };
  const [cls, label] = map[status] || ["", status];
  if (count === 0) return null;
  return <span className={`co-tag ${cls}`}>{count} {label}</span>;
}

function formatKickoff(iso) {
  if (!iso) return { day: "", time: "" };
  try {
    const d = new Date(iso);
    const now = new Date();
    const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    const tomorrow = new Date(today.getTime() + 24 * 60 * 60 * 1000);
    const matchDay = new Date(d.getFullYear(), d.getMonth(), d.getDate());
    let dayLabel;
    if (matchDay.getTime() === today.getTime()) dayLabel = "Today";
    else if (matchDay.getTime() === tomorrow.getTime()) dayLabel = "Tomorrow";
    else dayLabel = d.toLocaleDateString(undefined, { weekday: "short", month: "short", day: "numeric" });
    const time = d.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit", hour12: false });
    return { day: dayLabel, time };
  } catch {
    return { day: "", time: "" };
  }
}

export default function DailySlip({ slip, locked, onSubscribe }) {
  const [copied, setCopied] = useState(false);
  if (!slip) {
    return (
      <div className="co-card p-12 text-center bg-grid">
        <div className="mx-auto w-14 h-14 rounded-[8px] bg-white/5 border border-white/10 grid place-items-center mb-4">
          <Zap className="w-7 h-7 text-[#48a7ff]" />
        </div>
        <div className="font-mono text-[10px] uppercase tracking-widest text-[#667482] mb-2">Empty slate</div>
        <p className="font-heading text-lg text-[#aeb8c2]">No slip published yet today. Check back soon.</p>
      </div>
    );
  }

  const copyCode = async () => {
    try {
      await navigator.clipboard.writeText(slip.sportybet_code);
      setCopied(true);
      toast.success("SportyBet code copied");
      setTimeout(() => setCopied(false), 2000);
    } catch {
      toast.error("Copy failed");
    }
  };

  const evColor = slip.expected_value > 0 ? "text-[#00ff66]" : "text-[#ff3333]";
  const riskTag = slip.risk_level === "LOW" ? "co-tag-pos" : slip.risk_level === "HIGH" ? "co-tag-neg" : "co-tag-warn";
  const codeReady = !!slip.sportybet_code && slip.sportybet_code !== "LOCKED";
  // Average data_richness across legs — drives the data-quality badge
  const avgRichness = slip.legs && slip.legs.length
    ? slip.legs.reduce((s, l) => s + (l.data_richness || 0), 0) / slip.legs.length
    : 0;
  const dataBadge = avgRichness >= 0.7
    ? { label: "Full Intel", cls: "bg-[#00ff66] text-[#050505]", note: "Real injuries, form & H2H wired in." }
    : avgRichness >= 0.4
      ? { label: "Partial Intel", cls: "bg-[#ffb800] text-[#050505]", note: "Some real form/injuries data — bet smaller." }
      : { label: "Market-Data Only", cls: "bg-[#ff6b35] text-white", note: "Only bookmaker prices were available — no injury/form data. Treat as informational, not professional tipping." };

  return (
    <div className="space-y-4 sm:space-y-5" data-testid="daily-slip">
      <section className="co-glass rounded-[8px] p-5 sm:p-6 overflow-hidden">
        <div className="flex items-start justify-between gap-4">
          <div>
            <div className="font-mono text-[10px] uppercase tracking-widest text-[#667482]">Combined slip</div>
            <div className="font-heading font-black text-3xl sm:text-5xl mt-2 leading-none">
              {slip.combined_odds != null ? slip.combined_odds.toFixed(2) : (slip.combined_odds_range || "Locked")}
            </div>
            <div className="mt-2 text-sm text-[#aeb8c2]">{slip.leg_count} legs selected by the AI ensemble</div>
          </div>
          <div className={`co-tag rounded-[8px] px-3 py-2 font-mono text-[10px] uppercase tracking-widest font-bold ${riskTag}`}>
            {slip.risk_level || "Locked"}
          </div>
        </div>
        <div className="grid grid-cols-3 gap-2 mt-5">
          <div className="co-stat-tile p-3 min-h-0">
            <div className="font-mono text-[9px] uppercase tracking-widest text-[#667482]">Confidence</div>
            <div className="font-mono text-xl mt-2">{slip.combined_confidence ? `${slip.combined_confidence.toFixed(0)}%` : "Locked"}</div>
          </div>
          <div className="co-stat-tile p-3 min-h-0">
            <div className="font-mono text-[9px] uppercase tracking-widest text-[#667482]">EV</div>
            <div className={`font-mono text-xl mt-2 ${evColor}`}>{slip.expected_value != null ? `${slip.expected_value > 0 ? "+" : ""}${(slip.expected_value * 100).toFixed(1)}%` : "Locked"}</div>
          </div>
          <div className="co-stat-tile p-3 min-h-0">
            <div className="font-mono text-[9px] uppercase tracking-widest text-[#667482]">Legs</div>
            <div className="font-mono text-xl mt-2">{slip.leg_count}</div>
          </div>
        </div>
      </section>

      {/* Data-quality badge — hidden when locked */}
      {!locked && (
        <div className="co-card p-4 flex items-center gap-3" data-testid="data-quality-badge">
          <span className="w-10 h-10 rounded-[8px] bg-white/5 border border-white/10 grid place-items-center shrink-0">
            <Shield className="w-5 h-5 text-[#00ff66]" />
          </span>
          <div className="min-w-0">
            <span className={`px-3 py-1 font-mono text-[10px] uppercase tracking-widest font-bold rounded-full ${dataBadge.cls}`}>
            {dataBadge.label}
            </span>
            <div className="text-xs text-[#aeb8c2] leading-snug mt-2">{dataBadge.note}</div>
          </div>
        </div>
      )}

      {/* KPI strip — 2 cols on mobile, 5 on desktop */}
      <div className="hidden sm:grid sm:grid-cols-5 gap-2" data-testid="slip-kpis">
        {[
          ["Legs", slip.leg_count],
          ["Combined Odds", slip.combined_odds != null ? slip.combined_odds.toFixed(2) : (slip.combined_odds_range || "Locked")],
          ["Confidence", slip.combined_confidence ? `${slip.combined_confidence.toFixed(0)}%` : "Locked"],
          ["EV", slip.expected_value != null ? `${slip.expected_value > 0 ? "+" : ""}${(slip.expected_value * 100).toFixed(1)}%` : "Locked"],
          ["Risk", slip.risk_level || "Locked"],
        ].map(([k, v]) => (
          <div key={k} className="co-stat-tile p-4 sm:p-5">
            <div className="text-[10px] font-mono uppercase tracking-widest text-[#667482]">{k}</div>
            <div className={`font-mono text-xl sm:text-2xl mt-1 ${k === "EV" ? evColor : ""}`}>{v}</div>
          </div>
        ))}
      </div>

      {/* SportyBet bar */}
      {codeReady ? (
        <div className="co-soft-band rounded-[8px] p-4 sm:p-5" data-testid="sportybet-bar">
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
            <div className="flex items-center gap-3 sm:gap-4 flex-wrap">
              <div className="px-3 py-1 bg-[#00ff66] text-[#050607] font-mono text-[10px] uppercase tracking-widest font-bold rounded-full">
                SportyBet Code
              </div>
              <code className="font-mono text-2xl sm:text-3xl font-black tracking-[0.2em]" data-testid="sportybet-code">{slip.sportybet_code}</code>
            </div>
            <div className="flex items-center gap-2">
              <button onClick={copyCode} data-testid="copy-code-btn" className="flex-1 sm:flex-none co-secondary-action rounded-[6px] font-mono text-[11px] uppercase tracking-widest px-4 py-3 sm:py-2 inline-flex items-center justify-center gap-2 min-h-[44px]">
                {copied ? <><CheckCircle2 className="w-3.5 h-3.5 text-[#00ff66]"/> Copied</> : <><Copy className="w-3.5 h-3.5"/> Copy</>}
              </button>
              <a href={slip.sportybet_url} target="_blank" rel="noopener noreferrer" data-testid="open-sportybet"
                 className="flex-1 sm:flex-none co-primary-action rounded-[6px] font-mono text-[11px] uppercase tracking-widest px-4 py-3 sm:py-2 inline-flex items-center justify-center gap-2 min-h-[44px]">
                <ExternalLink className="w-3.5 h-3.5"/> Open
              </a>
            </div>
          </div>
        </div>
      ) : !locked && (
        <div className="co-card p-4 sm:p-5 border-l-4 border-l-[#00ff66]" data-testid="sportybet-pending">
          <div className="flex items-start gap-3">
            <AlertCircle className="w-5 h-5 text-[#00ff66] shrink-0 mt-0.5" />
            <div className="flex-1 min-w-0">
              <div className="font-heading font-bold text-base">Booking code being prepared</div>
              <p className="text-sm text-[#a3a3a3] leading-relaxed mt-1">
                SportyBet booking codes can only be issued by SportyBet itself. Our team is building today's slip on SportyBet now and will publish the real code here shortly. In the meantime you can manually add the picks below to your SportyBet slip.
              </p>
              <a href={slip.sportybet_url} target="_blank" rel="noopener noreferrer"
                 className="mt-3 inline-flex items-center gap-2 co-primary-action rounded-[6px] font-mono text-[11px] uppercase tracking-widest px-4 py-3 min-h-[44px]">
                <ExternalLink className="w-3.5 h-3.5"/> Open SportyBet
              </a>
            </div>
          </div>
        </div>
      )}

      {/* Status summary */}
      {slip.status_summary && (
        <div className="flex items-center gap-2 flex-wrap">
          <StatusBadge count={slip.status_summary.won} status="won"/>
          <StatusBadge count={slip.status_summary.lost} status="lost"/>
          <StatusBadge count={slip.status_summary.void} status="void"/>
          <StatusBadge count={slip.status_summary.pending} status="pending"/>
        </div>
      )}

      {/* Legs */}
      <div className="space-y-3" data-testid="slip-legs">
        {slip.legs.map((l, i) => {
          const { day, time } = formatKickoff(l.kickoff);
          const isLocked = locked || l.market === "LOCKED";
          return (
            <div key={i} className="co-card p-4 sm:p-5 flex items-start gap-3 sm:gap-4">
              <div className="font-mono text-sm text-[#050607] bg-[#00ff66] rounded-[6px] w-9 h-9 grid place-items-center shrink-0 font-bold">{String(i + 1).padStart(2, "0")}</div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-2 flex-wrap">
                  <span className="co-tag">{l.sport.toUpperCase()}</span>
                  {l.country_code && (
                    <span className="co-tag inline-flex items-center gap-1">
                      <MapPin className="w-3 h-3"/>{l.country_code}
                    </span>
                  )}
                  <span className="font-mono text-[10px] uppercase tracking-widest text-[#a3a3a3] truncate">{l.league}</span>
                  {(day || time) && (
                    <span className="font-mono text-[10px] uppercase tracking-widest text-[#667482] inline-flex items-center gap-2 sm:ml-auto">
                      <Calendar className="w-3 h-3"/>{day}
                      <Clock className="w-3 h-3 ml-1"/>{time}
                    </span>
                  )}
                </div>
                {isLocked ? (
                  <>
                    <div className="font-heading font-bold text-base sm:text-lg leading-tight select-none blur-sm text-[#667482]">
                      ████████ vs ████████
                    </div>
                    <div className="flex items-center gap-2 mt-1 text-[#667482]">
                      <Lock className="w-3.5 h-3.5"/>
                      <span className="font-mono text-[10px] uppercase tracking-widest">Subscribe to unlock bet</span>
                    </div>
                    <div className="flex items-center gap-3 mt-2 flex-wrap sm:hidden">
                      <span className="font-mono text-2xl font-bold text-[#f5f5f5]" data-testid={`leg-odds-mobile-${i}`}>
                        {l.odds != null ? l.odds.toFixed(2) : "—"}
                      </span>
                      <span className="font-mono text-[10px] uppercase tracking-widest text-[#667482]">Odds</span>
                    </div>
                  </>
                ) : (
                  <>
                    <div className="font-heading font-bold text-base sm:text-lg leading-tight">{l.match}</div>
                    <div className="text-sm text-[#aeb8c2] mt-1">{l.selection_label}</div>
                    <div className="flex items-center gap-3 mt-2 flex-wrap">
                      <span className="font-mono text-2xl sm:text-3xl font-bold sm:hidden">
                        {l.odds != null ? l.odds.toFixed(2) : (l.odds_range || "Locked")}
                      </span>
                      {l.confidence > 0 && (
                        <span className="font-mono text-[10px] uppercase tracking-widest text-[#667482] sm:hidden">
                          CONF {l.confidence.toFixed(0)}% · EDGE {l.edge_pct?.toFixed(1)}% · EV {l.expected_value > 0 ? "+" : ""}{(l.expected_value * 100).toFixed(1)}%
                        </span>
                      )}
                    </div>
                    {l.reasoning && (
                      <p className="text-xs text-[#667482] mt-2 leading-relaxed line-clamp-2">{l.reasoning}</p>
                    )}
                  </>
                )}
              </div>
              <div className="text-right shrink-0 hidden sm:block">
                <div className="font-mono text-3xl font-bold" data-testid={`leg-odds-${i}`}>
                  {l.odds != null ? l.odds.toFixed(2) : (l.odds_range || "Locked")}
                </div>
                {!isLocked && l.confidence > 0 && (
                  <div className="font-mono text-[10px] uppercase tracking-widest text-[#667482] mt-1">
                    CONF {l.confidence.toFixed(0)}% · EDGE {l.edge_pct?.toFixed(1)}% · EV {l.expected_value > 0 ? "+" : ""}{(l.expected_value * 100).toFixed(1)}%
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {/* Summary */}
      <div className="co-card p-5">
        <div className="text-[10px] font-mono uppercase tracking-widest text-[#667482] mb-2 inline-flex items-center gap-2">
          <TrendingUp className="w-3.5 h-3.5 text-[#48a7ff]"/> AI Ensemble Summary
        </div>
        <p className="text-sm text-[#aeb8c2] leading-relaxed">{slip.summary}</p>
        <div className="mt-3 inline-block">
          <span className={`co-tag ${riskTag}`}>{slip.risk_level} RISK</span>
        </div>
      </div>

      {locked && onSubscribe && (
        <button onClick={onSubscribe} data-testid="subscribe-btn" className="w-full co-primary-action rounded-[8px] font-mono uppercase tracking-widest text-sm py-4">
          Subscribe to Unlock
        </button>
      )}
    </div>
  );
}
