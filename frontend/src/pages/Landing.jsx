import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import AppHeader from "@/components/AppHeader";
import EmrizFooter from "@/components/EmrizFooter";
import PublicRoiTracker from "@/components/PublicRoiTracker";
import { api } from "@/lib/api";
import { BarChart3, BellRing, CheckCircle2, Clipboard, Lock, Radar, Shield, Sparkles, Trophy, Zap } from "lucide-react";

function MiniSlipPreview({ slip }) {
  const legs = slip?.legs?.length ? slip.legs.slice(0, 3) : [
    { sport: "Football", odds: 1.82 },
    { sport: "Basketball", odds: 1.74 },
    { sport: "Football", odds: 1.68 },
  ];

  return (
    <div className="co-glass rounded-[8px] p-4 sm:p-5 w-full max-w-[430px] mx-auto">
      <div className="flex items-center justify-between gap-3 mb-4">
        <div>
          <div className="font-mono text-[9px] uppercase tracking-widest text-[#667482]">Today preview</div>
          <div className="font-heading font-black text-2xl mt-1">
            {slip?.combined_odds ? slip.combined_odds.toFixed(2) : "2.00-5.00"}
          </div>
        </div>
        <span className="co-tag co-tag-pos px-3 py-1">AI slip</span>
      </div>

      <div className="grid grid-cols-3 gap-2 mb-4">
        <div className="co-stat-tile min-h-0 p-3">
          <div className="font-mono text-[8px] uppercase tracking-widest text-[#667482]">Legs</div>
          <div className="font-mono text-xl mt-2">{slip?.leg_count || legs.length}</div>
        </div>
        <div className="co-stat-tile min-h-0 p-3">
          <div className="font-mono text-[8px] uppercase tracking-widest text-[#667482]">Conf</div>
          <div className="font-mono text-xl mt-2">{slip?.combined_confidence ? `${slip.combined_confidence.toFixed(0)}%` : "Live"}</div>
        </div>
        <div className="co-stat-tile min-h-0 p-3">
          <div className="font-mono text-[8px] uppercase tracking-widest text-[#667482]">Risk</div>
          <div className="font-mono text-xl mt-2">{slip?.risk_level || "Med"}</div>
        </div>
      </div>

      <div className="space-y-2">
        {legs.map((leg, i) => (
          <div key={`${leg.sport}-${i}`} className="co-card p-3 flex items-center gap-3">
            <span className="w-8 h-8 rounded-[6px] bg-[#00ff66] text-[#050607] font-mono font-bold text-xs grid place-items-center shrink-0">
              {String(i + 1).padStart(2, "0")}
            </span>
            <div className="flex-1 min-w-0">
              <div className="font-mono text-[9px] uppercase tracking-widest text-[#667482]">{leg.sport}</div>
              <div className="font-heading font-bold blur-sm select-none text-[#aeb8c2]">Locked pick</div>
            </div>
            <div className="font-mono text-lg font-bold">{leg.odds?.toFixed ? leg.odds.toFixed(2) : leg.odds}</div>
          </div>
        ))}
      </div>

      <div className="mt-4 co-soft-band rounded-[8px] p-3 flex items-center justify-between gap-3">
        <div className="font-mono text-[10px] uppercase tracking-widest text-[#aeb8c2]">SportyBet code locked</div>
        <Lock className="w-4 h-4 text-[#00ff66]" />
      </div>
    </div>
  );
}

function FeatureCard({ Icon, title, body }) {
  return (
    <div className="co-card p-5 sm:p-6">
      <span className="w-11 h-11 rounded-[8px] bg-white/5 border border-white/10 grid place-items-center mb-4">
        <Icon className="w-5 h-5 text-[#00ff66]" strokeWidth={1.7} />
      </span>
      <h3 className="font-heading font-bold text-lg mb-2">{title}</h3>
      <p className="text-sm text-[#aeb8c2] leading-relaxed">{body}</p>
    </div>
  );
}

export default function Landing() {
  const [slip, setSlip] = useState(null);
  const [cfg, setCfg] = useState(null);

  useEffect(() => {
    api.slipToday().then(d => setSlip(d.slip)).catch(() => {});
    api.publicConfig().then(setCfg).catch(() => {});
  }, []);

  return (
    <div className="co-app-shell text-[#f5f5f5]">
      <AppHeader />

      <section className="relative overflow-hidden border-b border-white/10">
        <div className="max-w-[1400px] mx-auto px-4 sm:px-6 py-10 sm:py-16 lg:py-20 grid lg:grid-cols-[1fr_460px] gap-8 lg:gap-12 items-center">
          <div className="min-w-0">
            <div className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-black/20 px-3 py-1 font-mono text-[9px] uppercase tracking-widest text-[#aeb8c2]">
              <Sparkles className="w-3 h-3 text-[#00ff66]" />
              Built for SportyBet Nigeria
            </div>
            <h1 className="font-heading font-black text-5xl sm:text-6xl lg:text-7xl tracking-tight leading-none mt-5" data-testid="hero-title">
              AI slips that feel ready before kickoff.
            </h1>
            <p className="text-base sm:text-lg text-[#aeb8c2] max-w-2xl leading-relaxed mt-5">
              ClaudeOdds turns football and basketball data into one daily combined slip, with locked picks, booking-code workflow, push alerts, and a live performance trail.
            </p>
            <div className="flex items-center gap-3 flex-wrap mt-7">
              <Link to="/register" data-testid="cta-trial" className="co-primary-action rounded-[8px] font-mono uppercase tracking-widest text-sm px-6 sm:px-8 py-4">
                Start {cfg?.trial_days ?? 3}-Day Free Trial
              </Link>
              <Link to="/pricing" data-testid="cta-pricing" className="co-secondary-action rounded-[8px] font-mono uppercase tracking-widest text-sm px-6 sm:px-8 py-4">
                See Pricing
              </Link>
            </div>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 mt-8">
              {[
                ["18+", "Adults only"],
                ["2-5x", "Target odds"],
                ["3-5", "Daily legs"],
                ["PWA", "Phone ready"],
              ].map(([value, label]) => (
                <div key={label} className="co-stat-tile min-h-0 p-3">
                  <div className="font-mono text-xl font-bold">{value}</div>
                  <div className="font-mono text-[9px] uppercase tracking-widest text-[#667482] mt-1">{label}</div>
                </div>
              ))}
            </div>
          </div>

          <div className="lg:justify-self-end">
            <MiniSlipPreview slip={slip} />
          </div>
        </div>
      </section>

      <section className="border-b border-white/10">
        <div className="max-w-[1400px] mx-auto px-4 sm:px-6 py-12 sm:py-16">
          <div className="flex items-end justify-between gap-4 flex-wrap mb-6">
            <div>
              <div className="font-mono text-[10px] uppercase tracking-widest text-[#667482] mb-2">Locked preview</div>
              <h2 className="font-heading font-black text-3xl sm:text-4xl tracking-tight">Today at a glance</h2>
            </div>
            <Link to="/register" data-testid="landing-unlock" className="co-primary-action rounded-[8px] font-mono uppercase tracking-widest text-xs px-5 py-3">
              Unlock picks
            </Link>
          </div>

          {!slip ? (
            <div className="co-card p-12 text-center text-[#667482] font-mono text-xs uppercase tracking-widest">
              Awaiting today's ensemble run
            </div>
          ) : (
            <div className="grid lg:grid-cols-[360px_1fr] gap-4" data-testid="landing-slip">
              <div className="co-glass rounded-[8px] p-5">
                <div className="font-mono text-[10px] uppercase tracking-widest text-[#667482]">Combined odds</div>
                <div className="font-heading font-black text-5xl mt-3">{slip.combined_odds?.toFixed(2)}</div>
                <div className="mt-4 flex flex-wrap gap-2">
                  <span className="co-tag">{slip.leg_count} legs</span>
                  <span className="co-tag co-tag-pos">{slip.combined_confidence?.toFixed(0)}% confidence</span>
                  <span className="co-tag co-tag-warn">{slip.risk_level} risk</span>
                </div>
              </div>
              <div className="space-y-2">
                {(slip.legs || []).map((leg, i) => (
                  <div key={`leg-${i}`} className="co-card p-4 flex items-center gap-3">
                    <Lock className="w-4 h-4 text-[#667482] shrink-0" />
                    <span className="font-mono text-[10px] text-[#667482] uppercase w-20 shrink-0">{leg.sport}</span>
                    <div className="font-mono text-xs text-[#667482] blur-sm select-none flex-1">Locked selection</div>
                    <div className="font-mono text-lg text-[#f5f5f5] shrink-0">{leg.odds != null ? leg.odds.toFixed(2) : "Pending"}</div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </section>

      <PublicRoiTracker />

      <section className="border-b border-white/10">
        <div className="max-w-[1400px] mx-auto px-4 sm:px-6 py-12 sm:py-16">
          <div className="mb-8">
            <div className="font-mono text-[10px] uppercase tracking-widest text-[#667482] mb-2">System</div>
            <h2 className="font-heading font-black text-3xl sm:text-4xl tracking-tight">Made for repeated daily use</h2>
          </div>
          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3">
            <FeatureCard Icon={Radar} title="Fixture-first scanning" body="The app watches the schedule before odds land, then marks each game as waiting, analyzing, ready, live, or finished." />
            <FeatureCard Icon={BarChart3} title="Consensus scoring" body="Research, model probability, expected value, market edge, and confidence must agree before a pick becomes slip eligible." />
            <FeatureCard Icon={Clipboard} title="Booking workflow" body="Daily slips are formatted around the SportyBet flow so the locked code, picks, odds, and reasoning live in one place." />
            <FeatureCard Icon={BellRing} title="Push alerts" body="Phone alerts can notify subscribers when the slip or booking code is ready, reducing refresh-checking during match windows." />
            <FeatureCard Icon={Trophy} title="Public track record" body="The homepage shows settled slip results and flat-stake ROI so users can judge performance without screenshots." />
            <FeatureCard Icon={Shield} title="Responsible access" body="The product is subscription-gated, 18+ only, and built around discipline rather than aggressive betting claims." />
          </div>
        </div>
      </section>

      <section className="border-b border-white/10">
        <div className="max-w-[1000px] mx-auto px-4 sm:px-6 py-12 sm:py-16 text-center">
          <span className="mx-auto w-14 h-14 rounded-[8px] bg-[#00ff66] text-[#050607] grid place-items-center mb-5">
            <CheckCircle2 className="w-7 h-7" />
          </span>
          <h2 className="font-heading font-black text-3xl sm:text-4xl tracking-tight mb-4">Start with the trial. Judge the slips.</h2>
          <p className="text-base text-[#aeb8c2] mb-7 leading-relaxed">
            Past performance does not guarantee future results. ClaudeOdds is for adults 18+ and should be used with responsible staking.
          </p>
          <Link to="/register" data-testid="bottom-cta" className="inline-flex co-primary-action rounded-[8px] font-mono uppercase tracking-widest text-sm px-8 py-4">
            Start free trial
          </Link>
        </div>
      </section>

      <footer>
        <EmrizFooter />
      </footer>
    </div>
  );
}
