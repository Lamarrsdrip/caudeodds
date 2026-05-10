import React, { useEffect, useState } from "react";
import { TrendingUp, TrendingDown, Minus, CheckCircle2, XCircle } from "lucide-react";
import { api } from "@/lib/api";

/**
 * PublicRoiTracker
 * ────────────────
 * Honest, public-facing performance feed pulled from settled slips. Renders a
 * 30-day summary KPI strip + per-day outcome list (outcomes only, picks
 * hidden) so visitors see real W/L track record and ROI before subscribing.
 */
export default function PublicRoiTracker() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.publicRoi(30)
      .then((d) => { setData(d); setLoading(false); })
      .catch(() => { setLoading(false); });
  }, []);

  if (loading) {
    return (
      <section className="border-b border-[#262626]" data-testid="public-roi-section">
        <div className="max-w-[1400px] mx-auto px-6 py-20">
          <h2 className="font-heading font-black text-3xl tracking-tight mb-8">PUBLIC ROI TRACKER</h2>
          <div className="co-card p-12 text-center text-[#525252] font-mono text-xs uppercase tracking-widest">
            Loading honest performance feed…
          </div>
        </div>
      </section>
    );
  }

  if (!data) return null;

  const t = data.totals || {};
  const settled = t.slips_settled || 0;
  const noData = settled === 0;
  const roiPositive = (t.roi_pct || 0) > 0;
  const roiNegative = (t.roi_pct || 0) < 0;
  const profitColor = roiPositive ? "text-[#00ff66]" : roiNegative ? "text-[#ff3333]" : "text-[#f5f5f5]";

  return (
    <section className="border-b border-[#262626] bg-grid" data-testid="public-roi-section">
      <div className="max-w-[1400px] mx-auto px-6 py-20">
        <div className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-4 mb-8">
          <div>
            <div className="font-mono text-[10px] uppercase tracking-widest text-[#525252] mb-3">
              // {data.from} → {data.to} · settled slips only · 1 unit flat stake
            </div>
            <h2 className="font-heading font-black text-3xl sm:text-4xl tracking-tight">PUBLIC ROI TRACKER</h2>
            <p className="text-sm text-[#a3a3a3] mt-2 max-w-2xl">
              Every slip we publish is graded against real final scores. No hiding losses, no
              cherry-picking screenshots. Here's the honest last-30-day P/L on a flat 1-unit stake.
            </p>
          </div>
          <div className="font-mono text-[10px] uppercase tracking-widest text-[#525252] sm:text-right">
            {data.window_days}-day window<br/>updated live
          </div>
        </div>

        {noData ? (
          <div className="co-card p-12 text-center font-mono text-xs uppercase tracking-widest text-[#525252]" data-testid="public-roi-empty">
            // No settled slips in the last {data.window_days} days yet. Track record will fill in as auto-settlement grades each day's matches.
          </div>
        ) : (
          <>
            {/* KPI strip */}
            <div className="grid grid-cols-2 sm:grid-cols-5 border border-[#262626] mb-8" data-testid="public-roi-kpis">
              {[
                { k: "Slips Settled", v: settled, c: "" },
                { k: "Won", v: t.won, c: "text-[#00ff66]" },
                { k: "Lost", v: t.lost, c: "text-[#ff3333]" },
                { k: "Win Rate", v: `${t.win_rate_pct?.toFixed(1)}%`, c: "" },
                { k: "ROI (30d)", v: `${roiPositive ? "+" : ""}${t.roi_pct?.toFixed(1)}%`, c: profitColor },
              ].map(({ k, v, c }) => (
                <div key={k} className="p-5 border-b sm:border-b-0 sm:border-r last:border-r-0 border-[#262626] bg-[#0a0a0a]">
                  <div className="text-[10px] font-mono uppercase tracking-widest text-[#525252]">{k}</div>
                  <div className={`font-mono text-2xl sm:text-3xl mt-1 font-bold ${c}`}>{v}</div>
                </div>
              ))}
            </div>

            <div className={`co-card p-4 mb-6 flex items-center gap-3 ${roiPositive ? "border-l-4 border-l-[#00ff66]" : roiNegative ? "border-l-4 border-l-[#ff3333]" : ""}`} data-testid="public-roi-profit">
              {roiPositive ? <TrendingUp className="w-5 h-5 text-[#00ff66]"/> :
                roiNegative ? <TrendingDown className="w-5 h-5 text-[#ff3333]"/> :
                <Minus className="w-5 h-5 text-[#a3a3a3]"/>}
              <div className="font-mono text-sm">
                <span className="text-[#525252] uppercase tracking-widest text-[10px] mr-2">P/L</span>
                <span className={`text-xl font-bold ${profitColor}`}>{(t.profit_units || 0) > 0 ? "+" : ""}{t.profit_units?.toFixed(2)} units</span>
                <span className="text-[#525252] ml-3">over {settled} settled slip{settled === 1 ? "" : "s"}</span>
              </div>
            </div>

            {/* Per-day outcome list */}
            <div className="co-card divide-y divide-[#1a1a1a]" data-testid="public-roi-history">
              <div className="px-5 py-3 font-mono text-[10px] uppercase tracking-widest text-[#525252] bg-[#0a0a0a]">
                // Recent results — outcomes only, picks unlocked after subscribe
              </div>
              {(data.history || []).slice(0, 14).map((row) => {
                const outcomeMap = {
                  won: { Icon: CheckCircle2, cls: "text-[#00ff66]", label: "WON", bg: "bg-[#00ff66]/10" },
                  lost: { Icon: XCircle, cls: "text-[#ff3333]", label: "LOST", bg: "bg-[#ff3333]/10" },
                  void: { Icon: Minus, cls: "text-[#a3a3a3]", label: "VOID", bg: "bg-[#262626]" },
                  pending: { Icon: Minus, cls: "text-[#ffb800]", label: "PENDING", bg: "bg-[#ffb800]/10" },
                };
                const o = outcomeMap[row.outcome] || outcomeMap.pending;
                const profit = row.outcome === "won" ? `+${(row.combined_odds - 1).toFixed(2)}` :
                  row.outcome === "lost" ? "-1.00" :
                  row.outcome === "void" ? "0.00" : "—";
                return (
                  <div key={row.date} className="px-5 py-4 flex items-center gap-4" data-testid={`roi-row-${row.date}`}>
                    <o.Icon className={`w-5 h-5 shrink-0 ${o.cls}`}/>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="font-mono text-sm text-[#f5f5f5]">{row.date}</span>
                        <span className={`px-2 py-0.5 ${o.bg} font-mono text-[10px] uppercase tracking-widest font-bold ${o.cls}`}>{o.label}</span>
                      </div>
                      <div className="font-mono text-[10px] uppercase tracking-widest text-[#525252] mt-1">
                        {row.leg_count}-leg @ {row.combined_odds.toFixed(2)}
                        {row.won_legs > 0 && <span className="text-[#00ff66] ml-2">{row.won_legs}W</span>}
                        {row.lost_legs > 0 && <span className="text-[#ff3333] ml-2">{row.lost_legs}L</span>}
                        {row.void_legs > 0 && <span className="text-[#a3a3a3] ml-2">{row.void_legs}V</span>}
                        {row.pending_legs > 0 && <span className="text-[#ffb800] ml-2">{row.pending_legs}P</span>}
                      </div>
                    </div>
                    <div className={`font-mono text-base sm:text-lg font-bold tabular-nums shrink-0 ${
                      row.outcome === "won" ? "text-[#00ff66]" :
                      row.outcome === "lost" ? "text-[#ff3333]" : "text-[#525252]"
                    }`}>
                      {profit}
                    </div>
                  </div>
                );
              })}
            </div>

            <p className="text-[10px] font-mono uppercase tracking-widest text-[#525252] mt-6 leading-relaxed">
              // Past results do not guarantee future results. 18+ only. Bet responsibly.
            </p>
          </>
        )}
      </div>
    </section>
  );
}
