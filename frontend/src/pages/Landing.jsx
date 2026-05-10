import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import AppHeader from "@/components/AppHeader";
import { api } from "@/lib/api";
import { Lock, TrendingUp, Shield, Zap, BarChart3, Globe } from "lucide-react";

export default function Landing() {
  const [slip, setSlip] = useState(null);
  const [cfg, setCfg] = useState(null);

  useEffect(() => {
    api.slipToday().then(d => setSlip(d.slip)).catch(() => {});
    api.publicConfig().then(setCfg).catch(() => {});
  }, []);

  return (
    <div className="min-h-screen bg-[#050505] text-[#f5f5f5]">
      <AppHeader />

      {/* Hero */}
      <section className="relative bg-grid border-b border-[#262626]">
        <div className="max-w-[1400px] mx-auto px-6 py-24">
          <div className="font-mono text-[10px] uppercase tracking-widest text-[#525252] mb-6">
            // Two AIs · One winning slip every day · Built for SportyBet Nigeria
          </div>
          <h1 className="font-heading font-black text-5xl sm:text-6xl lg:text-7xl tracking-tighter leading-none mb-8" data-testid="hero-title">
            WIN MORE.<br/>
            <span className="text-[#00ff66]">BET SMARTER.</span><br/>
            DAILY.
          </h1>
          <p className="text-lg text-[#a3a3a3] max-w-2xl leading-relaxed mb-10">
            ClaudeOdd combines Claude and GPT into one quant brain. Every day we hand-pick 3–5
            highest-confidence football and basketball games and pack them into one combined slip
            with total odds between <span className="text-[#f5f5f5] font-bold">2.00 and 5.00</span>.
            Easy to play. Easy to copy onto SportyBet. Designed to win.
          </p>
          <div className="flex items-center gap-4 flex-wrap">
            <Link to="/register" data-testid="cta-trial" className="bg-[#00ff66] text-[#050505] font-mono uppercase tracking-widest text-sm px-8 py-4 hover:bg-[#f5f5f5] transition-colors">
              Start {cfg?.trial_days ?? 3}-Day Free Trial →
            </Link>
            <Link to="/pricing" data-testid="cta-pricing" className="border border-[#262626] hover:border-[#525252] font-mono uppercase tracking-widest text-sm px-8 py-4 transition-colors">
              See Pricing
            </Link>
          </div>
          <div className="mt-12 flex flex-wrap gap-6 font-mono text-[11px] uppercase tracking-widest text-[#525252]">
            <span>// 18+ only</span>
            <span>// SportyBet booking codes</span>
            <span>// Football + Basketball mix</span>
            <span>// Cancel anytime</span>
          </div>
        </div>
      </section>

      {/* Today's slip preview (locked) */}
      <section className="border-b border-[#262626]">
        <div className="max-w-[1400px] mx-auto px-6 py-20">
          <h2 className="font-heading font-black text-3xl tracking-tight mb-2">TODAY'S SLIP — TEASER</h2>
          <p className="text-sm text-[#a3a3a3] font-mono mb-8">Subscribe to unlock the picks, the SportyBet booking code, and the full reasoning.</p>
          {!slip ? (
            <div className="co-card p-12 text-center text-[#525252] font-mono text-xs uppercase tracking-widest">
              Awaiting today's ensemble run…
            </div>
          ) : (
            <div className="co-card p-6 relative" data-testid="landing-slip">
              <div className="grid grid-cols-2 md:grid-cols-4 gap-px bg-[#262626] border border-[#262626] mb-6">
                {[
                  ["Legs", slip.leg_count],
                  ["Combined Odds", slip.combined_odds?.toFixed(2)],
                  ["Confidence", `${slip.combined_confidence?.toFixed(0)}%`],
                  ["Risk", slip.risk_level],
                ].map(([k, v]) => (
                  <div key={k} className="bg-[#121212] p-4">
                    <div className="text-[10px] font-mono uppercase tracking-widest text-[#525252]">{k}</div>
                    <div className="font-mono text-2xl mt-1">{v}</div>
                  </div>
                ))}
              </div>
              <div className="space-y-px bg-[#262626] border border-[#262626]">
                {(slip.legs || []).map((l, i) => (
                  <div key={i} className="bg-[#121212] p-4 flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <Lock className="w-4 h-4 text-[#525252]" />
                      <span className="font-mono text-[10px] text-[#525252] uppercase">{l.sport} · {l.league}</span>
                    </div>
                    <div className="font-mono text-xs text-[#525252]">{l.selection_label}</div>
                    <div className="font-mono text-lg text-[#525252]">{l.odds?.toFixed(2)}</div>
                  </div>
                ))}
              </div>
              <div className="mt-6 flex items-center justify-between">
                <div className="font-mono text-[10px] uppercase tracking-widest text-[#525252]">SportyBet code: 🔒 SB-XXXXXX-XXXX</div>
                <Link to="/register" data-testid="landing-unlock" className="bg-[#00ff66] text-[#050505] font-mono uppercase tracking-widest text-xs px-6 py-3">
                  Unlock with Free Trial →
                </Link>
              </div>
            </div>
          )}
        </div>
      </section>

      {/* Features */}
      <section className="border-b border-[#262626]">
        <div className="max-w-[1400px] mx-auto px-6 py-20">
          <h2 className="font-heading font-black text-3xl tracking-tight mb-12">HOW IT WORKS</h2>
          <div className="grid md:grid-cols-3 gap-px bg-[#262626] border border-[#262626]">
            {[
              { Icon: BarChart3, title: "1. Ingest the Slate", body: "Live odds, line movement, sharp money %, public bias, injuries, xG, pace, fatigue, weather, referee tendency." },
              { Icon: Zap, title: "2. Dual AI Ensemble", body: "GPT‑4o‑mini runs the quant analysis. Claude Haiku 4.5 runs the tactical review. Both must agree on the side direction." },
              { Icon: Shield, title: "3. Discipline Filter", body: "We reject low‑liquidity, suspicious moves, hyped public traps, narrative risk, and EV‑negative bets — even if you'd love them." },
              { Icon: TrendingUp, title: "4. One Combined Slip", body: "2–5 legs, multiplied odds, ensemble confidence, expected value. If the bar isn't met, no slip is published." },
              { Icon: Globe, title: "5. SportyBet Ready", body: "Decimal odds, NGN-friendly format, copyable SportyBet booking code, deep-link to open the platform." },
              { Icon: Lock, title: "6. Subscriber‑Only", body: "3-day free trial. ₦5,000/month or local bank transfer. Cancel anytime. Admin reviews bank proofs same day." },
            ].map((f, i) => (
              <div key={i} className="bg-[#121212] p-8">
                <f.Icon className="w-6 h-6 text-[#00ff66] mb-4" strokeWidth={1.5} />
                <h3 className="font-heading font-bold text-lg mb-2">{f.title}</h3>
                <p className="text-sm text-[#a3a3a3] leading-relaxed">{f.body}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Compliance + CTA */}
      <section className="border-b border-[#262626] bg-grid">
        <div className="max-w-[1000px] mx-auto px-6 py-20 text-center">
          <h2 className="font-heading font-black text-3xl tracking-tight mb-6">RESPONSIBLE BY DESIGN</h2>
          <p className="text-base text-[#a3a3a3] mb-8 leading-relaxed">
            CLAUDEODD is for adults 18+. Nothing here is financial or betting advice. Past performance doesn't guarantee future results.
            We optimise for long-term discipline, not viral win-rate marketing.
          </p>
          <Link to="/register" data-testid="bottom-cta" className="inline-block bg-[#00ff66] text-[#050505] font-mono uppercase tracking-widest text-sm px-10 py-4">
            Start your free trial
          </Link>
        </div>
      </section>

      <footer className="px-6 py-8 text-center font-mono text-[10px] uppercase tracking-widest text-[#525252]">
        © 2026 CLAUDEODD · 18+ only · Bet responsibly · Not affiliated with SportyBet
      </footer>
    </div>
  );
}
