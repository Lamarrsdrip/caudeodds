import React from "react";

export default function EmrizFooter() {
  return (
    <footer className="px-6 py-10 text-center space-y-3 border-t border-[#262626] mt-12" data-testid="emriz-footer">
      <div className="font-mono text-[10px] uppercase tracking-widest text-[#525252]">
        © 2026 ClaudeOdd · 18+ only · Bet responsibly · Not affiliated with SportyBet
      </div>
      <a
        href="https://twitter.com/emriz_eth"
        target="_blank"
        rel="noopener noreferrer"
        data-testid="emriz-credit"
        className="inline-block group"
      >
        <div className="emriz-glow inline-flex items-center gap-2 px-5 py-2 border border-[#00ff66] text-[#00ff66] font-mono text-xs uppercase tracking-widest hover:bg-[#00ff66] hover:text-[#050505] transition-all">
          <span className="w-1.5 h-1.5 bg-[#00ff66] rounded-full co-pulse group-hover:bg-[#050505]" />
          Made by emriz.eth
        </div>
      </a>
    </footer>
  );
}
