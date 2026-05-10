import React, { useEffect, useState } from "react";
import { api, formatApiError } from "@/lib/api";
import { toast } from "sonner";

export default function AdminPayments() {
  const [pays, setPays] = useState([]);
  const [statusFilter, setStatusFilter] = useState("all");
  const [view, setView] = useState(null);

  const refresh = () => api.adminPayments(statusFilter).then(setPays);
  useEffect(() => { refresh(); }, [statusFilter]);

  const approve = async (id) => {
    try { await api.adminApprove(id, "Approved by admin"); toast.success("Approved"); refresh(); }
    catch (e) { toast.error(formatApiError(e)); }
  };
  const reject = async (id) => {
    const note = prompt("Reason for rejection?") || "Rejected by admin";
    try { await api.adminReject(id, note); toast.success("Rejected"); refresh(); }
    catch (e) { toast.error(formatApiError(e)); }
  };

  return (
    <div className="space-y-6" data-testid="admin-payments-view">
      <div className="flex items-center justify-between">
        <h1 className="font-heading font-black text-3xl tracking-tight">PAYMENTS</h1>
        <div className="flex items-center gap-1">
          {["all","pending","successful","rejected","failed"].map(s => (
            <button key={s} onClick={() => setStatusFilter(s)} data-testid={`pay-filter-${s}`}
                    className={`font-mono uppercase tracking-widest text-[10px] px-3 py-1.5 border ${statusFilter === s ? "bg-[#f5f5f5] text-[#050505] border-[#f5f5f5]" : "border-[#262626] text-[#a3a3a3] hover:bg-[#1a1a1a]"}`}>
              {s}
            </button>
          ))}
        </div>
      </div>

      <div className="co-card overflow-x-auto">
        <table className="w-full text-sm">
          <thead><tr className="border-b border-[#262626]">
            {["Date","User","Method","Amount","Reference","Status","Actions"].map(h =>
              <th key={h} className="text-left font-mono text-[10px] uppercase tracking-widest text-[#525252] px-3 py-3">{h}</th>)}
          </tr></thead>
          <tbody>
            {pays.length === 0 ? <tr><td colSpan={7} className="text-center py-12 text-[#525252] font-mono text-xs uppercase tracking-widest">No payments</td></tr> :
              pays.map(p => (
                <tr key={p.id} className="border-b border-[#1a1a1a]" data-testid={`pay-row-${p.id}`}>
                  <td className="px-3 py-3 font-mono text-xs">{new Date(p.created_at).toLocaleString()}</td>
                  <td className="px-3 py-3 font-mono text-xs">{p.user_email}</td>
                  <td className="px-3 py-3"><span className="co-tag">{p.method.toUpperCase()}</span></td>
                  <td className="px-3 py-3 font-mono">₦{p.amount.toLocaleString()}</td>
                  <td className="px-3 py-3 font-mono text-xs text-[#a3a3a3]">{p.tx_ref || p.reference || "—"}</td>
                  <td className="px-3 py-3"><span className={`co-tag ${p.status === "successful" ? "co-tag-pos" : p.status === "rejected" || p.status === "failed" ? "co-tag-neg" : "co-tag-warn"}`}>{p.status.toUpperCase()}</span></td>
                  <td className="px-3 py-3">
                    {p.status === "pending" && (
                      <div className="flex gap-1">
                        {p.method === "bank_transfer" && p.proof_data_url && (
                          <button onClick={() => setView(p)} data-testid={`pay-view-${p.id}`} className="border border-[#262626] hover:bg-[#1a1a1a] font-mono text-[10px] uppercase px-2 py-1">Receipt</button>
                        )}
                        <button onClick={() => approve(p.id)} data-testid={`pay-approve-${p.id}`} className="border border-[#00ff66] text-[#00ff66] font-mono text-[10px] uppercase px-2 py-1 hover:bg-[#00ff66] hover:text-[#050505]">Approve</button>
                        <button onClick={() => reject(p.id)} data-testid={`pay-reject-${p.id}`} className="border border-[#ff3333] text-[#ff3333] font-mono text-[10px] uppercase px-2 py-1 hover:bg-[#ff3333] hover:text-[#050505]">Reject</button>
                      </div>
                    )}
                  </td>
                </tr>
              ))}
          </tbody>
        </table>
      </div>

      {view && (
        <div className="fixed inset-0 bg-black/80 flex items-center justify-center z-50 p-6" onClick={() => setView(null)}>
          <div onClick={e => e.stopPropagation()} className="co-card max-w-2xl w-full p-5">
            <h3 className="font-heading font-bold mb-3">Payment Receipt — {view.user_email}</h3>
            <img src={view.proof_data_url} alt="receipt" className="max-h-[70vh] w-full object-contain border border-[#262626]"/>
            <div className="mt-3 font-mono text-xs text-[#a3a3a3]">Sender: {view.sender_name} · Reference: {view.reference}</div>
            <button onClick={() => setView(null)} className="mt-4 bg-[#262626] hover:bg-[#1a1a1a] font-mono text-[10px] uppercase tracking-widest px-4 py-2">Close</button>
          </div>
        </div>
      )}
    </div>
  );
}
