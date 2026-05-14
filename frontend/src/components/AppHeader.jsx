import React, { useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "@/contexts/AuthContext";
import { LogOut, Activity, Menu, X, Crown, Bell } from "lucide-react";

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
      className="sticky top-0 z-30 border-b border-white/10 bg-[#050607]/82 backdrop-blur-xl"
      data-testid="app-header"
      style={{ paddingTop: "env(safe-area-inset-top, 0px)" }}
    >
      <div className="mx-auto max-w-[1300px] px-4 sm:px-6 py-3 sm:py-4 flex items-center justify-between gap-3">
        <Link to="/" onClick={close} className="flex items-center gap-2 sm:gap-3 min-w-0" data-testid="brand-link">
          <span className="grid place-items-center w-10 h-10 bg-white/5 border border-white/10 rounded-[8px] shrink-0">
            <img src="/logo-icon.png" alt="ClaudeOdds" className="w-7 h-7 object-contain" />
          </span>
          <span className="min-w-0">
            <h1 className="font-heading font-black text-lg sm:text-2xl tracking-tight truncate leading-none">ClaudeOdds</h1>
            <span className="font-mono text-[9px] text-[#667482] tracking-widest uppercase hidden sm:block mt-1">
              AI betting companion
            </span>
          </span>
        </Link>

        {/* Desktop nav */}
        <nav className="hidden md:flex items-center gap-6 font-mono text-[11px] uppercase tracking-widest">
          {!user && (
            <>
              <Link to="/" data-testid="nav-home" className={linkCls("/", true)}>Home</Link>
              <Link to="/pricing" data-testid="nav-pricing" className={linkCls("/pricing", true)}>Pricing</Link>
              <Link to="/login" data-testid="nav-login" className="text-[#a3a3a3] hover:text-[#00ff66]">Login</Link>
              <Link to="/register" data-testid="nav-register" className="co-primary-action px-4 py-2 rounded-[6px]">Get Started</Link>
            </>
          )}
          {user && (
            <>
              <Link to="/dashboard" data-testid="nav-dashboard" className={linkCls("/dashboard")}>Dashboard</Link>
              <Link to="/subscription" data-testid="nav-subscription" className={linkCls("/subscription", true)}>Subscription</Link>
              {user.role === "admin" && (
                <Link to="/admin" data-testid="nav-admin" className={linkCls("/admin")}>Admin</Link>
              )}
              <span className="text-[#667482] flex items-center gap-2">
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
          className="md:hidden w-10 h-10 grid place-items-center text-[#aeb8c2] bg-white/5 border border-white/10 rounded-[8px]"
          aria-label="Menu"
        >
          {open ? <X className="w-6 h-6" /> : <Menu className="w-6 h-6" />}
        </button>
      </div>

      {/* Mobile menu drawer */}
      {open && (
        <div data-testid="mobile-menu" className="md:hidden border-t border-white/10 bg-[#0b0f12]/96 backdrop-blur-xl">
          <div className="px-4 py-4 flex flex-col gap-2 font-mono text-[12px] uppercase tracking-widest">
            {!user && (
              <>
                <Link to="/" onClick={close} className="p-4 co-secondary-action rounded-[8px] text-[#aeb8c2]">Home</Link>
                <Link to="/pricing" onClick={close} className="p-4 co-secondary-action rounded-[8px] text-[#aeb8c2]">Pricing</Link>
                <Link to="/login" onClick={close} className="p-4 co-secondary-action rounded-[8px] text-[#aeb8c2]">Login</Link>
                <Link to="/register" onClick={close} className="p-4 mt-1 co-primary-action text-center rounded-[8px]">Start Free Trial</Link>
              </>
            )}
            {user && (
              <>
                <span className="p-4 co-soft-band rounded-[8px] text-[10px] text-[#aeb8c2] flex items-center gap-2 normal-case tracking-normal font-body">
                  <Activity className="w-4 h-4 text-[#00ff66]"/> {user.email}
                </span>
                <Link to="/dashboard" onClick={close} className="p-4 co-secondary-action rounded-[8px] text-[#aeb8c2] flex items-center gap-3"><Bell className="w-4 h-4"/> Today's Slip</Link>
                <Link to="/subscription" onClick={close} className="p-4 co-secondary-action rounded-[8px] text-[#aeb8c2] flex items-center gap-3"><Crown className="w-4 h-4"/> Subscription</Link>
                {user.role === "admin" && (
                  <Link to="/admin" onClick={close} className="p-4 co-secondary-action rounded-[8px] text-[#aeb8c2]">Admin Panel</Link>
                )}
                <button onClick={onLogout} className="p-4 mt-1 text-left text-[#ff6b6b] flex items-center gap-2 co-secondary-action rounded-[8px]">
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
