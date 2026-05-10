import React, { useEffect, useState } from "react";
import { api, formatApiError } from "@/lib/api";
import { toast } from "sonner";

export default function AdminUsers() {
  const [users, setUsers] = useState([]);
  const [filter, setFilter] = useState("");

  const refresh = () => api.adminUsers().then(setUsers);
  useEffect(() => { refresh(); }, []);

  const grant = async (id) => {
    try { await api.adminGrant(id, 30); toast.success("Granted 30 days"); refresh(); }
    catch (e) { toast.error(formatApiError(e)); }
  };
  const suspend = async (id) => {
    if (!window.confirm("Suspend this user?")) return;
    try { await api.adminSuspend(id); toast.success("Suspended"); refresh(); }
    catch (e) { toast.error(formatApiError(e)); }
  };

  const filtered = users.filter(u => !filter || (u.email + " " + (u.name || "")).toLowerCase().includes(filter.toLowerCase()));

  return (
    <div className="space-y-6" data-testid="admin-users-view">
      <div className="flex items-center justify-between">
        <h1 className="font-heading font-black text-3xl tracking-tight">USERS</h1>
        <input placeholder="Search…" value={filter} onChange={e => setFilter(e.target.value)} data-testid="users-search"
               className="bg-[#0a0a0a] border border-[#262626] font-mono text-xs px-3 py-2 outline-none focus:border-[#525252]"/>
      </div>
      <div className="co-card overflow-x-auto">
        <table className="w-full text-sm">
          <thead><tr className="border-b border-[#262626]">
            {["Email","Name","Role","Status","Trial Ends","Sub Ends","Created","Actions"].map(h =>
              <th key={h} className="text-left font-mono text-[10px] uppercase tracking-widest text-[#525252] px-3 py-3">{h}</th>)}
          </tr></thead>
          <tbody>
            {filtered.map(u => (
              <tr key={u.id} className="border-b border-[#1a1a1a]" data-testid={`user-row-${u.id}`}>
                <td className="px-3 py-3 font-mono text-xs">{u.email}</td>
                <td className="px-3 py-3">{u.name}</td>
                <td className="px-3 py-3"><span className={`co-tag ${u.role === "admin" ? "co-tag-warn" : ""}`}>{u.role.toUpperCase()}</span></td>
                <td className="px-3 py-3"><span className={`co-tag ${u.subscription_status === "active" ? "co-tag-pos" : u.subscription_status === "trial" ? "co-tag-warn" : ""}`}>{(u.subscription_status || "none").toUpperCase()}</span></td>
                <td className="px-3 py-3 font-mono text-xs text-[#a3a3a3]">{u.trial_ends_at ? new Date(u.trial_ends_at).toLocaleDateString() : "—"}</td>
                <td className="px-3 py-3 font-mono text-xs text-[#a3a3a3]">{u.subscription_ends_at ? new Date(u.subscription_ends_at).toLocaleDateString() : "—"}</td>
                <td className="px-3 py-3 font-mono text-xs text-[#a3a3a3]">{new Date(u.created_at).toLocaleDateString()}</td>
                <td className="px-3 py-3">
                  {u.role !== "admin" && (
                    <div className="flex gap-1">
                      <button onClick={() => grant(u.id)} data-testid={`grant-${u.id}`} className="border border-[#00ff66] text-[#00ff66] font-mono text-[10px] uppercase px-2 py-1 hover:bg-[#00ff66] hover:text-[#050505]">+30d</button>
                      <button onClick={() => suspend(u.id)} data-testid={`suspend-${u.id}`} className="border border-[#ff3333] text-[#ff3333] font-mono text-[10px] uppercase px-2 py-1 hover:bg-[#ff3333] hover:text-[#050505]">Suspend</button>
                    </div>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
