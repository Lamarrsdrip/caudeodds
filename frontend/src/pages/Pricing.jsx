import { Link, useNavigate } from "react-router-dom";
import { useState } from "react";
import { Check } from "lucide-react";
import AppHeader from "@/components/AppHeader";
import EmrizFooter from "@/components/EmrizFooter";
import { api } from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";
import React, { useEffect } from "react";

export default function Pricing() {
  const { user } = useAuth();
  const nav = useNavigate();
  const [cfg, setCfg] = useState(null);
  useEffect(() => { api.publicConfig().then(setCfg); }, []);

  const cta = () => nav(user ? "/subscription" : "/register");
  const price = cfg?.price_ngn ?? 5000;

  const features = [
    "1 combined slip per day · always 2.00–5.00 odds",
    "3–5 highest-confidence games · football + basketball",
    "Claude + GPT must agree before any pick ships",
    "SportyBet booking code · 1-tap copy + open",
    "Decimal NGN odds · designed for SportyBet Nigeria",
    "Slip history with W/L tracking",
    "Cancel anytime, no card details kept",
  ];

  return (
    <div className="min-h-screen bg-[#050505] text-[#f5f5f5]">
      <AppHeader />
      <main className="max-w-4xl mx-auto px-6 py-20">
        <h1 className="font-heading font-black text-5xl tracking-tighter mb-3 text-center">SIMPLE PRICING</h1>
        <p className="text-center font-mono text-[11px] uppercase tracking-widest text-[#525252] mb-16">
          // {cfg?.trial_days ?? 3}-day free trial · No card needed to start
        </p>

        <div className="grid md:grid-cols-2 gap-6">
          {/* Free trial card */}
          <div className="co-card p-8" data-testid="pricing-trial">
            <div className="font-mono text-[10px] uppercase tracking-widest text-[#525252] mb-3">// Try first</div>
            <h2 className="font-heading font-black text-3xl tracking-tight mb-1">FREE TRIAL</h2>
            <div className="font-mono text-5xl font-black mt-4">₦0</div>
            <div className="font-mono text-[10px] uppercase tracking-widest text-[#525252] mt-1">{cfg?.trial_days ?? 3} days · Full access</div>
            <ul className="mt-8 space-y-3 text-sm text-[#a3a3a3]">
              {features.slice(0, 4).map(f => (
                <li key={f} className="flex items-start gap-2"><Check className="w-4 h-4 text-[#00ff66] mt-0.5 shrink-0"/> {f}</li>
              ))}
            </ul>
            <button onClick={cta} data-testid="pricing-trial-cta" className="w-full mt-8 border border-[#262626] hover:border-[#525252] hover:bg-[#1a1a1a] font-mono uppercase tracking-widest text-xs py-3">
              {user ? "Go to Dashboard" : "Start Free Trial →"}
            </button>
          </div>
          {/* Paid card */}
          <div className="co-card p-8 border-[#00ff66]" data-testid="pricing-paid">
            <div className="font-mono text-[10px] uppercase tracking-widest text-[#00ff66] mb-3">// Most popular</div>
            <h2 className="font-heading font-black text-3xl tracking-tight mb-1">{cfg?.plan_label || "VIP MONTHLY"}</h2>
            <div className="font-mono text-5xl font-black mt-4">₦{price.toLocaleString()}</div>
            <div className="font-mono text-[10px] uppercase tracking-widest text-[#525252] mt-1">per month · Cancel anytime</div>
            <ul className="mt-8 space-y-3 text-sm text-[#a3a3a3]">
              {features.map(f => (
                <li key={f} className="flex items-start gap-2"><Check className="w-4 h-4 text-[#00ff66] mt-0.5 shrink-0"/> {f}</li>
              ))}
            </ul>
            <button onClick={cta} data-testid="pricing-paid-cta" className="w-full mt-8 bg-[#00ff66] text-[#050505] font-mono uppercase tracking-widest text-xs py-3 hover:bg-[#f5f5f5]">
              {user ? "Subscribe Now →" : "Get Started →"}
            </button>
          </div>
        </div>

        <div className="mt-16 text-center font-mono text-[10px] uppercase tracking-widest text-[#525252]">
          // Pay with Flutterwave (card / bank / USSD) or local bank transfer (admin verifies same day)
        </div>
      </main>
      <EmrizFooter />
    </div>
  );
}
