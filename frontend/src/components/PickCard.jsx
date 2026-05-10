import React from "react";

function ConsensusBar({ agreement, claudeConf, gptConf }) {
  return (
    <div className="space-y-2" data-testid="consensus-meter">
      <div className="flex items-center justify-between text-[10px] font-mono uppercase tracking-widest text-[#525252]">
        <span>CLAUDE&nbsp;{claudeConf?.toFixed(0)}%</span>
        <span>AGREEMENT&nbsp;{agreement?.toFixed(0)}%</span>
        <span>GPT&nbsp;{gptConf?.toFixed(0)}%</span>
      </div>
      <div className="h-2 w-full bg-[#1a1a1a] flex overflow-hidden">
        <div className="h-full bg-[#ffffff]" style={{ width: `${claudeConf}%` }} />
        <div className="h-full bg-[#737373] ml-auto" style={{ width: `${gptConf}%` }} />
      </div>
    </div>
  );
}

function RiskBadge({ level }) {
  const map = {
    LOW: "co-tag-pos",
    MEDIUM: "co-tag-warn",
    HIGH: "co-tag-neg",
  };
  return <span className={`co-tag ${map[level] || ""}`} data-testid="risk-badge">{level}</span>;
}

export default function PickCard({ pick, onSettle }) {
  const claudeConf = pick.reasoning_view?.tactical_confidence ?? 0;
  const gptConf = pick.quant_view?.confidence ?? 0;
  const evColor = pick.expected_value > 0 ? "text-[#00ff66]" : "text-[#ff3333]";
  const settled = pick.status !== "pending";

  return (
    <div className="co-card co-rise p-5 flex flex-col gap-4" data-testid={`pick-card-${pick.id}`}>
      {/* Header */}
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="co-tag" data-testid="pick-sport">{pick.sport.toUpperCase()}</span>
            <span className="font-mono text-[10px] uppercase tracking-widest text-[#525252]">{pick.league}</span>
          </div>
          <h3 className="font-heading font-bold text-lg leading-tight" data-testid="pick-match">{pick.match}</h3>
          <div className="font-mono text-[10px] text-[#525252] mt-1">
            {new Date(pick.kickoff).toLocaleString(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })}
          </div>
        </div>
        <RiskBadge level={pick.risk_level} />
      </div>

      <div className="co-divider" />

      {/* Selection */}
      <div>
        <div className="text-[10px] font-mono uppercase tracking-widest text-[#525252] mb-1">Selection</div>
        <div className="flex items-baseline justify-between">
          <div className="font-heading font-bold text-base" data-testid="pick-selection">{pick.selection_label}</div>
          <div className="font-mono text-3xl font-bold" data-testid="pick-odds">{pick.odds.toFixed(2)}</div>
        </div>
      </div>

      {/* Stats grid */}
      <div className="grid grid-cols-3 border border-[#262626]">
        <div className="p-3 border-r border-[#262626]">
          <div className="text-[10px] font-mono uppercase tracking-widest text-[#525252]">Confidence</div>
          <div className="font-mono text-xl mt-1" data-testid="pick-confidence">{pick.confidence.toFixed(0)}%</div>
        </div>
        <div className="p-3 border-r border-[#262626]">
          <div className="text-[10px] font-mono uppercase tracking-widest text-[#525252]">EV</div>
          <div className={`font-mono text-xl mt-1 ${evColor}`} data-testid="pick-ev">
            {pick.expected_value > 0 ? "+" : ""}{(pick.expected_value * 100).toFixed(1)}%
          </div>
        </div>
        <div className="p-3">
          <div className="text-[10px] font-mono uppercase tracking-widest text-[#525252]">Edge</div>
          <div className={`font-mono text-xl mt-1 ${pick.edge_pct > 0 ? "text-[#00ff66]" : "text-[#a3a3a3]"}`} data-testid="pick-edge">
            {pick.edge_pct > 0 ? "+" : ""}{pick.edge_pct.toFixed(1)}%
          </div>
        </div>
      </div>

      {/* Consensus */}
      <ConsensusBar agreement={pick.agreement} claudeConf={claudeConf} gptConf={gptConf} />

      {/* Kelly stake */}
      <div className="flex items-center justify-between border-t border-[#262626] pt-3">
        <div>
          <div className="text-[10px] font-mono uppercase tracking-widest text-[#525252]">Kelly Stake</div>
          <div className="font-mono text-sm">{pick.kelly_stake_pct.toFixed(2)}% • ${pick.stake_units.toFixed(2)}</div>
        </div>
        <div className="text-right">
          <div className="text-[10px] font-mono uppercase tracking-widest text-[#525252]">Potential</div>
          <div className="font-mono text-sm text-[#00ff66]">+${(pick.stake_units * (pick.odds - 1)).toFixed(2)}</div>
        </div>
      </div>

      {/* Reasoning */}
      <div className="border-t border-[#262626] pt-3">
        <div className="text-[10px] font-mono uppercase tracking-widest text-[#525252] mb-1">AI Ensemble Reasoning</div>
        <p className="text-xs text-[#a3a3a3] leading-relaxed line-clamp-4" data-testid="pick-reasoning">
          {pick.reasoning}
        </p>
      </div>

      {/* Settle controls */}
      <div className="flex items-center gap-2">
        {settled ? (
          <div className={`co-tag w-full text-center py-2 ${pick.status === "won" ? "co-tag-pos" : pick.status === "lost" ? "co-tag-neg" : ""}`} data-testid="pick-status">
            {pick.status.toUpperCase()}
          </div>
        ) : (
          <>
            <button
              onClick={() => onSettle(pick.id, "won")}
              data-testid={`settle-won-${pick.id}`}
              className="flex-1 border border-[#00ff66] text-[#00ff66] font-mono uppercase tracking-widest text-[11px] py-2 hover:bg-[#00ff66] hover:text-[#050505] transition-colors"
            >
              Won
            </button>
            <button
              onClick={() => onSettle(pick.id, "lost")}
              data-testid={`settle-lost-${pick.id}`}
              className="flex-1 border border-[#ff3333] text-[#ff3333] font-mono uppercase tracking-widest text-[11px] py-2 hover:bg-[#ff3333] hover:text-[#050505] transition-colors"
            >
              Lost
            </button>
            <button
              onClick={() => onSettle(pick.id, "void")}
              data-testid={`settle-void-${pick.id}`}
              className="flex-1 border border-[#262626] text-[#a3a3a3] font-mono uppercase tracking-widest text-[11px] py-2 hover:bg-[#1a1a1a] transition-colors"
            >
              Void
            </button>
          </>
        )}
      </div>
    </div>
  );
}
