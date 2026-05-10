import React from "react";
import PickCard from "./PickCard";
import { TrendingUp } from "lucide-react";

function ParlayBar({ parlay }) {
  if (!parlay || parlay.legs === 0) return null;
  return (
    <div className="co-card p-5 flex items-center justify-between" data-testid="parlay-bar">
      <div className="flex items-center gap-4">
        <TrendingUp className="w-5 h-5 text-[#00ff66]" strokeWidth={2.5} />
        <div>
          <div className="text-[10px] font-mono uppercase tracking-widest text-[#525252]">Daily Combined Slip</div>
          <div className="font-heading font-bold text-base">{parlay.legs}-Fold Accumulator</div>
        </div>
      </div>
      <div className="grid grid-cols-3 gap-8">
        <div>
          <div className="text-[10px] font-mono uppercase tracking-widest text-[#525252]">Total Odds</div>
          <div className="font-mono text-2xl">{parlay.combined_odds?.toFixed(2)}</div>
        </div>
        <div>
          <div className="text-[10px] font-mono uppercase tracking-widest text-[#525252]">EV</div>
          <div className={`font-mono text-2xl ${parlay.expected_value > 0 ? "text-[#00ff66]" : "text-[#ff3333]"}`}>
            {parlay.expected_value > 0 ? "+" : ""}{(parlay.expected_value * 100).toFixed(1)}%
          </div>
        </div>
        <div>
          <div className="text-[10px] font-mono uppercase tracking-widest text-[#525252]">Suggested Stake</div>
          <div className="font-mono text-2xl">${parlay.stake_units?.toFixed(2)}</div>
        </div>
      </div>
    </div>
  );
}

export default function PicksBoard({ picks, parlay, onSettle, generating, lastRun }) {
  return (
    <div className="space-y-6" data-testid="picks-board">
      <div className="flex items-baseline justify-between">
        <div>
          <h2 className="font-heading font-black text-3xl tracking-tight">TODAY'S APPROVED PICKS</h2>
          <p className="text-xs font-mono text-[#525252] uppercase tracking-widest mt-1">
            {generating ? "Running Claude + GPT ensemble…" : picks.length === 0
              ? "No picks yet — run the ensemble to scan today's slate"
              : `${picks.length} high-confidence pick${picks.length === 1 ? "" : "s"} from disciplined ensemble`}
          </p>
        </div>
        {lastRun && (
          <div className="text-right">
            <div className="text-[10px] font-mono uppercase tracking-widest text-[#525252]">Fixtures Analyzed</div>
            <div className="font-mono text-xl">{lastRun.fixtures_analyzed}</div>
            <div className="text-[10px] font-mono text-[#525252] mt-0.5">{lastRun.rejected_count} rejected by filter</div>
          </div>
        )}
      </div>

      <ParlayBar parlay={parlay} />

      {picks.length === 0 ? (
        <div className="co-card p-12 text-center bg-grid">
          <div className="font-mono text-[10px] uppercase tracking-widest text-[#525252] mb-2">EMPTY SLATE</div>
          <div className="font-heading text-lg text-[#a3a3a3]">
            {generating ? "Analyzing fixtures with disciplined filters…" : "Click RUN ENSEMBLE to generate today's high-confidence picks."}
          </div>
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-4">
          {picks.map(p => <PickCard key={p.id} pick={p} onSettle={onSettle} />)}
        </div>
      )}
    </div>
  );
}
