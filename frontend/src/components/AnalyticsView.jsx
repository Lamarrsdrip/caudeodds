import React from "react";
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Area, AreaChart } from "recharts";

export default function AnalyticsView({ roi, sharp }) {
  const curve = (roi?.curve || []).map((c, i) => ({ ...c, idx: i }));
  return (
    <div className="space-y-6" data-testid="analytics-view">
      <h2 className="font-heading font-black text-3xl tracking-tight">PERFORMANCE ANALYTICS</h2>

      {/* KPI grid */}
      <div className="grid grid-cols-2 md:grid-cols-5 border border-[#262626]">
        {[
          { l: "Bankroll", v: `$${roi?.current_bankroll?.toFixed(2) ?? "0.00"}`, c: "" },
          { l: "Profit", v: `${roi?.profit >= 0 ? "+" : ""}$${roi?.profit?.toFixed(2) ?? "0.00"}`, c: roi?.profit > 0 ? "text-[#00ff66]" : roi?.profit < 0 ? "text-[#ff3333]" : "" },
          { l: "Total Staked", v: `$${roi?.total_staked?.toFixed(2) ?? "0.00"}`, c: "" },
          { l: "Win Rate", v: `${roi?.win_rate?.toFixed(1) ?? "0.0"}%`, c: "" },
          { l: "ROI", v: `${roi?.roi_pct >= 0 ? "+" : ""}${roi?.roi_pct?.toFixed(2) ?? "0.00"}%`, c: roi?.roi_pct > 0 ? "text-[#00ff66]" : roi?.roi_pct < 0 ? "text-[#ff3333]" : "" },
        ].map((k, i) => (
          <div key={i} className={`p-5 ${i < 4 ? "border-r border-[#262626]" : ""} border-b md:border-b-0 border-[#262626]`}>
            <div className="text-[10px] font-mono uppercase tracking-widest text-[#525252]">{k.l}</div>
            <div className={`font-mono text-2xl mt-1 ${k.c}`}>{k.v}</div>
          </div>
        ))}
      </div>

      {/* Bankroll curve */}
      <div className="co-card p-5">
        <div className="flex items-center justify-between mb-4">
          <h3 className="font-heading font-bold text-lg">Bankroll Curve</h3>
          <span className="font-mono text-[10px] uppercase tracking-widest text-[#525252]">{curve.length} settled events</span>
        </div>
        <div style={{ width: "100%", height: 280, minHeight: 240 }}>
          <ResponsiveContainer width="100%" height="100%" minHeight={240}>
            <AreaChart data={curve} margin={{ top: 10, right: 12, bottom: 0, left: -12 }}>
              <defs>
                <linearGradient id="brkArea" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#00ff66" stopOpacity={0.18} />
                  <stop offset="100%" stopColor="#00ff66" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid stroke="#262626" strokeDasharray="0" />
              <XAxis dataKey="idx" stroke="#525252" fontSize={10} tick={{ fontFamily: "JetBrains Mono" }} />
              <YAxis stroke="#525252" fontSize={10} tick={{ fontFamily: "JetBrains Mono" }} domain={['dataMin', 'dataMax']} />
              <Tooltip
                contentStyle={{ background: "#121212", border: "1px solid #262626", borderRadius: 0, fontFamily: "JetBrains Mono", fontSize: 11 }}
                labelStyle={{ color: "#a3a3a3" }}
              />
              <Area type="monotone" dataKey="bankroll" stroke="#00ff66" strokeWidth={2} fill="url(#brkArea)" />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Sharp money signals */}
      <div className="co-card p-5">
        <div className="flex items-center justify-between mb-4">
          <h3 className="font-heading font-bold text-lg">Sharp Money & Line Movement</h3>
          <span className="font-mono text-[10px] uppercase tracking-widest text-[#525252]">Top {sharp?.length ?? 0} signals</span>
        </div>
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-[#262626]">
              {["Match","League","Δ Line","Sharp%","Public%","Alert"].map(h => (
                <th key={h} className="text-left font-mono text-[10px] uppercase tracking-widest text-[#525252] py-2">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {(sharp || []).map((s, i) => (
              <tr key={i} className="border-b border-[#1a1a1a]">
                <td className="py-2 pr-2">{s.match}</td>
                <td className="py-2 pr-2 font-mono text-xs text-[#a3a3a3]">{s.league}</td>
                <td className={`py-2 pr-2 font-mono ${s.line_delta_pct > 0 ? "text-[#00ff66]" : "text-[#ff3333]"}`}>
                  {s.line_delta_pct > 0 ? "+" : ""}{s.line_delta_pct?.toFixed(1)}%
                </td>
                <td className="py-2 pr-2 font-mono">{s.sharp_home_pct}%</td>
                <td className="py-2 pr-2 font-mono">{s.public_home_pct}%</td>
                <td className="py-2"><span className={`co-tag ${s.alert === "STEAM_MOVE" ? "co-tag-pos" : s.alert === "SHARP_FADE_PUBLIC" ? "co-tag-warn" : ""}`}>{s.alert}</span></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
