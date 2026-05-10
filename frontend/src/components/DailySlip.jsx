import React, { useState } from "react";
import { Copy, ExternalLink, CheckCircle2, AlertCircle } from "lucide-react";
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

export default function DailySlip({ slip, locked, onSubscribe }) {
  const [copied, setCopied] = useState(false);
  if (!slip) {
    return (
      <div className="co-card p-12 text-center bg-grid">
        <div className="font-mono text-[10px] uppercase tracking-widest text-[#525252] mb-2">EMPTY SLATE</div>
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

  return (
    <div className="space-y-5" data-testid="daily-slip">
      {/* KPI strip */}
      <div className="grid grid-cols-2 md:grid-cols-5 border border-[#262626]" data-testid="slip-kpis">
        {[
          ["Legs", slip.leg_count],
          ["Combined Odds", slip.combined_odds?.toFixed(2)],
          ["Confidence", `${slip.combined_confidence?.toFixed(0)}%`],
          ["EV", `${slip.expected_value > 0 ? "+" : ""}${(slip.expected_value * 100).toFixed(1)}%`],
          ["Risk", slip.risk_level],
        ].map(([k, v], i) => (
          <div key={k} className={`p-5 ${i < 4 ? "border-r border-[#262626]" : ""} border-b md:border-b-0 border-[#262626]`}>
            <div className="text-[10px] font-mono uppercase tracking-widest text-[#525252]">{k}</div>
            <div className={`font-mono text-2xl mt-1 ${k === "EV" ? evColor : ""}`}>{v}</div>
          </div>
        ))}
      </div>

      {/* SportyBet bar */}
      <div className="co-card p-5 flex items-center justify-between flex-wrap gap-4" data-testid="sportybet-bar">
        <div className="flex items-center gap-4">
          <div className="px-3 py-1 bg-[#00ff66] text-[#050505] font-mono text-[10px] uppercase tracking-widest font-bold">
            SportyBet Code
          </div>
          <code className="font-mono text-2xl font-bold tracking-widest" data-testid="sportybet-code">{slip.sportybet_code}</code>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={copyCode} data-testid="copy-code-btn" className="border border-[#262626] hover:border-[#525252] hover:bg-[#1a1a1a] font-mono text-[11px] uppercase tracking-widest px-4 py-2 inline-flex items-center gap-2">
            {copied ? <><CheckCircle2 className="w-3.5 h-3.5 text-[#00ff66]"/> Copied</> : <><Copy className="w-3.5 h-3.5"/> Copy Code</>}
          </button>
          <a href={slip.sportybet_url} target="_blank" rel="noopener noreferrer" data-testid="open-sportybet"
             className="bg-[#f5f5f5] text-[#050505] font-mono text-[11px] uppercase tracking-widest px-4 py-2 hover:bg-[#00ff66] inline-flex items-center gap-2">
            <ExternalLink className="w-3.5 h-3.5"/> Open SportyBet
          </a>
        </div>
      </div>

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
        {slip.legs.map((l, i) => (
          <div key={i} className="p-5 flex items-start gap-4">
            <div className="font-mono text-2xl text-[#525252] w-10 shrink-0">{String(i + 1).padStart(2, "0")}</div>
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 mb-1">
                <span className="co-tag">{l.sport.toUpperCase()}</span>
                <span className="font-mono text-[10px] uppercase tracking-widest text-[#525252]">{l.league}</span>
              </div>
              <div className="font-heading font-bold text-base">{l.match}</div>
              <div className="text-sm text-[#a3a3a3] mt-1">{l.selection_label}</div>
              {l.reasoning && (
                <p className="text-xs text-[#525252] mt-2 leading-relaxed line-clamp-2">{l.reasoning}</p>
              )}
            </div>
            <div className="text-right shrink-0">
              <div className="font-mono text-3xl font-bold">{l.odds?.toFixed(2)}</div>
              {l.confidence > 0 && (
                <div className="font-mono text-[10px] uppercase tracking-widest text-[#525252] mt-1">
                  CONF {l.confidence.toFixed(0)}% · EDGE {l.edge_pct?.toFixed(1)}%
                </div>
              )}
            </div>
          </div>
        ))}
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
