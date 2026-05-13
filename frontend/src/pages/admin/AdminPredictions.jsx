import React, { useEffect, useState } from "react";
import { api, formatApiError } from "@/lib/api";
import { toast } from "sonner";

export default function AdminPredictions() {
  const [preds, setPreds] = useState([]);
  const [busy, setBusy] = useState(false);
  const [code, setCode] = useState("");
  const [savedCode, setSavedCode] = useState("");
  const [savingCode, setSavingCode] = useState(false);
  const [dateFilter, setDateFilter] = useState("all"); // "all" | "today" | "tomorrow"

  const todayISO = new Date().toISOString().slice(0, 10);
  const tomorrowISO = new Date(Date.now() + 86400000).toISOString().slice(0, 10);

  const refresh = () => api.adminPredictions().then(setPreds);
  const refreshCode = () => api.adminGetSlipCode().then(d => { setCode(d.code || ""); setSavedCode(d.code || ""); }).catch(() => {});
  useEffect(() => { refresh(); refreshCode(); }, []);

  const filteredPreds = preds.filter(p => {
    if (dateFilter === "today") return p.date === todayISO;
    if (dateFilter === "tomorrow") return p.date === tomorrowISO;
    return true;
  });
  const tomorrowCount = preds.filter(p => p.date === tomorrowISO).length;
  const todayCount = preds.filter(p => p.date === todayISO).length;

  const settle = async (id, result) => {
    try { await api.adminSettle(id, result); toast.success(`Marked ${result}`); refresh(); }
    catch (e) { toast.error(formatApiError(e)); }
  };

  const generate = async (force, date = "today") => {
    setBusy(true);
    try {
      // For tomorrow pre-gen we ALWAYS force so the admin can re-run the pipeline
      // even if a previous (perhaps empty) run is cached — bookmakers post tomorrow's
      // lines progressively through the day.
      const useForce = date === "tomorrow" ? true : force;
      const r = await api.adminGenerate(useForce, date);
      if (r.status === "completed" || r.cached) {
        const picks = r.picks ?? 0;
        const fx = r.fixtures_analyzed ?? 0;
        if (picks === 0 && fx === 0 && date === "tomorrow") {
          toast.warning(`No fixtures yet for tomorrow (${r.date}). Bookmakers usually post tomorrow's lines after 18:00 UTC — try again later.`, { duration: 8000 });
        } else if (picks === 0) {
          toast.warning(`Pipeline ran · 0 picks from ${fx} fixtures (${r.date}). All rejected by EV/quality gate.`, { duration: 6000 });
        } else {
          toast.success(`Done. ${r.cached ? "Cached" : "Generated"} for ${r.date} · picks: ${picks} · fixtures analyzed: ${fx}`);
        }
        refresh();
        setBusy(false);
        return;
      }
      if (r.status === "running" && r.job_id) {
        toast.info("AI ensemble running on real fixtures — this takes 1-3 minutes…");
        // Poll every 4 seconds, max 5 minutes
        const jobId = r.job_id;
        for (let i = 0; i < 75; i++) {
          await new Promise(res => setTimeout(res, 4000));
          try {
            const st = await api.adminGenerateStatus(jobId);
            if (st.status === "completed") {
              const stPicks = st.picks ?? 0;
              const stFx = st.fixtures_analyzed ?? 0;
              if (st.kept_old) {
                toast.warning(`Re-run produced 0 picks — KEPT existing slip intact (no destruction). Odds API may be rate-limited; try again in a few minutes.`, { duration: 8000 });
              } else if (stPicks === 0 && stFx === 0 && date === "tomorrow") {
                toast.warning(`No fixtures yet for tomorrow. Bookmakers usually post tomorrow's lines after 18:00 UTC — try again later.`, { duration: 8000 });
              } else if (stPicks === 0) {
                toast.warning(`Pipeline finished · 0 picks from ${stFx} fixtures. All rejected by EV/quality gate.`, { duration: 6000 });
              } else {
                toast.success(`Generated · picks: ${stPicks} · fixtures analyzed: ${stFx} · rejected: ${st.rejected ?? 0}`);
              }
              refresh();
              setBusy(false);
              return;
            }
            if (st.status === "failed") {
              toast.error(`Pipeline failed: ${st.error || "unknown error"}`);
              setBusy(false);
              return;
            }
          } catch (e) {
            // Polling error is recoverable — log for diagnostics, then keep polling
            console.warn("Pipeline status poll failed (will retry):", e?.message || e);
          }
        }
        toast.error("Generation timed out after 5 minutes — check backend logs.");
      }
    } catch (e) { toast.error(formatApiError(e)); }
    finally { setBusy(false); }
  };

  const saveCode = async () => {
    const c = code.trim().toUpperCase();
    if (c && !/^[A-Z0-9]{3,12}$/.test(c)) {
      toast.error("Code must be 3-12 letters/numbers");
      return;
    }
    setSavingCode(true);
    try {
      await api.adminSetSlipCode(c);
      setSavedCode(c);
      toast.success(c ? `SportyBet code "${c}" published to subscribers` : "SportyBet code cleared");
    } catch (e) { toast.error(formatApiError(e)); }
    finally { setSavingCode(false); }
  };

  const runHeal = async () => {
    setBusy(true);
    try {
      const r = await api.adminScheduleHeal();
      const a = r.mistagged_dropped ?? 0;
      const b = r.orphans_reset ?? 0;
      if (a === 0 && b === 0) {
        toast.success("No bad data found — predictions are clean.");
      } else {
        toast.success(`Healed · dropped ${a} mistagged pick${a === 1 ? "" : "s"}, reset ${b} orphan schedule entr${b === 1 ? "y" : "ies"}. Next 15-min cron will rebuild missing picks; or click Force Re-Generate now.`, { duration: 9000 });
      }
      // Also kick a schedule sync so the rebuild starts immediately
      await api.adminScheduleSync().catch(() => {});
      refresh();
    } catch (e) {
      toast.error(formatApiError(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-6" data-testid="admin-predictions-view">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <h1 className="font-heading font-black text-2xl sm:text-3xl tracking-tight">PREDICTIONS</h1>
        <div className="flex items-center gap-2 flex-wrap">
          <button onClick={() => generate(false)} disabled={busy} data-testid="generate-cached-btn" className="bg-[#00ff66] text-[#050505] font-mono text-xs uppercase tracking-widest px-4 py-2 hover:bg-[#f5f5f5] disabled:opacity-50 flex-1 sm:flex-none" title="RECOMMENDED — runs AI ensemble on today's fixture pool. Append-only; existing picks are preserved.">
            {busy ? "Running…" : "Run Daily Ensemble"}
          </button>
          <button
            onClick={() => {
              if (!window.confirm("⚠️ Force Re-Generate is a DEBUG action.\n\nIt re-runs the AI ensemble on every fixture for today (including already-analyzed ones). This is append-only — existing picks are NEVER deleted — but it will burn LLM credits.\n\nUse 'Run Daily Ensemble' for normal workflow.\n\nContinue?")) return;
              generate(true);
            }}
            disabled={busy} data-testid="force-regen-btn"
            className="border border-[#ff6b35] text-[#ff6b35] hover:bg-[#ff6b35] hover:text-[#050505] font-mono text-xs uppercase tracking-widest px-4 py-2 disabled:opacity-50 flex-1 sm:flex-none"
            title="DEBUG ONLY — re-runs the AI on every fixture. Append-only but burns LLM credits.">
            {busy ? "Running…" : "Force Re-Generate (debug)"}
          </button>
          <button onClick={() => generate(false, "tomorrow")} disabled={busy} data-testid="generate-tomorrow-btn" className="border border-[#00ff66] text-[#00ff66] hover:bg-[#00ff66] hover:text-[#050505] font-mono text-xs uppercase tracking-widest px-4 py-2 disabled:opacity-50 flex-1 sm:flex-none">
            {busy ? "Running…" : "Pre-Gen Tomorrow"}
          </button>
          <button onClick={runHeal} disabled={busy} data-testid="heal-btn" className="border border-[#ff6b35] text-[#ff6b35] hover:bg-[#ff6b35] hover:text-[#050505] font-mono text-xs uppercase tracking-widest px-4 py-2 disabled:opacity-50 flex-1 sm:flex-none" title="Cleans mistagged picks (kickoff != date) and resets orphan 'ready' schedule entries so the cron rebuilds missing picks">
            {busy ? "Running…" : "Heal Bad Data"}
          </button>
        </div>
      </div>

      {/* SportyBet booking code admin input */}
      <div className="co-card p-5" data-testid="admin-sb-code">
        <div className="text-[10px] font-mono uppercase tracking-widest text-[#525252] mb-2">// Today's SportyBet Booking Code</div>
        <p className="text-xs text-[#a3a3a3] mb-4 leading-relaxed">
          Build today's slip on SportyBet using the picks below, copy the booking code SportyBet gives you,
          and paste it here. Subscribers will see the real, working code on their dashboard.
        </p>
        <div className="flex items-center gap-3 flex-wrap">
          <input
            value={code}
            onChange={(e) => setCode(e.target.value.toUpperCase())}
            placeholder="e.g. STQLE2"
            maxLength={12}
            data-testid="sportybet-code-input"
            className="bg-[#0a0a0a] border border-[#262626] focus:border-[#00ff66] outline-none font-mono text-2xl tracking-[0.2em] px-4 py-3 w-64 uppercase"
          />
          <button
            onClick={saveCode}
            disabled={savingCode || code.trim().toUpperCase() === savedCode}
            data-testid="publish-code-btn"
            className="bg-[#00ff66] text-[#050505] font-mono text-xs uppercase tracking-widest px-5 py-3 hover:bg-[#f5f5f5] disabled:opacity-50"
          >
            {savingCode ? "Saving…" : "Publish Code"}
          </button>
          {savedCode && (
            <button
              onClick={() => { setCode(""); }}
              data-testid="clear-code-btn"
              className="border border-[#262626] hover:bg-[#1a1a1a] font-mono text-xs uppercase tracking-widest px-4 py-3"
            >
              Clear
            </button>
          )}
          {savedCode && (
            <span data-testid="live-code-indicator" className="font-mono text-[10px] uppercase tracking-widest text-[#00ff66] inline-flex items-center gap-2">
              ● Live to subscribers: <code className="text-[#f5f5f5]">{savedCode}</code>
            </span>
          )}
          {!savedCode && (
            <span className="font-mono text-[10px] uppercase tracking-widest text-[#a3a3a3]">
              No code set — subscribers see "code being prepared"
            </span>
          )}
        </div>
      </div>

      <div className="co-card overflow-x-auto">
        <div className="flex items-center gap-2 px-3 py-3 border-b border-[#262626] flex-wrap" data-testid="pred-date-filter">
          <span className="font-mono text-[10px] uppercase tracking-widest text-[#525252] mr-2">// Filter</span>
          {[
            { id: "all", label: `All (${preds.length})` },
            { id: "today", label: `Today (${todayCount})` },
            { id: "tomorrow", label: `Tomorrow (${tomorrowCount})` },
          ].map(t => (
            <button key={t.id} onClick={() => setDateFilter(t.id)} data-testid={`pred-filter-${t.id}`}
                    className={`font-mono uppercase tracking-widest text-[10px] px-3 py-1.5 border transition-colors ${
                      dateFilter === t.id
                        ? "bg-[#00ff66] text-[#050505] border-[#00ff66]"
                        : "border-[#262626] text-[#a3a3a3] hover:bg-[#1a1a1a]"
                    }`}>
              {t.label}
            </button>
          ))}
        </div>
        <table className="w-full text-sm">
          <thead><tr className="border-b border-[#262626]">
            {["Date","Sport","Match","Selection","Odds","Conf","EV","Status","Settle"].map(h =>
              <th key={h} className="text-left font-mono text-[10px] uppercase tracking-widest text-[#525252] px-3 py-3">{h}</th>)}
          </tr></thead>
          <tbody>
            {filteredPreds.length === 0 ? <tr><td colSpan={9} className="text-center py-12 text-[#525252] font-mono text-xs uppercase tracking-widest">
              {dateFilter === "tomorrow"
                ? "No tomorrow picks yet — click 'Pre-Gen Tomorrow' (bookmakers post lines progressively through the day)"
                : dateFilter === "today"
                  ? "No today picks yet — click 'Generate' or 'Force Re-Generate'"
                  : "No predictions yet — click Generate"}
            </td></tr> :
              filteredPreds.map(p => (
                <tr key={p.id} className="border-b border-[#1a1a1a]" data-testid={`pred-row-${p.id}`}>
                  <td className="px-3 py-3 font-mono text-xs">{p.date}</td>
                  <td className="px-3 py-3"><span className="co-tag">{p.sport.toUpperCase()}</span></td>
                  <td className="px-3 py-3">{p.match}</td>
                  <td className="px-3 py-3 text-[#a3a3a3]">{p.selection_label}</td>
                  <td className="px-3 py-3 font-mono">{p.odds.toFixed(2)}</td>
                  <td className="px-3 py-3 font-mono">{p.confidence.toFixed(0)}%</td>
                  <td className={`px-3 py-3 font-mono ${p.expected_value > 0 ? "text-[#00ff66]" : "text-[#ff3333]"}`}>{(p.expected_value * 100).toFixed(1)}%</td>
                  <td className="px-3 py-3"><span className={`co-tag ${p.status === "won" ? "co-tag-pos" : p.status === "lost" ? "co-tag-neg" : "co-tag-warn"}`}>{p.status.toUpperCase()}</span></td>
                  <td className="px-3 py-3">
                    {p.status === "pending" ? (
                      <div className="flex gap-1">
                        <button onClick={() => settle(p.id, "won")} data-testid={`settle-w-${p.id}`} className="border border-[#00ff66] text-[#00ff66] font-mono text-[10px] uppercase px-2 py-1 hover:bg-[#00ff66] hover:text-[#050505]">W</button>
                        <button onClick={() => settle(p.id, "lost")} data-testid={`settle-l-${p.id}`} className="border border-[#ff3333] text-[#ff3333] font-mono text-[10px] uppercase px-2 py-1 hover:bg-[#ff3333] hover:text-[#050505]">L</button>
                        <button onClick={() => settle(p.id, "void")} data-testid={`settle-v-${p.id}`} className="border border-[#262626] hover:bg-[#1a1a1a] font-mono text-[10px] uppercase px-2 py-1">V</button>
                      </div>
                    ) : <span className="text-[#525252] font-mono text-[10px]">—</span>}
                  </td>
                </tr>
              ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
