import React, { useState } from "react";

export default function HistoryTable({ picks, onSettle }) {
  const [sport, setSport] = useState("all");
  const [status, setStatus] = useState("all");
  const filtered = picks.filter(p =>
    (sport === "all" || p.sport === sport) &&
    (status === "all" || p.status === status)
  );

  return (
    <div className="space-y-4" data-testid="history-view">
      <div className="flex items-center justify-between">
        <h2 className="font-heading font-black text-3xl tracking-tight">PREDICTION HISTORY</h2>
        <div className="flex items-center gap-2">
          {["all", "football", "basketball"].map(s => (
            <button
              key={s}
              onClick={() => setSport(s)}
              data-testid={`history-sport-${s}`}
              className={`font-mono uppercase tracking-widest text-[10px] px-3 py-1.5 border ${
                sport === s ? "bg-[#f5f5f5] text-[#050505] border-[#f5f5f5]" : "border-[#262626] text-[#a3a3a3] hover:bg-[#1a1a1a]"
              }`}
            >{s}</button>
          ))}
          <span className="text-[#262626] mx-1">|</span>
          {["all", "pending", "won", "lost"].map(s => (
            <button
              key={s}
              onClick={() => setStatus(s)}
              data-testid={`history-status-${s}`}
              className={`font-mono uppercase tracking-widest text-[10px] px-3 py-1.5 border ${
                status === s ? "bg-[#f5f5f5] text-[#050505] border-[#f5f5f5]" : "border-[#262626] text-[#a3a3a3] hover:bg-[#1a1a1a]"
              }`}
            >{s}</button>
          ))}
        </div>
      </div>

      <div className="co-card overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-[#262626]">
              {["Date","Sport","Match","Selection","Odds","Conf","EV","Risk","Stake","Status","Action"].map(h => (
                <th key={h} className="text-left font-mono text-[10px] uppercase tracking-widest text-[#525252] px-3 py-3">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {filtered.length === 0 ? (
              <tr><td colSpan={11} className="text-center py-12 text-[#525252] font-mono text-xs uppercase tracking-widest">No predictions yet</td></tr>
            ) : filtered.map(p => (
              <tr key={p.id} className="border-b border-[#1a1a1a] hover:bg-[#1a1a1a] transition-colors" data-testid={`history-row-${p.id}`}>
                <td className="px-3 py-3 font-mono text-xs text-[#a3a3a3]">{p.date}</td>
                <td className="px-3 py-3"><span className="co-tag">{p.sport.toUpperCase()}</span></td>
                <td className="px-3 py-3 font-medium">{p.match}</td>
                <td className="px-3 py-3 text-[#a3a3a3]">{p.selection_label}</td>
                <td className="px-3 py-3 font-mono">{p.odds.toFixed(2)}</td>
                <td className="px-3 py-3 font-mono">{p.confidence.toFixed(0)}%</td>
                <td className={`px-3 py-3 font-mono ${p.expected_value > 0 ? "text-[#00ff66]" : "text-[#ff3333]"}`}>
                  {p.expected_value > 0 ? "+" : ""}{(p.expected_value * 100).toFixed(1)}%
                </td>
                <td className="px-3 py-3"><span className={`co-tag ${p.risk_level === "LOW" ? "co-tag-pos" : p.risk_level === "HIGH" ? "co-tag-neg" : "co-tag-warn"}`}>{p.risk_level}</span></td>
                <td className="px-3 py-3 font-mono">${p.stake_units.toFixed(2)}</td>
                <td className="px-3 py-3">
                  <span className={`co-tag ${p.status === "won" ? "co-tag-pos" : p.status === "lost" ? "co-tag-neg" : ""}`}>{p.status.toUpperCase()}</span>
                </td>
                <td className="px-3 py-3">
                  {p.status === "pending" ? (
                    <div className="flex gap-1">
                      <button onClick={() => onSettle(p.id, "won")} data-testid={`hist-won-${p.id}`} className="px-2 py-1 border border-[#00ff66] text-[#00ff66] font-mono text-[10px] hover:bg-[#00ff66] hover:text-[#050505]">W</button>
                      <button onClick={() => onSettle(p.id, "lost")} data-testid={`hist-lost-${p.id}`} className="px-2 py-1 border border-[#ff3333] text-[#ff3333] font-mono text-[10px] hover:bg-[#ff3333] hover:text-[#050505]">L</button>
                    </div>
                  ) : <span className="text-[#525252] font-mono text-[10px]">—</span>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
