import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import AppHeader from "@/components/AppHeader";
import EmrizFooter from "@/components/EmrizFooter";
import DailySlip from "@/components/DailySlip";
import PushOptIn from "@/components/PushOptIn";
import { useAuth } from "@/contexts/AuthContext";
import { api } from "@/lib/api";
import { Calendar, Clock, ShieldCheck } from "lucide-react";

function SubscriptionBanner({ user }) {
  const status = user.subscription_status;
  const ends = user.subscription_ends_at || user.trial_ends_at;
  const daysLeft = ends ? Math.max(0, Math.ceil((new Date(ends) - new Date()) / (1000 * 60 * 60 * 24))) : 0;
  if (status === "active") {
    return (
      <div className="co-card p-4 flex items-center justify-between" data-testid="sub-banner-active">
        <div className="flex items-center gap-3">
          <ShieldCheck className="w-5 h-5 text-[#00ff66]" />
          <div>
            <div className="font-heading font-bold">Active Subscription</div>
            <div className="font-mono text-[10px] uppercase tracking-widest text-[#525252]">
              {daysLeft} day{daysLeft === 1 ? "" : "s"} remaining · renews {new Date(ends).toLocaleDateString()}
            </div>
          </div>
        </div>
        <Link to="/subscription" className="font-mono text-[10px] uppercase tracking-widest text-[#a3a3a3] hover:text-[#00ff66]">Manage</Link>
      </div>
    );
  }
  if (status === "trial") {
    return (
      <div className="co-card p-4 flex items-center justify-between border-[#00ff66]" data-testid="sub-banner-trial">
        <div className="flex items-center gap-3">
          <Clock className="w-5 h-5 text-[#00ff66]" />
          <div>
            <div className="font-heading font-bold">Free Trial Active</div>
            <div className="font-mono text-[10px] uppercase tracking-widest text-[#525252]">{daysLeft} day{daysLeft === 1 ? "" : "s"} remaining</div>
          </div>
        </div>
        <Link to="/subscription" data-testid="upgrade-cta" className="bg-[#00ff66] text-[#050505] font-mono uppercase tracking-widest text-[11px] px-4 py-2 hover:bg-[#f5f5f5]">Upgrade →</Link>
      </div>
    );
  }
  return (
    <div className="co-card p-4 flex items-center justify-between border-[#ff3333]" data-testid="sub-banner-expired">
      <div className="flex items-center gap-3">
        <Calendar className="w-5 h-5 text-[#ff3333]" />
        <div>
          <div className="font-heading font-bold">Subscription Inactive</div>
          <div className="font-mono text-[10px] uppercase tracking-widest text-[#525252]">Subscribe to unlock daily slips</div>
        </div>
      </div>
      <Link to="/subscription" data-testid="subscribe-cta" className="bg-[#00ff66] text-[#050505] font-mono uppercase tracking-widest text-[11px] px-4 py-2 hover:bg-[#f5f5f5]">Subscribe →</Link>
    </div>
  );
}

export default function Dashboard() {
  const { user } = useAuth();
  const [slip, setSlip] = useState(null);
  const [locked, setLocked] = useState(true);
  const [awaitingData, setAwaitingData] = useState(null);
  const [history, setHistory] = useState([]);
  const [tab, setTab] = useState("today");
  const [vapid, setVapid] = useState("");

  useEffect(() => {
    api.slipToday().then(d => {
      setSlip(d.slip);
      setLocked(d.locked);
      if (d.awaiting_data) {
        setAwaitingData({
          message: d.message,
          richness: d.data_richness,
          min_required: d.min_required,
        });
      } else {
        setAwaitingData(null);
      }
    }).catch(() => {});
    api.slipHistory().then(setHistory).catch(() => setHistory([]));
    api.publicConfig().then(c => setVapid(c.vapid_public_key || "")).catch(() => {});
  }, [user?.subscription_status]);

  return (
    <div className="min-h-screen bg-[#050505] text-[#f5f5f5]">
      <AppHeader />
      <main className="max-w-[1300px] mx-auto px-4 sm:px-6 py-6 sm:py-10 space-y-5 sm:space-y-6">
        <SubscriptionBanner user={user} />
        <PushOptIn vapidPublicKey={vapid} />

        <div className="flex items-center gap-0 border border-[#262626] overflow-x-auto">
          {[
            { id: "today", label: "Today's Slip" },
            { id: "history", label: "History" },
          ].map(t => (
            <button key={t.id} onClick={() => setTab(t.id)} data-testid={`dash-tab-${t.id}`}
                    className={`font-mono uppercase tracking-widest text-[11px] px-5 py-3 border-r border-[#262626] transition-colors whitespace-nowrap ${
                      tab === t.id ? "bg-[#f5f5f5] text-[#050505]" : "text-[#a3a3a3] hover:bg-[#1a1a1a] hover:text-[#f5f5f5]"
                    }`}>
              {t.label}
            </button>
          ))}
        </div>

        {tab === "today" && (
          <div>
            <h1 className="font-heading font-black text-2xl sm:text-3xl tracking-tight mb-2">TODAY'S COMBINED SLIP</h1>
            <p className="font-mono text-[10px] uppercase tracking-widest text-[#525252] mb-5 sm:mb-6">
              // {awaitingData ? "Awaiting real intel data" : (slip ? `${slip.leg_count} legs · published by AI ensemble` : "Awaiting today's run…")}
            </p>
            {awaitingData ? (
              <div className="co-card p-6 sm:p-8 border-l-4 border-l-[#ffb800]" data-testid="awaiting-data-card">
                <div className="font-heading font-bold text-lg mb-2">No slip today — awaiting real data</div>
                <p className="text-sm text-[#a3a3a3] leading-relaxed mb-3">{awaitingData.message}</p>
                <div className="font-mono text-[10px] uppercase tracking-widest text-[#525252]">
                  // data richness today: {Math.round((awaitingData.richness || 0) * 100)}% · minimum required: {Math.round((awaitingData.min_required || 0) * 100)}%
                </div>
                <p className="text-xs text-[#525252] mt-4 leading-relaxed">
                  We refuse to ship slips that aren't backed by real injury / form / head-to-head data — that's how we keep your win-rate honest. Check back later today.
                </p>
              </div>
            ) : (
              <DailySlip slip={slip} locked={locked} onSubscribe={locked ? () => (window.location.href = "/subscription") : null} />
            )}
          </div>
        )}

        {tab === "history" && (
          <div className="space-y-5 sm:space-y-6">
            <h1 className="font-heading font-black text-2xl sm:text-3xl tracking-tight">SLIP HISTORY</h1>
            {history.length === 0 ? (
              <div className="co-card p-12 text-center font-mono text-[10px] uppercase tracking-widest text-[#525252]">
                No history yet
              </div>
            ) : history.map(s => (
              <div key={s.date} className="co-card p-5" data-testid={`hist-slip-${s.date}`}>
                <div className="flex items-center justify-between mb-3 flex-wrap gap-2">
                  <div>
                    <div className="font-mono text-[10px] uppercase tracking-widest text-[#525252]">{s.date}</div>
                    <div className="font-heading font-bold">{s.leg_count}-leg @ {s.combined_odds?.toFixed(2)}</div>
                  </div>
                  <div className="flex items-center gap-2 flex-wrap">
                    {s.status_summary?.won > 0 && <span className="co-tag co-tag-pos">{s.status_summary.won} W</span>}
                    {s.status_summary?.lost > 0 && <span className="co-tag co-tag-neg">{s.status_summary.lost} L</span>}
                    {s.status_summary?.void > 0 && <span className="co-tag">{s.status_summary.void} V</span>}
                    {s.status_summary?.pending > 0 && <span className="co-tag co-tag-warn">{s.status_summary.pending} P</span>}
                  </div>
                </div>
                <div className="text-xs text-[#a3a3a3] font-mono">{s.summary}</div>
              </div>
            ))}
          </div>
        )}
      </main>
      <EmrizFooter />
    </div>
  );
}
