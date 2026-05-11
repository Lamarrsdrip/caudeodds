import React, { useEffect, useState } from "react";
import { Link, NavLink, Outlet } from "react-router-dom";
import AppHeader from "@/components/AppHeader";
import { api } from "@/lib/api";
import { Users, CreditCard, Settings, BarChart3, Layers, Activity, Shield } from "lucide-react";

const ITEMS = [
  { to: "/admin", icon: BarChart3, label: "Overview", end: true },
  { to: "/admin/users", icon: Users, label: "Users" },
  { to: "/admin/payments", icon: CreditCard, label: "Payments" },
  { to: "/admin/predictions", icon: Layers, label: "Predictions" },
  { to: "/admin/security", icon: Shield, label: "Security" },
  { to: "/admin/config", icon: Settings, label: "Configuration" },
];

export default function AdminLayout() {
  return (
    <div className="min-h-screen bg-[#050505] text-[#f5f5f5]">
      <AppHeader />
      <div className="md:grid md:grid-cols-[220px_1fr] md:min-h-[calc(100vh-130px)]">
        <aside className="hidden md:block border-r border-[#262626] py-6">
          <div className="px-6 mb-6 font-mono text-[10px] uppercase tracking-widest text-[#525252]">// Admin Panel</div>
          <nav className="flex flex-col">
            {ITEMS.map(it => (
              <NavLink key={it.to} to={it.to} end={it.end} data-testid={`admin-nav-${it.label.toLowerCase()}`}
                       className={({isActive}) => `px-6 py-3 flex items-center gap-3 font-mono text-[11px] uppercase tracking-widest border-l-2 ${
                         isActive ? "border-[#00ff66] bg-[#1a1a1a] text-[#f5f5f5]" : "border-transparent text-[#a3a3a3] hover:bg-[#1a1a1a]"
                       }`}>
                <it.icon className="w-3.5 h-3.5"/> {it.label}
              </NavLink>
            ))}
          </nav>
        </aside>
        {/* Mobile: horizontal sub-tab bar */}
        <nav data-testid="admin-mobile-tabs" className="md:hidden flex items-center gap-0 border-b border-[#262626] overflow-x-auto bg-[#050505]">
          {ITEMS.map(it => (
            <NavLink key={it.to} to={it.to} end={it.end}
                     className={({isActive}) => `shrink-0 px-4 py-3 flex items-center gap-2 font-mono text-[10px] uppercase tracking-widest border-b-2 ${
                       isActive ? "border-[#00ff66] text-[#f5f5f5]" : "border-transparent text-[#a3a3a3]"
                     }`}>
              <it.icon className="w-3.5 h-3.5"/> {it.label}
            </NavLink>
          ))}
        </nav>
        <main className="p-4 sm:p-6 md:p-8 max-w-full overflow-x-hidden">
          <Outlet />
        </main>
      </div>
    </div>
  );
}

export function AdminOverview() {
  const [stats, setStats] = useState(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => { api.adminStats().then(setStats); }, []);

  const generate = async () => {
    setBusy(true);
    try {
      const r = await api.adminGenerate(false);
      alert(`Done. ${r.cached ? "Cached" : "Generated"}. Picks: ${r.picks ?? 0}`);
      window.location.reload();
    } finally { setBusy(false); }
  };

  return (
    <div className="space-y-6 sm:space-y-8">
      <div className="flex items-baseline justify-between flex-wrap gap-3">
        <h1 className="font-heading font-black text-2xl sm:text-3xl tracking-tight">ADMIN OVERVIEW</h1>
        <button onClick={generate} disabled={busy} data-testid="admin-generate" className="bg-[#00ff66] text-[#050505] font-mono uppercase tracking-widest text-xs px-4 py-2 hover:bg-[#f5f5f5] disabled:opacity-50 inline-flex items-center gap-2">
          <Activity className="w-3.5 h-3.5"/> {busy ? "Running…" : "Run Daily Ensemble"}
        </button>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-7 border border-[#262626]">
        {[
          ["Total Users", stats?.total_users],
          ["Trial Users", stats?.trial_users],
          ["Active Subs", stats?.active_subscribers],
          ["Expired", stats?.expired_subscribers],
          ["Pending Pay", stats?.pending_payments],
          ["Successful", stats?.successful_payments],
          ["Revenue ₦", stats?.revenue_ngn?.toLocaleString()],
        ].map(([k, v], i) => (
          <div key={k} className="p-4 sm:p-5 border-b sm:border-b-0 border-r last:border-r-0 sm:border-r border-[#262626]" data-testid={`stat-${k.toLowerCase().replace(/[^a-z]/g,'-')}`}>
            <div className="text-[10px] font-mono uppercase tracking-widest text-[#525252]">{k}</div>
            <div className="font-mono text-xl sm:text-2xl mt-1">{v ?? "—"}</div>
          </div>
        ))}
      </div>

      <div className="co-card p-5 sm:p-6">
        <h2 className="font-heading font-bold text-lg mb-3">Quick Actions</h2>
        <div className="flex items-center gap-3 flex-wrap font-mono text-xs">
          <Link to="/admin/payments" className="bg-[#262626] hover:bg-[#1a1a1a] px-4 py-3 uppercase tracking-widest">Review Pending Payments</Link>
          <Link to="/admin/config" className="bg-[#262626] hover:bg-[#1a1a1a] px-4 py-3 uppercase tracking-widest">API Source / Config</Link>
          <Link to="/admin/predictions" className="bg-[#262626] hover:bg-[#1a1a1a] px-4 py-3 uppercase tracking-widest">Settle Predictions</Link>
        </div>
      </div>
    </div>
  );
}
