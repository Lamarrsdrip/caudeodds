import React from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "@/contexts/AuthContext";
import { LogOut, Activity } from "lucide-react";

export default function AppHeader({ children }) {
  const { user, logout } = useAuth();
  const nav = useNavigate();
  const loc = useLocation();
  const onLogout = async () => { await logout(); nav("/"); };

  return (
    <header className="border-b border-[#262626] bg-[#050505] sticky top-0 z-30" data-testid="app-header">
      <div className="px-6 py-4 flex items-center justify-between">
        <Link to="/" className="flex items-center gap-2" data-testid="brand-link">
          <div className="w-2 h-2 bg-[#00ff66] co-pulse" />
          <h1 className="font-heading font-black text-2xl tracking-tight">CLAUDEODD</h1>
          <span className="font-mono text-[10px] text-[#525252] tracking-widest uppercase pl-2 border-l border-[#262626]">
            QUANT&nbsp;BETTING&nbsp;TERMINAL
          </span>
        </Link>
        <nav className="flex items-center gap-6 font-mono text-[11px] uppercase tracking-widest">
          {!user && (
            <>
              <Link to="/" data-testid="nav-home" className={`hover:text-[#00ff66] ${loc.pathname === "/" ? "text-[#f5f5f5]" : "text-[#a3a3a3]"}`}>Home</Link>
              <Link to="/pricing" data-testid="nav-pricing" className={`hover:text-[#00ff66] ${loc.pathname === "/pricing" ? "text-[#f5f5f5]" : "text-[#a3a3a3]"}`}>Pricing</Link>
              <Link to="/login" data-testid="nav-login" className="text-[#a3a3a3] hover:text-[#00ff66]">Login</Link>
              <Link to="/register" data-testid="nav-register" className="bg-[#f5f5f5] text-[#050505] px-4 py-2 hover:bg-[#00ff66]">Get Started</Link>
            </>
          )}
          {user && (
            <>
              <Link to="/dashboard" data-testid="nav-dashboard" className={`hover:text-[#00ff66] ${loc.pathname.startsWith("/dashboard") ? "text-[#f5f5f5]" : "text-[#a3a3a3]"}`}>Dashboard</Link>
              <Link to="/subscription" data-testid="nav-subscription" className={`hover:text-[#00ff66] ${loc.pathname === "/subscription" ? "text-[#f5f5f5]" : "text-[#a3a3a3]"}`}>Subscription</Link>
              {user.role === "admin" && (
                <Link to="/admin" data-testid="nav-admin" className={`hover:text-[#00ff66] ${loc.pathname.startsWith("/admin") ? "text-[#f5f5f5]" : "text-[#a3a3a3]"}`}>Admin</Link>
              )}
              <span className="text-[#525252] flex items-center gap-2">
                <Activity className="w-3 h-3" />
                {user.email}
              </span>
              <button onClick={onLogout} data-testid="nav-logout" className="text-[#a3a3a3] hover:text-[#ff3333] flex items-center gap-1">
                <LogOut className="w-3.5 h-3.5" /> Logout
              </button>
            </>
          )}
        </nav>
      </div>
      {children}
    </header>
  );
}
