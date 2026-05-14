import React from "react";
import { Link, useLocation } from "react-router-dom";
import { Home, CreditCard, Shield, Trophy } from "lucide-react";
import { useAuth } from "@/contexts/AuthContext";

/** Bottom tab navigation for mobile users. Hidden on md+ screens. */
export default function BottomNav() {
  const { user } = useAuth();
  const loc = useLocation();
  if (!user) return null;

  const tabs = [
    { to: "/dashboard", icon: Home, label: "Slip", testid: "tab-slip", match: () => loc.pathname === "/dashboard" && loc.hash !== "#fixtures" },
    { to: "/dashboard#fixtures", icon: Trophy, label: "Fixtures", testid: "tab-fixtures", match: () => loc.pathname === "/dashboard" && loc.hash === "#fixtures" },
    { to: "/subscription", icon: CreditCard, label: "Plan", testid: "tab-subscription" },
  ];
  if (user.role === "admin") {
    tabs.push({ to: "/admin", icon: Shield, label: "Admin", testid: "tab-admin" });
  }

  return (
    <nav
      data-testid="bottom-nav"
      className="md:hidden fixed bottom-0 inset-x-0 z-40 px-3 pt-2"
      style={{
        paddingBottom: "env(safe-area-inset-bottom, 0px)",
      }}
    >
      <div
        className="grid co-glass rounded-[8px] overflow-hidden mb-2"
        style={{ gridTemplateColumns: `repeat(${tabs.length}, 1fr)` }}
      >
        {tabs.map(({ to, icon: Icon, label, testid, match }) => {
          const active = match ? match() : to === "/admin" ? loc.pathname.startsWith("/admin") : loc.pathname === to;
          return (
            <Link
              key={`${to}-${label}`}
              to={to}
              data-testid={testid}
              className={`relative flex flex-col items-center justify-center py-3 gap-1 min-h-[62px] ${
                active ? "text-[#050607]" : "text-[#aeb8c2] hover:text-[#f5f5f5]"
              }`}
            >
              {active && <span className="absolute inset-1 bg-[#00ff66] rounded-[6px]" />}
              <Icon className="relative w-5 h-5" strokeWidth={active ? 2.4 : 1.8} />
              <span className="relative font-mono text-[9px] uppercase tracking-widest">{label}</span>
            </Link>
          );
        })}
      </div>
    </nav>
  );
}
