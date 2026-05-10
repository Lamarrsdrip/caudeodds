import React, { useEffect, useState } from "react";
import { api, formatApiError } from "@/lib/api";
import { toast } from "sonner";

export default function AdminPredictions() {
  const [preds, setPreds] = useState([]);
  const [busy, setBusy] = useState(false);

  const refresh = () => api.adminPredictions().then(setPreds);
  useEffect(() => { refresh(); }, []);

  const settle = async (id, result) => {
    try { await api.adminSettle(id, result); toast.success(`Marked ${result}`); refresh(); }
    catch (e) { toast.error(formatApiError(e)); }
  };

  const generate = async (force) => {
    setBusy(true);
    try {
      const r = await api.adminGenerate(force);
      toast.success(`Done. ${r.cached ? "Cached" : "Generated"} · picks: ${r.picks ?? 0}`);
      refresh();
    } catch (e) { toast.error(formatApiError(e)); }
    finally { setBusy(false); }
  };

  return (
    <div className="space-y-6" data-testid="admin-predictions-view">
      <div className="flex items-center justify-between">
        <h1 className="font-heading font-black text-3xl tracking-tight">PREDICTIONS</h1>
        <div className="flex items-center gap-2">
          <button onClick={() => generate(false)} disabled={busy} data-testid="pred-gen" className="border border-[#262626] hover:bg-[#1a1a1a] font-mono text-xs uppercase tracking-widest px-4 py-2 disabled:opacity-50">
            {busy ? "Running…" : "Generate (cached)"}
          </button>
          <button onClick={() => generate(true)} disabled={busy} data-testid="pred-gen-force" className="bg-[#00ff66] text-[#050505] font-mono text-xs uppercase tracking-widest px-4 py-2 hover:bg-[#f5f5f5] disabled:opacity-50">
            {busy ? "Running…" : "Force Re-Generate"}
          </button>
        </div>
      </div>

      <div className="co-card overflow-x-auto">
        <table className="w-full text-sm">
          <thead><tr className="border-b border-[#262626]">
            {["Date","Sport","Match","Selection","Odds","Conf","EV","Status","Settle"].map(h =>
              <th key={h} className="text-left font-mono text-[10px] uppercase tracking-widest text-[#525252] px-3 py-3">{h}</th>)}
          </tr></thead>
          <tbody>
            {preds.length === 0 ? <tr><td colSpan={9} className="text-center py-12 text-[#525252] font-mono text-xs uppercase tracking-widest">No predictions yet — click Generate</td></tr> :
              preds.map(p => (
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
