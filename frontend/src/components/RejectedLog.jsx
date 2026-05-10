import React from "react";

const REASON_COLOR = {
  TRAP: "co-tag-neg",
  LOW_EV: "co-tag-warn",
  LOW_LIQ: "co-tag-warn",
  VOLATILITY: "co-tag-warn",
  INJURY_CHAOS: "co-tag-warn",
  CONFLICT: "co-tag-warn",
  DISAGREEMENT: "co-tag-neg",
  LOW_CONFIDENCE: "co-tag-warn",
  NARRATIVE_RISK: "co-tag-neg",
  MODEL_ERROR: "co-tag-neg",
  ODDS_INVALID: "co-tag-warn",
  OUTRANKED: "",
};

export default function RejectedLog({ rejected }) {
  return (
    <div className="space-y-4" data-testid="rejected-view">
      <div className="flex items-baseline justify-between">
        <h2 className="font-heading font-black text-3xl tracking-tight">FILTER REJECTION LOG</h2>
        <p className="font-mono text-[10px] uppercase tracking-widest text-[#525252]">
          {rejected.length} games skipped — discipline over volume
        </p>
      </div>
      <div className="co-card divide-y divide-[#1a1a1a]">
        {rejected.length === 0 ? (
          <div className="p-12 text-center text-[#525252] font-mono text-xs uppercase tracking-widest">No rejections yet</div>
        ) : rejected.map(r => (
          <div key={r.id} className="px-5 py-3 flex items-center gap-4 hover:bg-[#1a1a1a] transition-colors" data-testid={`reject-row-${r.id}`}>
            <span className="font-mono text-[10px] text-[#525252] w-24 shrink-0">{r.date}</span>
            <span className="co-tag w-24 text-center shrink-0">{r.sport.toUpperCase()}</span>
            <span className={`co-tag w-32 text-center shrink-0 ${REASON_COLOR[r.reason_code] || ""}`}>{r.reason_code}</span>
            <span className="text-sm font-medium w-64 shrink-0 truncate text-[#a3a3a3]">{r.match}</span>
            <span className="text-xs text-[#525252] flex-1 truncate font-mono">{r.reason}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
