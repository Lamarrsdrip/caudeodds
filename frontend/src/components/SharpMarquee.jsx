import React from "react";

export default function SharpMarquee({ signals }) {
  if (!signals?.length) return null;
  const items = [...signals, ...signals]; // duplicate for seamless loop
  return (
    <div className="border-b border-[#262626] bg-[#050505] overflow-hidden no-scrollbar" data-testid="sharp-marquee">
      <div className="co-marquee-track flex items-center">
        {items.map((s, i) => {
          const positive = s.line_delta_pct > 0;
          const color = s.alert === "STEAM_MOVE"
            ? "text-[#00ff66]"
            : s.alert === "SHARP_FADE_PUBLIC"
              ? "text-[#ff9900]"
              : "text-[#a3a3a3]";
          return (
            <div key={i} className="flex items-center gap-2 px-6 py-2 border-r border-[#262626] whitespace-nowrap">
              <span className="font-mono text-[10px] uppercase tracking-widest text-[#525252]">{s.sport === "football" ? "FB" : "BB"}</span>
              <span className="font-mono text-xs text-[#f5f5f5]">{s.match}</span>
              <span className={`font-mono text-xs ${positive ? "text-[#00ff66]" : "text-[#ff3333]"}`}>
                {positive ? "▲" : "▼"} {Math.abs(s.line_delta_pct).toFixed(1)}%
              </span>
              <span className="font-mono text-[10px] text-[#a3a3a3]">SHARP {s.sharp_home_pct}%</span>
              <span className={`co-tag ${color}`}>{s.alert}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
