import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import AppHeader from "@/components/AppHeader";
import EmrizFooter from "@/components/EmrizFooter";
import DailySlip from "@/components/DailySlip";
import PushOptIn from "@/components/PushOptIn";
import UpcomingFixtures from "@/components/UpcomingFixtures";
import ReferralCard from "@/components/ReferralCard";
import { useAuth } from "@/contexts/AuthContext";
import { api } from "@/lib/api";
import { Calendar, Clock, ShieldCheck, BellRing, ChevronRight, History, Sparkles, Trophy, Zap } from "lucide-react";

function SubscriptionBanner({ user }) {
  const status = user.subscription_status;
  const ends = user.subscription_ends_at || user.trial_ends_at;
  const daysLeft = ends ? Math.max(0, Math.ceil((new Date(ends) - new Date()) / (1000 * 60 * 60 * 24))) : 0;
  if (status === "active") {
    return (
      <div className="co-glass rounded-[8px] p-4 flex items-center justify-between gap-4" data-testid="sub-banner-active">
        <div className="flex items-center gap-3">
          <span className="w-10 h-10 rounded-[8px] bg-[#00ff66]/12 grid place-items-center shrink-0">
            <ShieldCheck className="w-5 h-5 text-[#00ff66]" />
          </span>
          <div>
            <div className="font-heading font-bold">Active Subscription</div>
            <div className="font-mono text-[10px] uppercase tracking-widest text-[#667482]">
              {daysLeft} day{daysLeft === 1 ? "" : "s"} remaining · renews {new Date(ends).toLocaleDateString()}
            </div>
          </div>
        </div>
        <Link to="/subscription" className="font-mono text-[10px] uppercase tracking-widest text-[#aeb8c2] hover:text-[#00ff66] inline-flex items-center gap-1">Manage <ChevronRight className="w-3 h-3"/></Link>
      </div>
    );
  }
  if (status === "trial") {
    return (
      <div className="co-soft-band rounded-[8px] p-4 flex items-center justify-between gap-4 border-[#00ff66]" data-testid="sub-banner-trial">
        <div className="flex items-center gap-3">
          <span className="w-10 h-10 rounded-[8px] bg-[#00ff66]/14 grid place-items-center shrink-0">
            <Clock className="w-5 h-5 text-[#00ff66]" />
          </span>
          <div>
            <div className="font-heading font-bold">Free Trial Active</div>
            <div className="font-mono text-[10px] uppercase tracking-widest text-[#667482]">{daysLeft} day{daysLeft === 1 ? "" : "s"} remaining</div>
          </div>
        </div>
        <Link to="/subscription" data-testid="upgrade-cta" className="co-primary-action rounded-[6px] font-mono uppercase tracking-widest text-[11px] px-4 py-3">Upgrade</Link>
      </div>
    );
  }
  return (
    <div className="co-card p-4 flex items-center justify-between gap-4 border-[#ff3333]" data-testid="sub-banner-expired">
      <div className="flex items-center gap-3">
        <span className="w-10 h-10 rounded-[8px] bg-[#ff3333]/12 grid place-items-center shrink-0">
          <Calendar className="w-5 h-5 text-[#ff3333]" />
        </span>
        <div>
          <div className="font-heading font-bold">Subscription Inactive</div>
          <div className="font-mono text-[10px] uppercase tracking-widest text-[#667482]">Subscribe to unlock daily slips</div>
        </div>
      </div>
      <Link to="/subscription" data-testid="subscribe-cta" className="co-primary-action rounded-[6px] font-mono uppercase tracking-widest text-[11px] px-4 py-3">Subscribe</Link>
    </div>
  );
}

function HeroMetric({ icon: Icon, label, value, tone = "text-[#f5f5f5]" }) {
  return (
    <div className="co-stat-tile p-4">
      <div className="flex items-center justify-between gap-3">
        <span className="font-mono text-[9px] uppercase tracking-widest text-[#667482]">{label}</span>
        <Icon className="w-4 h-4 text-[#48a7ff]" />
      </div>
      <div className={`font-mono text-2xl font-bold mt-4 ${tone}`}>{value}</div>
    </div>
  );
}

export default function Dashboard() {
  const { user } = useAuth();
  const [slip, setSlip] = useState(null);
  const [locked, setLocked] = useState(true);
  const [awaitingData, setAwaitingData] = useState(null);
  const [isTomorrow, setIsTomorrow] = useState(false);
  const [awaitingTomorrow, setAwaitingTomorrow] = useState(null);
  const [slipDate, setSlipDate] = useState("");
  const [history, setHistory] = useState([]);
  const [tab, setTab] = useState("today");
  const [vapid, setVapid] = useState("");

  useEffect(() => {
    api.slipToday().then(d => {
      setSlip(d.slip);
      setLocked(d.locked);
      setIsTomorrow(!!d.is_tomorrow);
      setSlipDate(d.date || "");
      if (d.awaiting_tomorrow) {
        setAwaitingTomorrow({ message: d.message });
      } else {
        setAwaitingTomorrow(null);
      }
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

  const headingLabel = isTomorrow ? "TOMORROW'S COMBINED SLIP" : "TODAY'S COMBINED SLIP";
  const subLabel = awaitingTomorrow
    ? "Today's matches are done — tomorrow's slip coming soon"
    : awaitingData
      ? "Awaiting real intel data"
      : isTomorrow
        ? `${slip?.leg_count || 0} legs · pre-built for ${slipDate}`
        : (slip ? `${slip.leg_count} legs · published by AI ensemble` : "Awaiting today's run…");

  return (
    <div className="co-app-shell text-[#f5f5f5]">
      <AppHeader />
      <main className="max-w-[1300px] mx-auto px-4 sm:px-6 py-5 sm:py-10 space-y-5 sm:space-y-6">
        <section className="co-soft-band rounded-[8px] p-5 sm:p-7 overflow-hidden">
          <div className="flex items-start justify-between gap-4">
            <div className="min-w-0">
              <div className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-black/20 px-3 py-1 font-mono text-[9px] uppercase tracking-widest text-[#aeb8c2]">
                <Sparkles className="w-3 h-3 text-[#00ff66]" /> Live intelligence hub
              </div>
              <h1 className="font-heading font-black text-3xl sm:text-5xl tracking-tight mt-4 leading-none">
                Your betting command center
              </h1>
              <p className="mt-3 max-w-2xl text-sm sm:text-base text-[#aeb8c2] leading-relaxed">
                Daily slip, fixture status, subscription, alerts, and referral rewards are now shaped for phone-first use.
              </p>
            </div>
            <div className="hidden sm:grid w-16 h-16 rounded-[8px] bg-[#00ff66] text-[#050607] place-items-center shrink-0">
              <Zap className="w-8 h-8" />
            </div>
          </div>
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mt-6">
            <HeroMetric icon={Trophy} label="Slip" value={slip ? `${slip.leg_count || 0} legs` : "Pending"} />
            <HeroMetric icon={Zap} label="Odds" value={slip?.combined_odds ? slip.combined_odds.toFixed(2) : (slip?.combined_odds_range || "Locked")} />
            <HeroMetric icon={BellRing} label="Alerts" value={vapid ? "Ready" : "Quiet"} tone={vapid ? "text-[#00ff66]" : "text-[#ffb800]"} />
            <HeroMetric icon={ShieldCheck} label="Access" value={user?.subscription_status || "trial"} />
          </div>
        </section>

        <div className="grid grid-cols-1 lg:grid-cols-[1fr_360px] gap-4 items-start">
          <div className="space-y-4">
            <SubscriptionBanner user={user} />
            <PushOptIn vapidPublicKey={vapid} />
          </div>
          <div className="co-glass rounded-[8px] p-4 hidden lg:block">
            <div className="font-mono text-[10px] uppercase tracking-widest text-[#667482]">Session</div>
            <div className="font-heading font-bold text-lg mt-1 truncate">{user?.email}</div>
            <div className="mt-3 flex items-center gap-2 text-xs text-[#aeb8c2]">
              <span className="w-2 h-2 rounded-full bg-[#00ff66]" />
              Protected PWA session
            </div>
          </div>
        </div>

        <div className="co-native-tabs sticky top-[72px] z-20 backdrop-blur-xl">
          {[
            { id: "today", label: "Slip", Icon: Zap },
            { id: "history", label: "History", Icon: History },
          ].map(t => (
            <button key={t.id} onClick={() => setTab(t.id)} data-testid={`dash-tab-${t.id}`}
                    className={`co-native-tab font-mono uppercase tracking-widest text-[11px] px-5 py-3 transition-colors whitespace-nowrap inline-flex items-center justify-center gap-2 ${
                      tab === t.id ? "bg-[#00ff66] text-[#050607]" : "text-[#aeb8c2] hover:bg-white/5 hover:text-[#f5f5f5]"
                    }`}>
              <t.Icon className="w-4 h-4" />
              {t.label}
            </button>
          ))}
        </div>

        {tab === "today" && (
          <div>
            <div className="flex items-center gap-3 flex-wrap mb-2">
              <h1 className="font-heading font-black text-2xl sm:text-3xl tracking-tight">{headingLabel}</h1>
              {isTomorrow && !awaitingTomorrow && (
                <span data-testid="tomorrow-badge" className="px-2 py-1 bg-[#00ff66] text-[#050607] font-mono text-[10px] uppercase tracking-widest font-bold rounded-full">
                  Next-day rollover
                </span>
              )}
            </div>
            <p className="font-mono text-[10px] uppercase tracking-widest text-[#667482] mb-5 sm:mb-6">
              {subLabel}
            </p>
            {awaitingTomorrow ? (
              <div className="co-card p-6 sm:p-8 border-l-4 border-l-[#00ff66]" data-testid="awaiting-tomorrow-card">
                <div className="font-heading font-bold text-lg mb-2">Today's slate is finished</div>
                <p className="text-sm text-[#a3a3a3] leading-relaxed mb-3">{awaitingTomorrow.message}</p>
                <div className="font-mono text-[10px] uppercase tracking-widest text-[#525252]">
                  // The next AI ensemble run is scheduled — check back in a few minutes.
                </div>
              </div>
            ) : awaitingData ? (
              <div className="co-card p-6 sm:p-8 border-l-4 border-l-[#ffb800]" data-testid="awaiting-data-card">
                <div className="font-heading font-bold text-lg mb-2">No slip {isTomorrow ? "tomorrow" : "today"} — awaiting real data</div>
                <p className="text-sm text-[#a3a3a3] leading-relaxed mb-3">{awaitingData.message}</p>
                <div className="font-mono text-[10px] uppercase tracking-widest text-[#525252]">
                  // data richness: {Math.round((awaitingData.richness || 0) * 100)}% · minimum required: {Math.round((awaitingData.min_required || 0) * 100)}%
                </div>
                <p className="text-xs text-[#525252] mt-4 leading-relaxed">
                  We refuse to ship slips that aren't backed by real injury / form / head-to-head data — that's how we keep your win-rate honest. Check back later.
                </p>
              </div>
            ) : (
              <DailySlip slip={slip} locked={locked} onSubscribe={locked ? () => (window.location.href = "/subscription") : null} />
            )}

            {/* Live fixture schedule — never empty, even before odds arrive */}
            <div className="mt-8" id="fixtures">
              <UpcomingFixtures />
            </div>

            {/* Refer-a-friend — get more trial / sub days */}
            <div className="mt-8">
              <ReferralCard />
            </div>
          </div>
        )}

        {tab === "history" && (
          <div className="space-y-5 sm:space-y-6">
            <div className="flex items-center justify-between flex-wrap gap-3">
              <h1 className="font-heading font-black text-2xl sm:text-3xl tracking-tight">SLIP HISTORY</h1>
              {history.length > 0 && history[0]?.locked && (
                <Link to="/subscription" data-testid="history-unlock-cta"
                      className="bg-[#00ff66] text-[#050505] font-mono uppercase tracking-widest text-[11px] px-4 py-2 hover:bg-[#f5f5f5]">
                  Subscribe to see the picks →
                </Link>
              )}
            </div>
            {history.length > 0 && history[0]?.locked && (
              <div className="co-card p-4 border-l-4 border-l-[#ffb800]" data-testid="history-locked-banner">
                <p className="text-sm text-[#a3a3a3] leading-relaxed">
                  Your subscription is inactive. These are the slips you missed — odds and win/loss are real, picks are blurred.
                  <span className="text-[#f5f5f5] font-bold"> Resubscribe to stop missing out.</span>
                </p>
              </div>
            )}
            {history.length === 0 ? (
              <div className="co-card p-12 text-center font-mono text-[10px] uppercase tracking-widest text-[#525252]">
                No history yet
              </div>
            ) : history.map(s => {
              const won = s.status_summary?.won || 0;
              const lost = s.status_summary?.lost || 0;
              const pending = s.status_summary?.pending || 0;
              const allWon = lost === 0 && pending === 0 && won > 0;
              return (
                <div key={s.date} className="co-card p-5" data-testid={`hist-slip-${s.date}`}>
                  <div className="flex items-center justify-between mb-3 flex-wrap gap-2">
                    <div>
                      <div className="font-mono text-[10px] uppercase tracking-widest text-[#525252]">{s.date}</div>
                      <div className="font-heading font-bold">
                        {s.leg_count}-leg @ {s.combined_odds?.toFixed(2)}
                        {allWon && <span className="ml-2 px-2 py-0.5 bg-[#00ff66] text-[#050505] font-mono text-[10px] uppercase tracking-widest font-bold">CASHED</span>}
                      </div>
                    </div>
                    <div className="flex items-center gap-2 flex-wrap">
                      {won > 0 && <span className="co-tag co-tag-pos">{won} W</span>}
                      {lost > 0 && <span className="co-tag co-tag-neg">{lost} L</span>}
                      {s.status_summary?.void > 0 && <span className="co-tag">{s.status_summary.void} V</span>}
                      {pending > 0 && <span className="co-tag co-tag-warn">{pending} P</span>}
                    </div>
                  </div>
                  {s.locked && s.legs?.length > 0 && (
                    <div className="border-t border-[#1a1a1a] pt-3 mt-2 space-y-2">
                      {s.legs.map((l, i) => {
                        const map = { won: ["bg-[#00ff66] text-[#050505]", "✓ WON"], lost: ["bg-[#ff3333] text-[#f5f5f5]", "✗ LOST"], void: ["bg-[#525252] text-[#f5f5f5]", "VOID"], pending: ["bg-[#ffb800] text-[#050505]", "PENDING"] };
                        const [pillCls, pillLabel] = map[l.status] || map.pending;
                        return (
                          <div key={`${s.date}-leg-${i}`} className="flex items-center gap-3">
                            <span className="font-mono text-[10px] text-[#525252] uppercase w-6 shrink-0">{String(i + 1).padStart(2, "0")}</span>
                            <span className="font-mono text-[10px] uppercase tracking-widest text-[#a3a3a3] w-16 shrink-0">{l.sport}</span>
                            <span className="font-mono text-xs text-[#525252] blur-sm select-none flex-1">████████ pick</span>
                            <span className="font-mono text-sm text-[#f5f5f5] w-12 text-right">{l.odds?.toFixed(2)}</span>
                            <span className={`font-mono text-[9px] uppercase tracking-widest font-bold px-2 py-0.5 ${pillCls} w-16 text-center`}>{pillLabel}</span>
                          </div>
                        );
                      })}
                    </div>
                  )}
                  <div className="text-xs text-[#a3a3a3] font-mono mt-3">{s.summary}</div>
                </div>
              );
            })}
          </div>
        )}
      </main>
      <EmrizFooter />
    </div>
  );
}
