import React from "react";
import { Link, useLocation } from "react-router-dom";
import { Home, CreditCard, Shield } from "lucide-react";
import { useAuth } from "@/contexts/AuthContext";

/** Bottom tab navigation for mobile users. Hidden on md+ screens. */
export default function BottomNav() {
  const { user } = useAuth();
  const loc = useLocation();
  if (!user) return null;

  const tabs = [
    { to: "/dashboard", icon: Home, label: "Slip", testid: "tab-slip" },
    { to: "/subscription", icon: CreditCard, label: "Plan", testid: "tab-subscription" },
  ];
  if (user.role === "admin") {
    tabs.push({ to: "/admin", icon: Shield, label: "Admin", testid: "tab-admin" });
  }

  return (
    <nav
      data-testid="bottom-nav"
      className="md:hidden fixed bottom-0 inset-x-0 z-40 bg-[#050505] border-t border-[#262626] grid"
      style={{
        gridTemplateColumns: `repeat(${tabs.length}, 1fr)`,
        paddingBottom: "env(safe-area-inset-bottom, 0px)",
      }}
    >
      {tabs.map(({ to, icon: Icon, label, testid }) => {
        const active = to === "/admin" ? loc.pathname.startsWith("/admin") : loc.pathname === to || (to === "/dashboard" && loc.pathname === "/dashboard");
        return (
          <Link
            key={to}
            to={to}
            data-testid={testid}
            className={`flex flex-col items-center justify-center py-2.5 gap-1 ${
              active ? "text-[#00ff66]" : "text-[#a3a3a3] hover:text-[#f5f5f5]"
            }`}
          >
            <Icon className="w-5 h-5" strokeWidth={active ? 2.2 : 1.6} />
            <span className="font-mono text-[9px] uppercase tracking-widest">{label}</span>
          </Link>
        );
      })}
    </nav>
  );
}
