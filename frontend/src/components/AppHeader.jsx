import React, { useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "@/contexts/AuthContext";
import { LogOut, Activity, Menu, X } from "lucide-react";

export default function AppHeader({ children }) {
  const { user, logout } = useAuth();
  const nav = useNavigate();
  const loc = useLocation();
  const [open, setOpen] = useState(false);
  const onLogout = async () => { setOpen(false); await logout(); nav("/"); };
  const close = () => setOpen(false);

  const linkCls = (path, exact = false) => {
    const active = exact ? loc.pathname === path : loc.pathname.startsWith(path);
    return `hover:text-[#00ff66] ${active ? "text-[#f5f5f5]" : "text-[#a3a3a3]"}`;
  };

  return (
    <header
      className="border-b border-[#262626] bg-[#050505] sticky top-0 z-30"
      data-testid="app-header"
      style={{ paddingTop: "env(safe-area-inset-top, 0px)" }}
    >
      <div className="px-4 sm:px-6 py-3 sm:py-4 flex items-center justify-between gap-3">
        <Link to="/" onClick={close} className="flex items-center gap-2 sm:gap-3 min-w-0" data-testid="brand-link">
          <img src="/logo-icon.png" alt="ClaudeOdds" className="w-8 h-8 sm:w-9 sm:h-9 object-contain shrink-0" />
          <h1 className="font-heading font-black text-xl sm:text-2xl tracking-tight truncate">ClaudeOdds</h1>
          <span className="font-mono text-[10px] text-[#525252] tracking-widest uppercase pl-2 border-l border-[#262626] hidden lg:inline">
            AI&nbsp;BETTING&nbsp;COMPANION
          </span>
        </Link>

        {/* Desktop nav */}
        <nav className="hidden md:flex items-center gap-6 font-mono text-[11px] uppercase tracking-widest">
          {!user && (
            <>
              <Link to="/" data-testid="nav-home" className={linkCls("/", true)}>Home</Link>
              <Link to="/pricing" data-testid="nav-pricing" className={linkCls("/pricing", true)}>Pricing</Link>
              <Link to="/login" data-testid="nav-login" className="text-[#a3a3a3] hover:text-[#00ff66]">Login</Link>
              <Link to="/register" data-testid="nav-register" className="bg-[#f5f5f5] text-[#050505] px-4 py-2 hover:bg-[#00ff66]">Get Started</Link>
            </>
          )}
          {user && (
            <>
              <Link to="/dashboard" data-testid="nav-dashboard" className={linkCls("/dashboard")}>Dashboard</Link>
              <Link to="/subscription" data-testid="nav-subscription" className={linkCls("/subscription", true)}>Subscription</Link>
              {user.role === "admin" && (
                <Link to="/admin" data-testid="nav-admin" className={linkCls("/admin")}>Admin</Link>
              )}
              <span className="text-[#525252] flex items-center gap-2">
                <Activity className="w-3 h-3" />
                <span className="hidden xl:inline">{user.email}</span>
              </span>
              <button onClick={onLogout} data-testid="nav-logout" className="text-[#a3a3a3] hover:text-[#ff3333] flex items-center gap-1">
                <LogOut className="w-3.5 h-3.5" /> Logout
              </button>
            </>
          )}
        </nav>

        {/* Mobile hamburger */}
        <button
          onClick={() => setOpen(o => !o)}
          data-testid="mobile-menu-toggle"
          className="md:hidden p-2 text-[#a3a3a3] hover:text-[#f5f5f5]"
          aria-label="Menu"
        >
          {open ? <X className="w-6 h-6" /> : <Menu className="w-6 h-6" />}
        </button>
      </div>

      {/* Mobile menu drawer */}
      {open && (
        <div data-testid="mobile-menu" className="md:hidden border-t border-[#262626] bg-[#0a0a0a]">
          <div className="px-4 py-3 flex flex-col gap-1 font-mono text-[12px] uppercase tracking-widest">
            {!user && (
              <>
                <Link to="/" onClick={close} className="py-3 border-b border-[#1a1a1a] text-[#a3a3a3] hover:text-[#00ff66]">Home</Link>
                <Link to="/pricing" onClick={close} className="py-3 border-b border-[#1a1a1a] text-[#a3a3a3] hover:text-[#00ff66]">Pricing</Link>
                <Link to="/login" onClick={close} className="py-3 border-b border-[#1a1a1a] text-[#a3a3a3] hover:text-[#00ff66]">Login</Link>
                <Link to="/register" onClick={close} className="py-3 mt-2 bg-[#00ff66] text-[#050505] text-center">Start Free Trial →</Link>
              </>
            )}
            {user && (
              <>
                <span className="py-2 text-[10px] text-[#525252] flex items-center gap-2"><Activity className="w-3 h-3"/> {user.email}</span>
                <Link to="/dashboard" onClick={close} className="py-3 border-t border-[#1a1a1a] text-[#a3a3a3] hover:text-[#00ff66]">Today's Slip</Link>
                <Link to="/history" onClick={close} className="py-3 border-t border-[#1a1a1a] text-[#a3a3a3] hover:text-[#00ff66]">History</Link>
                <Link to="/subscription" onClick={close} className="py-3 border-t border-[#1a1a1a] text-[#a3a3a3] hover:text-[#00ff66]">Subscription</Link>
                {user.role === "admin" && (
                  <Link to="/admin" onClick={close} className="py-3 border-t border-[#1a1a1a] text-[#a3a3a3] hover:text-[#00ff66]">Admin Panel</Link>
                )}
                <button onClick={onLogout} className="py-3 mt-2 border-t border-[#1a1a1a] text-left text-[#ff3333] flex items-center gap-2">
                  <LogOut className="w-4 h-4" /> Logout
                </button>
              </>
            )}
          </div>
        </div>
      )}

      {children}
    </header>
  );
}
