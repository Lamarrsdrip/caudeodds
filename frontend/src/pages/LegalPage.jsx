import React from "react";
import { Link } from "react-router-dom";
import { ArrowLeft, ShieldCheck } from "lucide-react";
import AppHeader from "@/components/AppHeader";
import EmrizFooter from "@/components/EmrizFooter";

const COPY = {
  terms: {
    title: "Terms",
    kicker: "Responsible access rules",
    intro: "ClaudeOdds is a subscription software product that provides sports prediction research, odds context, and betting-slip organization for adults only.",
    sections: [
      ["Adults only", "You must be 18 years or older and legally allowed to bet in your jurisdiction."],
      ["No guaranteed profit", "Predictions are informational. Past results do not guarantee future outcomes, and every user is responsible for their own staking decisions."],
      ["Fair access", "Trials are limited to one device/account so the referral and subscription system remains fair."],
      ["Subscription", "Paid access unlocks daily slips, history, alerts, and booking-code workflow for the active subscription period."],
      ["Account safety", "We may suspend access for abuse, fraud, chargebacks, credential sharing, or attempts to bypass subscription controls."],
    ],
  },
  privacy: {
    title: "Privacy",
    kicker: "How account data is handled",
    intro: "ClaudeOdds keeps the app practical: we collect only what is needed to run accounts, subscriptions, referrals, alerts, and security checks.",
    sections: [
      ["Account data", "We store your name, email, subscription status, referral code, and login activity for account support and security."],
      ["Payments", "Card payments are handled by Flutterwave. Manual bank-transfer receipts are stored so admins can verify access."],
      ["Device checks", "A device fingerprint may be used to reduce free-trial abuse and protect the referral system."],
      ["Notifications", "If you enable push alerts, your browser push subscription is stored so slip updates can reach your device."],
      ["Control", "You can log out, disable push alerts, and contact support to review account access questions."],
    ],
  },
};

export default function LegalPage({ type = "terms" }) {
  const page = COPY[type] || COPY.terms;
  return (
    <div className="co-app-shell text-[#f5f5f5]">
      <AppHeader />
      <main className="mx-auto max-w-3xl px-4 sm:px-6 py-8 sm:py-14 pb-28">
        <Link to="/register" className="inline-flex items-center gap-2 text-[#aeb8c2] hover:text-[#00ff66] font-mono text-[11px] uppercase tracking-widest mb-6">
          <ArrowLeft className="w-4 h-4" /> Back
        </Link>
        <section className="co-glass rounded-[8px] p-5 sm:p-8">
          <span className="w-12 h-12 rounded-[8px] bg-[#00ff66]/12 border border-[#00ff66]/20 grid place-items-center mb-5">
            <ShieldCheck className="w-6 h-6 text-[#00ff66]" />
          </span>
          <div className="font-mono text-[10px] uppercase tracking-widest text-[#667482]">{page.kicker}</div>
          <h1 className="font-heading font-black text-4xl sm:text-5xl tracking-tight mt-2">{page.title}</h1>
          <p className="text-[#aeb8c2] leading-relaxed mt-4">{page.intro}</p>
          <div className="mt-7 space-y-3">
            {page.sections.map(([title, body]) => (
              <div key={title} className="co-card p-4">
                <h2 className="font-heading font-bold text-lg">{title}</h2>
                <p className="text-sm text-[#aeb8c2] leading-relaxed mt-1">{body}</p>
              </div>
            ))}
          </div>
        </section>
      </main>
      <EmrizFooter />
    </div>
  );
}
