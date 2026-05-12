import React, { useEffect, useState } from "react";
import { toast } from "sonner";
import { Activity, RotateCw, Zap, CheckCircle2, XCircle } from "lucide-react";
import { api, formatApiError } from "@/lib/api";

/**
 * Admin → Usage & API Cost Dashboard
 * ──────────────────────────────────
 * Shows API requests remaining, cache health, cost-per-prediction estimates,
 * and the raw API-Basketball diagnostic so you can see exactly what's blocked
 * by your subscription plan.
 */
export default function AdminUsage() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [diag, setDiag] = useState(null);
  const [diagLoading, setDiagLoading] = useState(false);

  const refresh = () => {
    setLoading(true);
    api.adminUsage().then(d => { setData(d); setLoading(false); }).catch(e => {
      toast.error(formatApiError(e)); setLoading(false);
    });
  };
  useEffect(() => { refresh(); }, []);

  const runDiag = async () => {
    setDiagLoading(true);
    try {
      const d = await api.adminApiBasketballDiagnostic();
      setDiag(d);
    } catch (e) { toast.error(formatApiError(e)); }
    finally { setDiagLoading(false); }
  };

  return (
    <div className="space-y-6" data-testid="admin-usage-view">
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div className="flex items-center gap-3">
          <Zap className="w-6 h-6 text-[#00ff66]" />
          <h1 className="font-heading font-black text-2xl sm:text-3xl tracking-tight">USAGE & API COST</h1>
        </div>
        <button onClick={refresh} data-testid="usage-refresh-btn" className="border border-[#262626] hover:bg-[#1a1a1a] font-mono text-xs uppercase tracking-widest px-3 py-2 inline-flex items-center gap-2">
          <RotateCw className="w-3.5 h-3.5" />
          Refresh
        </button>
      </div>

      <p className="text-sm text-[#a3a3a3] max-w-2xl">
        Monitor API spend, cache effectiveness, and prediction cost-per-pick. Aggressive caching
        is enabled by default (Odds API: 60-min off-peak, 15-min peak; API-Football: per-resource
        12h–7d). With 30-min fixture-sync + visibility-aware frontend polling, typical Odds API
        burn is <strong>~50 req/day</strong> on a quiet day.
      </p>

      {/* Cost summary */}
      {loading ? (
        <div className="co-card p-6 font-mono text-xs uppercase tracking-widest text-[#525252]">// loading usage…</div>
      ) : data && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3" data-testid="usage-kpis">
          {[
            { k: "Odds-API Remaining", v: data.odds_api?.remaining_requests ?? "—", note: "free tier=500/mo" },
            { k: "Odds Cache Entries", v: data.odds_api?.cache_entries ?? 0, note: `${(data.odds_api?.cache_ttl_offpeak_secs ?? 3600) / 60}min TTL` },
            { k: "LLM Cache Hits Saved", v: data.llm_ensemble_cache_entries ?? 0, note: `24h TTL · 3 calls/fixture` },
            { k: "Picks Last 7d", v: data.picks_generated_7d ?? 0, note: `${data.fixture_sync_runs_24h ?? 0} cron runs / 24h` },
          ].map(({ k, v, note }) => (
            <div key={k} className="co-card p-4">
              <div className="text-[10px] font-mono uppercase tracking-widest text-[#525252]">{k}</div>
              <div className="font-mono text-2xl font-bold mt-1 text-[#f5f5f5]">{v}</div>
              <div className="text-[10px] font-mono uppercase tracking-widest text-[#525252] mt-1">{note}</div>
            </div>
          ))}
        </div>
      )}

      {data?.budget_advice && (
        <div className="co-card p-4 border-l-4 border-l-[#00ff66] bg-[#00ff66]/5" data-testid="budget-advice">
          <div className="font-mono text-[10px] uppercase tracking-widest text-[#00ff66] font-bold mb-1">// budget advice</div>
          <p className="text-sm text-[#a3a3a3] leading-relaxed">{data.budget_advice}</p>
        </div>
      )}

      {/* Basketball diagnostic */}
      <div className="co-card p-5 space-y-3" data-testid="basketball-diag-card">
        <div className="flex items-center justify-between gap-2 flex-wrap">
          <div className="flex items-center gap-2">
            <Activity className="w-4 h-4 text-[#00ff66]" />
            <div className="font-heading font-bold">API-Basketball Raw Diagnostic</div>
          </div>
          <button onClick={runDiag} disabled={diagLoading} data-testid="run-basketball-diag" className="bg-[#00ff66] text-[#050505] font-mono text-xs uppercase tracking-widest px-3 py-2 disabled:opacity-50">
            {diagLoading ? "Running…" : "Run Diagnostic"}
          </button>
        </div>
        <p className="text-xs text-[#525252] leading-relaxed">
          Hits <code>/status</code>, <code>/timezone</code>, <code>/seasons</code>, <code>/leagues</code>, <code>/teams</code>, <code>/games</code> with your stored API key and shows the
          LITERAL provider response (status code, headers, errors, results count). If the active
          season is blocked by your plan, the response from <code>/teams?season=2025-2026</code> will
          say so verbatim.
        </p>
        {diag && (
          <div className="space-y-3" data-testid="basketball-diag-results">
            <div className="flex items-center gap-2 flex-wrap text-xs font-mono">
              <span className="co-tag">season: {diag.season_under_test}</span>
              <span className="co-tag">key: {diag.key_preview}</span>
              <span className={`co-tag ${diag.ok ? "co-tag-pos" : "co-tag-neg"}`}>{diag.ok ? "OK" : "FAIL"}</span>
              {diag.error && <span className="text-[#ff3333] text-xs">{diag.error}</span>}
            </div>
            {diag.endpoints && Object.entries(diag.endpoints).map(([path, info]) => {
              const ok = info?.status_code && info.status_code < 400 && !info.errors;
              return (
                <div key={path} className="border border-[#262626] p-3">
                  <div className="flex items-center gap-2 mb-1 flex-wrap">
                    {ok ? <CheckCircle2 className="w-3.5 h-3.5 text-[#00ff66]" /> : <XCircle className="w-3.5 h-3.5 text-[#ff3333]" />}
                    <span className="font-mono text-xs font-bold">{path}</span>
                    {info.params && <span className="text-[10px] font-mono text-[#525252]">{JSON.stringify(info.params)}</span>}
                    <span className="text-[10px] font-mono text-[#525252] ml-auto">status: {info.status_code}</span>
                    {info.results_count !== null && info.results_count !== undefined && (
                      <span className="text-[10px] font-mono text-[#525252]">results: {info.results_count}</span>
                    )}
                  </div>
                  {info.errors && (
                    <div className="text-xs text-[#ff3333] font-mono mt-1 break-all">
                      errors: {typeof info.errors === "object" ? JSON.stringify(info.errors) : info.errors}
                    </div>
                  )}
                  {info.sample && (
                    <pre className="text-[10px] text-[#a3a3a3] mt-1 overflow-x-auto whitespace-pre-wrap">{JSON.stringify(info.sample, null, 2).slice(0, 400)}</pre>
                  )}
                  {info.error && (
                    <div className="text-xs text-[#ff3333] font-mono mt-1">{info.error}</div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
