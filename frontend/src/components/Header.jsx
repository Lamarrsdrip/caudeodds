import React from "react";
import { Activity } from "lucide-react";

export default function Header({ roi, onGenerate, generating, onTabChange, tab, parlay }) {
  const profit = roi?.profit ?? 0;
  const profitColor = profit > 0 ? "text-[#00ff66]" : profit < 0 ? "text-[#ff3333]" : "text-[#a3a3a3]";
  const tabs = [
    { id: "picks", label: "Today's Picks" },
    { id: "history", label: "History" },
    { id: "analytics", label: "Analytics" },
    { id: "rejected", label: "Rejected" },
    { id: "settings", label: "Settings" },
  ];
  return (
    <header className="border-b border-[#262626] bg-[#050505] sticky top-0 z-30" data-testid="app-header">
      <div className="px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2">
            <div className="w-2 h-2 bg-[#00ff66] co-pulse" />
            <h1 className="font-heading font-black text-2xl tracking-tight">CLAUDEODD</h1>
            <span className="font-mono text-[10px] text-[#525252] tracking-widest uppercase pl-2 border-l border-[#262626]">
              QUANT&nbsp;BETTING&nbsp;TERMINAL
            </span>
          </div>
        </div>
        <div className="flex items-center gap-6">
          <div className="text-right" data-testid="hdr-bankroll">
            <div className="text-[10px] uppercase tracking-widest text-[#525252] font-mono">Bankroll</div>
            <div className="font-mono text-lg">${roi?.current_bankroll?.toFixed(2) ?? "—"}</div>
          </div>
          <div className="text-right" data-testid="hdr-roi">
            <div className="text-[10px] uppercase tracking-widest text-[#525252] font-mono">ROI</div>
            <div className={`font-mono text-lg ${profitColor}`}>
              {roi?.roi_pct >= 0 ? "+" : ""}{roi?.roi_pct?.toFixed(2) ?? "0.00"}%
            </div>
          </div>
          <div className="text-right" data-testid="hdr-winrate">
            <div className="text-[10px] uppercase tracking-widest text-[#525252] font-mono">Win Rate</div>
            <div className="font-mono text-lg">{roi?.win_rate?.toFixed(1) ?? "0.0"}%</div>
          </div>
          {parlay?.legs > 0 && (
            <div className="text-right border-l border-[#262626] pl-6" data-testid="hdr-parlay">
              <div className="text-[10px] uppercase tracking-widest text-[#525252] font-mono">Daily Slip ({parlay.legs}-fold)</div>
              <div className="font-mono text-lg">@{parlay.combined_odds?.toFixed(2)}</div>
            </div>
          )}
          <button
            onClick={onGenerate}
            disabled={generating}
            data-testid="generate-picks-btn"
            className="bg-[#f5f5f5] text-[#050505] font-mono uppercase tracking-widest text-xs px-4 py-2 hover:bg-[#00ff66] disabled:opacity-50 transition-colors"
          >
            <span className="inline-flex items-center gap-2">
              <Activity className="w-3.5 h-3.5" strokeWidth={2.5} />
              {generating ? "ANALYZING…" : "RUN ENSEMBLE"}
            </span>
          </button>
        </div>
      </div>
      <nav className="px-6 flex items-center gap-0 border-t border-[#262626]">
        {tabs.map(t => (
          <button
            key={t.id}
            onClick={() => onTabChange(t.id)}
            data-testid={`tab-${t.id}`}
            className={`font-mono uppercase tracking-widest text-[11px] px-4 py-3 border-r border-[#262626] transition-colors ${
              tab === t.id ? "bg-[#f5f5f5] text-[#050505]" : "text-[#a3a3a3] hover:bg-[#1a1a1a] hover:text-[#f5f5f5]"
            }`}
          >
            {t.label}
          </button>
        ))}
      </nav>
    </header>
  );
}
