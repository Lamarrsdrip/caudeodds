import React, { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { toast } from "sonner";
import AppHeader from "@/components/AppHeader";
import { useAuth, formatApiError } from "@/contexts/AuthContext";
import EmrizFooter from "@/components/EmrizFooter";

export default function Login() {
  const { login } = useAuth();
  const nav = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    try {
      const u = await login(email, password);
      toast.success("Logged in");
      nav(u.role === "admin" ? "/admin" : "/dashboard");
    } catch (err) {
      toast.error(formatApiError(err));
    } finally { setBusy(false); }
  };

  return (
    <div className="min-h-screen bg-[#050505] text-[#f5f5f5]">
      <AppHeader />
      <main className="max-w-md mx-auto px-6 py-20">
        <h1 className="font-heading font-black text-4xl tracking-tight mb-2">LOGIN</h1>
        <p className="font-mono text-[11px] uppercase tracking-widest text-[#525252] mb-10">// Welcome back to the terminal</p>
        <form onSubmit={submit} className="space-y-5" data-testid="login-form">
          <div>
            <label className="font-mono text-[10px] uppercase tracking-widest text-[#525252]">Email</label>
            <input type="email" required value={email} onChange={e => setEmail(e.target.value)} data-testid="login-email"
                   className="w-full bg-[#0a0a0a] border border-[#262626] focus:border-[#525252] outline-none font-mono px-3 py-3 mt-1" />
          </div>
          <div>
            <label className="font-mono text-[10px] uppercase tracking-widest text-[#525252]">Password</label>
            <input type="password" required value={password} onChange={e => setPassword(e.target.value)} data-testid="login-password"
                   className="w-full bg-[#0a0a0a] border border-[#262626] focus:border-[#525252] outline-none font-mono px-3 py-3 mt-1" />
          </div>
          <button type="submit" disabled={busy} data-testid="login-submit"
                  className="w-full bg-[#f5f5f5] text-[#050505] font-mono uppercase tracking-widest text-xs py-3 hover:bg-[#00ff66] disabled:opacity-50">
            {busy ? "Signing in…" : "Sign In →"}
          </button>
        </form>
        <p className="mt-8 text-sm text-[#a3a3a3] font-mono">
          No account? <Link to="/register" className="text-[#00ff66] hover:underline">Start a 3-day free trial</Link>
        </p>
      </main>
      <EmrizFooter />
    </div>
  );
}
