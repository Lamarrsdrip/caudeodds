import React, { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { toast } from "sonner";
import AppHeader from "@/components/AppHeader";
import { useAuth, formatApiError } from "@/contexts/AuthContext";
import EmrizFooter from "@/components/EmrizFooter";

export default function Register() {
  const { register } = useAuth();
  const nav = useNavigate();
  const [form, setForm] = useState({ email: "", password: "", name: "", dob: "", age_18_plus: false, accept_terms: false });
  const [busy, setBusy] = useState(false);

  const upd = (k, v) => setForm({ ...form, [k]: v });

  const submit = async (e) => {
    e.preventDefault();
    if (!form.age_18_plus) return toast.error("You must confirm you are 18+");
    if (!form.accept_terms) return toast.error("Please accept the Terms & Privacy Policy");
    setBusy(true);
    try {
      await register(form);
      toast.success("Welcome! Your 3-day free trial has started.");
      nav("/dashboard");
    } catch (err) {
      toast.error(formatApiError(err));
    } finally { setBusy(false); }
  };

  return (
    <div className="min-h-screen bg-[#050505] text-[#f5f5f5]">
      <AppHeader />
      <main className="max-w-md mx-auto px-6 py-16">
        <h1 className="font-heading font-black text-4xl tracking-tight mb-2">CREATE ACCOUNT</h1>
        <p className="font-mono text-[11px] uppercase tracking-widest text-[#525252] mb-8">// 3-day free trial · No card required</p>
        <form onSubmit={submit} className="space-y-4" data-testid="register-form">
          <div>
            <label className="font-mono text-[10px] uppercase tracking-widest text-[#525252]">Full Name</label>
            <input required value={form.name} onChange={e => upd("name", e.target.value)} data-testid="reg-name"
                   className="w-full bg-[#0a0a0a] border border-[#262626] focus:border-[#525252] outline-none font-mono px-3 py-3 mt-1" />
          </div>
          <div>
            <label className="font-mono text-[10px] uppercase tracking-widest text-[#525252]">Email</label>
            <input type="email" required value={form.email} onChange={e => upd("email", e.target.value)} data-testid="reg-email"
                   className="w-full bg-[#0a0a0a] border border-[#262626] focus:border-[#525252] outline-none font-mono px-3 py-3 mt-1" />
          </div>
          <div>
            <label className="font-mono text-[10px] uppercase tracking-widest text-[#525252]">Password (min 8)</label>
            <input type="password" required minLength={8} value={form.password} onChange={e => upd("password", e.target.value)} data-testid="reg-password"
                   className="w-full bg-[#0a0a0a] border border-[#262626] focus:border-[#525252] outline-none font-mono px-3 py-3 mt-1" />
          </div>
          <div>
            <label className="font-mono text-[10px] uppercase tracking-widest text-[#525252]">Date of Birth</label>
            <input type="date" value={form.dob} onChange={e => upd("dob", e.target.value)} data-testid="reg-dob"
                   className="w-full bg-[#0a0a0a] border border-[#262626] focus:border-[#525252] outline-none font-mono px-3 py-3 mt-1" />
          </div>
          <label className="flex items-start gap-2 text-xs text-[#a3a3a3] cursor-pointer pt-2">
            <input type="checkbox" checked={form.age_18_plus} onChange={e => upd("age_18_plus", e.target.checked)} data-testid="reg-18"
                   className="mt-0.5 accent-[#00ff66]" />
            <span>I confirm I am <strong className="text-[#f5f5f5]">18 years or older</strong> and gambling is legal in my jurisdiction.</span>
          </label>
          <label className="flex items-start gap-2 text-xs text-[#a3a3a3] cursor-pointer">
            <input type="checkbox" checked={form.accept_terms} onChange={e => upd("accept_terms", e.target.checked)} data-testid="reg-terms"
                   className="mt-0.5 accent-[#00ff66]" />
            <span>
              I accept the <Link to="/terms" className="text-[#00ff66] hover:underline">Terms</Link>,{" "}
              <Link to="/privacy" className="text-[#00ff66] hover:underline">Privacy Policy</Link>, and the
              <strong className="text-[#f5f5f5]"> responsible-gambling</strong> guidelines. Predictions are NOT financial advice.
            </span>
          </label>
          <button type="submit" disabled={busy} data-testid="reg-submit"
                  className="w-full bg-[#00ff66] text-[#050505] font-mono uppercase tracking-widest text-xs py-3 hover:bg-[#f5f5f5] disabled:opacity-50">
            {busy ? "Creating account…" : "Start Free Trial →"}
          </button>
        </form>
        <p className="mt-6 text-sm text-[#a3a3a3] font-mono">
          Already have an account? <Link to="/login" className="text-[#00ff66] hover:underline">Login</Link>
        </p>
      </main>
      <EmrizFooter />
    </div>
  );
}
