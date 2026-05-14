import React, { useEffect, useState, useCallback } from "react";
import { Clock, Loader2, CheckCircle2, XCircle, AlertCircle, Ban, Radio, Trophy } from "lucide-react";
import { api } from "@/lib/api";

/**
 * UpcomingFixtures
 * ────────────────
 * Fixture-first dashboard panel. Shows match schedule (from API-Football /
 * API-Basketball) regardless of whether bookmaker odds have landed yet, so
 * the dashboard is NEVER empty when matches actually exist.
 *
 * Lifecycle badges:
 *   waiting       → kickoff scheduled, odds not yet posted
 *   analyzing     → odds available, AI ensemble processing
 *   ready         → AI complete, pick exists (slip-eligible)
 *   no_prediction → no pick (odds never arrived OR AI rejected near kickoff)
 *   rejected      → AI ran but rejected (failed quality / EV gates)
 *   live          → match in progress (kicked off, <3h ago)
 *   completed     → match finished (>3h since kickoff)
 *
 * Auto-polls every 2 minutes (visibility-aware) so fixtures flip from
 * waiting → analyzing → ready as bookmakers price them and the AI processes.
 */

const BADGE_MAP = {
  waiting:       { Icon: Clock,         label: "WAITING FOR ODDS", cls: "bg-[#ffb800] text-[#050505]" },
  analyzing:     { Icon: Loader2,       label: "ANALYZING",        cls: "bg-[#3b82f6] text-white", spin: true },
  ready:         { Icon: CheckCircle2,  label: "READY",            cls: "bg-[#00ff66] text-[#050505]" },
  no_prediction: { Icon: Ban,           label: "NO PREDICTION",    cls: "bg-[#525252] text-white" },
  rejected:      { Icon: XCircle,       label: "NO BET",           cls: "bg-[#525252] text-white" },
  failed:        { Icon: AlertCircle,   label: "RETRYING",         cls: "bg-[#ff6b35] text-white" },
  live:          { Icon: Radio,         label: "LIVE",             cls: "bg-[#ff3333] text-white" },
  completed:     { Icon: Trophy,        label: "FINISHED",         cls: "bg-[#262626] text-[#a3a3a3]" },
};

const GROUPS = [
  { key: "upcoming", label: "Upcoming",     badges: ["waiting", "analyzing"] },
  { key: "ready",    label: "Predictions",  badges: ["ready"] },
  { key: "nopred",   label: "No Prediction", badges: ["no_prediction", "rejected", "failed"] },
  { key: "live",     label: "Live Now",     badges: ["live"] },
  { key: "history",  label: "Finished",     badges: ["completed"] },
];

function formatKickoff(iso) {
  if (!iso) return "";
  try {
    const d = new Date(iso);
    return d.toLocaleString(undefined, {
      weekday: "short", month: "short", day: "numeric",
      hour: "2-digit", minute: "2-digit", hour12: false,
    });
  } catch { return iso; }
}

export default function UpcomingFixtures() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [activeDate, setActiveDate] = useState(null);

  const fetchData = useCallback(() => {
    api.scheduleUpcoming()
      .then((d) => {
        setData(d);
        setLoading(false);
        if (!activeDate && d?.schedule?.length) {
          setActiveDate(d.schedule[0].date);
        }
      })
      .catch(() => setLoading(false));
  }, [activeDate]);

  useEffect(() => {
    fetchData();
    // Poll every 2 minutes — schedule changes slowly. Skip when tab is hidden
    // to avoid burning API quota for users who left the dashboard open.
    const tick = () => {
      if (document.visibilityState === "visible") fetchData();
    };
    const id = setInterval(tick, 120_000);
    document.addEventListener("visibilitychange", tick);
    return () => {
      clearInterval(id);
      document.removeEventListener("visibilitychange", tick);
    };
  }, [fetchData]);

  if (loading) {
    return (
      <div className="co-card p-6" data-testid="upcoming-fixtures-loading">
        <div className="font-mono text-[10px] uppercase tracking-widest text-[#667482]">Loading fixture schedule</div>
      </div>
    );
  }

  if (!data?.schedule?.length) return null;
  const totalAcrossDays = data.schedule.reduce((s, d) => s + (d.summary?.total || 0), 0);
  if (totalAcrossDays === 0) return null;

  const activeDay = data.schedule.find(d => d.date === activeDate) || data.schedule[0];

  return (
    <div className="space-y-4" data-testid="upcoming-fixtures">
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div>
          <h2 className="font-heading font-black text-xl sm:text-2xl tracking-tight">UPCOMING FIXTURES</h2>
          <p className="font-mono text-[10px] uppercase tracking-widest text-[#667482] mt-1">
            Live schedule · updates every 15 min · {totalAcrossDays} match{totalAcrossDays === 1 ? "" : "es"} across {data.schedule.length} day{data.schedule.length === 1 ? "" : "s"}
          </p>
        </div>
        <button onClick={fetchData} data-testid="refresh-fixtures-btn" className="co-secondary-action rounded-[6px] font-mono text-[10px] uppercase tracking-widest px-3 py-2 min-h-[40px]">
          Refresh
        </button>
      </div>

      {/* Date tabs */}
      <div className="co-native-tabs overflow-x-auto no-scrollbar" data-testid="fixture-date-tabs">
        {data.schedule.map((d, i) => {
          const dayLabel = i === 0 ? "Today" : i === 1 ? "Tomorrow" : new Date(d.date).toLocaleDateString(undefined, { weekday: "short", month: "short", day: "numeric" });
          const isActive = d.date === activeDay.date;
          return (
            <button key={d.date} onClick={() => setActiveDate(d.date)} data-testid={`fixture-tab-${d.date}`}
                    className={`co-native-tab font-mono uppercase tracking-widest text-[11px] px-4 py-3 whitespace-nowrap transition-colors ${
                      isActive ? "bg-[#00ff66] text-[#050607]" : "text-[#aeb8c2] hover:bg-white/5"
                    }`}>
              {dayLabel} ({d.summary?.total || 0})
            </button>
          );
        })}
      </div>

      {/* Summary chips */}
      <div className="flex items-center gap-2 flex-wrap" data-testid="fixture-summary">
        {activeDay.summary?.ready > 0 && (
          <span className="co-tag co-tag-pos" data-testid="summary-ready">{activeDay.summary.ready} READY</span>
        )}
        {activeDay.summary?.analyzing > 0 && (
          <span className="co-tag co-tag-warn">{activeDay.summary.analyzing} ANALYZING</span>
        )}
        {activeDay.summary?.waiting_odds > 0 && (
          <span className="co-tag co-tag-warn" data-testid="summary-waiting">{activeDay.summary.waiting_odds} WAITING FOR ODDS</span>
        )}
        {activeDay.summary?.live > 0 && (
          <span className="co-tag co-tag-neg" data-testid="summary-live">{activeDay.summary.live} LIVE</span>
        )}
        {activeDay.summary?.no_prediction > 0 && (
          <span className="co-tag">{activeDay.summary.no_prediction} NO PRED</span>
        )}
        {activeDay.summary?.rejected > 0 && (
          <span className="co-tag">{activeDay.summary.rejected} NO-BET</span>
        )}
        {activeDay.summary?.completed > 0 && (
          <span className="co-tag" data-testid="summary-completed">{activeDay.summary.completed} FINISHED</span>
        )}
      </div>

      {/* Grouped fixture sections — separates lifecycle states cleanly */}
      <div className="space-y-6" data-testid="fixture-list">
        {GROUPS.map((group) => {
          const items = activeDay.fixtures.filter((fx) => group.badges.includes(fx.badge));
          if (items.length === 0) return null;
          return (
            <div key={group.key} data-testid={`fixture-group-${group.key}`}>
              <div className="font-mono text-[10px] uppercase tracking-widest text-[#667482] mb-2">
                {group.label} ({items.length})
              </div>
              <div className="space-y-2">
                {items.map((fx) => {
                  const badge = BADGE_MAP[fx.badge] || BADGE_MAP.waiting;
                  const resultBadge = fx.result_status === "won"
                    ? { Icon: CheckCircle2, label: "WIN", cls: "bg-[#00ff66] text-[#050607]" }
                    : fx.result_status === "lost"
                    ? { Icon: XCircle, label: "LOSS", cls: "bg-[#ff3333] text-white" }
                    : fx.result_status === "void"
                    ? { Icon: Ban, label: "VOID", cls: "bg-[#667482] text-white" }
                    : null;
                  return (
                    <div key={fx.id} className="co-card p-4 flex items-center gap-3" data-testid={`fixture-row-${fx.id}`}>
                      <span className={`px-2 py-1 rounded-full font-mono text-[9px] uppercase tracking-widest font-bold inline-flex items-center gap-1.5 shrink-0 ${badge.cls}`}>
                        <badge.Icon className={`w-3 h-3 ${badge.spin ? "animate-spin" : ""}`} />
                        {badge.label}
                      </span>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 flex-wrap">
                          <span className="co-tag">{fx.sport.toUpperCase()}</span>
                          <span className="font-mono text-[10px] uppercase tracking-widest text-[#aeb8c2] truncate">{fx.league}</span>
                          {resultBadge && (
                            <span className={`px-2 py-0.5 rounded-full font-mono text-[9px] uppercase tracking-widest font-bold inline-flex items-center gap-1 ${resultBadge.cls}`} data-testid={`fixture-result-${fx.id}`}>
                              <resultBadge.Icon className="w-3 h-3" />
                              {resultBadge.label}
                            </span>
                          )}
                        </div>
                        <div className="font-heading font-bold text-sm sm:text-base mt-1 truncate">
                          {fx.home} <span className="text-[#667482] font-mono mx-1">vs</span> {fx.away}
                        </div>
                        {fx.no_prediction_reason && (
                          <div className="text-[10px] font-mono uppercase tracking-widest text-[#667482] mt-0.5">
                            Reason: {fx.no_prediction_reason.replace(/_/g, " ")}
                          </div>
                        )}
                      </div>
                      <div className="font-mono text-[10px] uppercase tracking-widest text-[#667482] text-right shrink-0">
                        {formatKickoff(fx.kickoff)}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          );
        })}
        {activeDay.fixtures.length === 0 && (
          <div className="co-card p-8 text-center font-mono text-[10px] uppercase tracking-widest text-[#667482]">
            No fixtures scheduled for {activeDay.date} yet
          </div>
        )}
      </div>

      <p className="text-[10px] font-mono uppercase tracking-widest text-[#667482] leading-relaxed">
        Fixtures appear as soon as the league publishes the schedule. Odds and AI picks arrive progressively from bookmakers; READY fixtures become eligible for today's slip.
      </p>
    </div>
  );
}
