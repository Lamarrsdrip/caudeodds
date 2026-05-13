import React, { useState } from "react";
import { Copy, ExternalLink, CheckCircle2, AlertCircle, Lock, Calendar, Clock, MapPin } from "lucide-react";
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
        <div className="font-mono text-[10px] uppercase tracking-widest text-[#525252] mb-2">// EMPTY SLATE</div>
        <p className="font-heading text-lg text-[#a3a3a3]">No slip published yet today. Check back soon.</p>
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
      {/* Data-quality badge — hidden when locked */}
      {!locked && (
        <div className="co-card p-3 sm:p-4 flex items-center gap-3" data-testid="data-quality-badge">
          <span className={`px-3 py-1 font-mono text-[10px] uppercase tracking-widest font-bold ${dataBadge.cls}`}>
            {dataBadge.label}
          </span>
          <span className="text-xs text-[#a3a3a3] leading-snug">{dataBadge.note}</span>
        </div>
      )}

      {/* KPI strip — 2 cols on mobile, 5 on desktop */}
      <div className="grid grid-cols-2 sm:grid-cols-5 border border-[#262626]" data-testid="slip-kpis">
        {[
          ["Legs", slip.leg_count],
          ["Combined Odds", slip.combined_odds != null ? slip.combined_odds.toFixed(2) : (slip.combined_odds_range || "🔒")],
          ["Confidence", slip.combined_confidence ? `${slip.combined_confidence.toFixed(0)}%` : "🔒"],
          ["EV", slip.expected_value != null ? `${slip.expected_value > 0 ? "+" : ""}${(slip.expected_value * 100).toFixed(1)}%` : "🔒"],
          ["Risk", slip.risk_level || "🔒"],
        ].map(([k, v]) => (
          <div key={k} className="p-4 sm:p-5 border-b sm:border-b-0 sm:border-r last:border-r-0 border-[#262626]">
            <div className="text-[10px] font-mono uppercase tracking-widest text-[#525252]">{k}</div>
            <div className={`font-mono text-xl sm:text-2xl mt-1 ${k === "EV" ? evColor : ""}`}>{v}</div>
          </div>
        ))}
      </div>

      {/* SportyBet bar */}
      {codeReady ? (
        <div className="co-card p-4 sm:p-5" data-testid="sportybet-bar">
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
            <div className="flex items-center gap-3 sm:gap-4 flex-wrap">
              <div className="px-3 py-1 bg-[#00ff66] text-[#050505] font-mono text-[10px] uppercase tracking-widest font-bold">
                SportyBet Code
              </div>
              <code className="font-mono text-2xl sm:text-3xl font-black tracking-[0.2em]" data-testid="sportybet-code">{slip.sportybet_code}</code>
            </div>
            <div className="flex items-center gap-2">
              <button onClick={copyCode} data-testid="copy-code-btn" className="flex-1 sm:flex-none border border-[#262626] hover:border-[#525252] hover:bg-[#1a1a1a] active:bg-[#262626] font-mono text-[11px] uppercase tracking-widest px-4 py-3 sm:py-2 inline-flex items-center justify-center gap-2 min-h-[44px]">
                {copied ? <><CheckCircle2 className="w-3.5 h-3.5 text-[#00ff66]"/> Copied</> : <><Copy className="w-3.5 h-3.5"/> Copy</>}
              </button>
              <a href={slip.sportybet_url} target="_blank" rel="noopener noreferrer" data-testid="open-sportybet"
                 className="flex-1 sm:flex-none bg-[#f5f5f5] text-[#050505] font-mono text-[11px] uppercase tracking-widest px-4 py-3 sm:py-2 hover:bg-[#00ff66] inline-flex items-center justify-center gap-2 min-h-[44px]">
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
                 className="mt-3 inline-flex items-center gap-2 bg-[#f5f5f5] text-[#050505] font-mono text-[11px] uppercase tracking-widest px-4 py-3 hover:bg-[#00ff66] min-h-[44px]">
                <ExternalLink className="w-3.5 h-3.5"/> Open SportyBet
              </a>
            </div>
          </div>
        </div>
      )}

      {/* Status summary */}
      {slip.status_summary && (
        <div className="flex items-center gap-2">
          <StatusBadge count={slip.status_summary.won} status="won"/>
          <StatusBadge count={slip.status_summary.lost} status="lost"/>
          <StatusBadge count={slip.status_summary.void} status="void"/>
          <StatusBadge count={slip.status_summary.pending} status="pending"/>
        </div>
      )}

      {/* Legs */}
      <div className="co-card divide-y divide-[#1a1a1a]" data-testid="slip-legs">
        {slip.legs.map((l, i) => {
          const { day, time } = formatKickoff(l.kickoff);
          const isLocked = locked || l.market === "LOCKED";
          return (
            <div key={i} className="p-4 sm:p-5 flex items-start gap-3 sm:gap-4">
              <div className="font-mono text-xl sm:text-2xl text-[#525252] w-8 sm:w-10 shrink-0">{String(i + 1).padStart(2, "0")}</div>
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
                    <span className="font-mono text-[10px] uppercase tracking-widest text-[#525252] inline-flex items-center gap-2 sm:ml-auto">
                      <Calendar className="w-3 h-3"/>{day}
                      <Clock className="w-3 h-3 ml-1"/>{time}
                    </span>
                  )}
                </div>
                {isLocked ? (
                  <div className="flex items-center gap-2 mt-1 text-[#525252]">
                    <Lock className="w-4 h-4"/>
                    <span className="font-heading font-bold text-base">Subscribe to unlock</span>
                  </div>
                ) : (
                  <>
                    <div className="font-heading font-bold text-base sm:text-lg leading-tight">{l.match}</div>
                    <div className="text-sm text-[#a3a3a3] mt-1">{l.selection_label}</div>
                    <div className="flex items-center gap-3 mt-2 flex-wrap">
                      <span className="font-mono text-2xl sm:text-3xl font-bold sm:hidden">
                        {l.odds != null ? l.odds.toFixed(2) : (l.odds_range || "🔒")}
                      </span>
                      {l.confidence > 0 && (
                        <span className="font-mono text-[10px] uppercase tracking-widest text-[#525252] sm:hidden">
                          CONF {l.confidence.toFixed(0)}% · EDGE {l.edge_pct?.toFixed(1)}% · EV {l.expected_value > 0 ? "+" : ""}{(l.expected_value * 100).toFixed(1)}%
                        </span>
                      )}
                    </div>
                    {l.reasoning && (
                      <p className="text-xs text-[#525252] mt-2 leading-relaxed line-clamp-2">{l.reasoning}</p>
                    )}
                  </>
                )}
              </div>
              <div className="text-right shrink-0 hidden sm:block">
                <div className="font-mono text-3xl font-bold" data-testid={`leg-odds-${i}`}>
                  {l.odds != null ? l.odds.toFixed(2) : (l.odds_range || "🔒")}
                </div>
                {!isLocked && l.confidence > 0 && (
                  <div className="font-mono text-[10px] uppercase tracking-widest text-[#525252] mt-1">
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
        <div className="text-[10px] font-mono uppercase tracking-widest text-[#525252] mb-2 inline-flex items-center gap-2">
          <AlertCircle className="w-3.5 h-3.5"/> AI Ensemble Summary
        </div>
        <p className="text-sm text-[#a3a3a3] leading-relaxed">{slip.summary}</p>
        <div className="mt-3 inline-block">
          <span className={`co-tag ${riskTag}`}>{slip.risk_level} RISK</span>
        </div>
      </div>

      {locked && onSubscribe && (
        <button onClick={onSubscribe} data-testid="subscribe-btn" className="w-full bg-[#00ff66] text-[#050505] font-mono uppercase tracking-widest text-sm py-4 hover:bg-[#f5f5f5]">
          Subscribe to Unlock →
        </button>
      )}
    </div>
  );
}
