import React, { useEffect, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { toast } from "sonner";
import AppHeader from "@/components/AppHeader";
import { useAuth, formatApiError } from "@/contexts/AuthContext";
import EmrizFooter from "@/components/EmrizFooter";
import { api } from "@/lib/api";
import { getDeviceFingerprint } from "@/lib/fingerprint";
import { Gift, CheckCircle2, XCircle } from "lucide-react";

export default function Register() {
  const { register } = useAuth();
  const nav = useNavigate();
  const [params] = useSearchParams();
  const initialRef = (params.get("ref") || "").toUpperCase().trim();

  const [form, setForm] = useState({
    email: "",
    password: "",
    name: "",
    dob: "",
    age_18_plus: false,
    accept_terms: false,
    referral_code: initialRef,
  });
  const [busy, setBusy] = useState(false);
  const [refStatus, setRefStatus] = useState(null); // {valid, referrer_name, referee_trial_days}
  const [fingerprint, setFingerprint] = useState(null);

  const upd = (k, v) => setForm((f) => ({ ...f, [k]: v }));

  // Compute device fingerprint on mount — kept hidden from the user
  useEffect(() => {
    getDeviceFingerprint().then(setFingerprint);
  }, []);

  // Live-validate the referral code (debounced)
  useEffect(() => {
    const code = (form.referral_code || "").trim();
    if (!code) {
      setRefStatus(null);
      return;
    }
    const t = setTimeout(async () => {
      try {
        const res = await api.referralValidate(code);
        setRefStatus(res);
      } catch {
        setRefStatus({ valid: false });
      }
    }, 400);
    return () => clearTimeout(t);
  }, [form.referral_code]);

  const submit = async (e) => {
    e.preventDefault();
    if (!form.age_18_plus) return toast.error("You must confirm you are 18+");
    if (!form.accept_terms) return toast.error("Please accept the Terms & Privacy Policy");
    setBusy(true);
    try {
      // Re-fetch fingerprint if it wasn't ready by submit time
      const fp = fingerprint || (await getDeviceFingerprint());
      await register({
        ...form,
        referral_code: (form.referral_code || "").trim().toUpperCase() || null,
        device_fingerprint: fp,
      });
      const trialMsg = refStatus?.valid
        ? `5-day free trial unlocked thanks to ${refStatus.referrer_name}.`
        : "Your 3-day free trial has started.";
      toast.success(`Welcome! ${trialMsg}`);
      nav("/dashboard");
    } catch (err) {
      toast.error(formatApiError(err));
    } finally {
      setBusy(false);
    }
  };

  const trialDays = refStatus?.valid ? refStatus.referee_trial_days : 3;

  return (
    <div className="min-h-screen bg-[#050505] text-[#f5f5f5]">
      <AppHeader />
      <main className="max-w-md mx-auto px-6 py-16">
        <h1 className="font-heading font-black text-4xl tracking-tight mb-2">CREATE ACCOUNT</h1>
        <p className="font-mono text-[11px] uppercase tracking-widest text-[#525252] mb-8">
          // {trialDays}-day free trial · No card required
        </p>
        {refStatus?.valid && (
          <div className="co-card p-3 mb-6 flex items-center gap-3 border-l-4 border-l-[#00ff66]" data-testid="ref-bonus-banner">
            <Gift className="w-4 h-4 text-[#00ff66] shrink-0" />
            <div className="text-xs text-[#a3a3a3]">
              <span className="text-[#f5f5f5] font-bold">{refStatus.referrer_name}</span> invited you · You get
              <span className="text-[#00ff66] font-bold"> {refStatus.referee_trial_days} days</span> free instead of 3.
            </div>
          </div>
        )}
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
          <div>
            <label className="font-mono text-[10px] uppercase tracking-widest text-[#525252] flex items-center gap-2">
              <Gift className="w-3 h-3 text-[#00ff66]" /> Referral code <span className="text-[#525252] normal-case tracking-normal">(optional · get 5-day trial)</span>
            </label>
            <div className="relative">
              <input value={form.referral_code}
                     onChange={e => upd("referral_code", e.target.value.toUpperCase())}
                     data-testid="reg-referral"
                     placeholder="e.g. AB12CD34"
                     className="w-full bg-[#0a0a0a] border border-[#262626] focus:border-[#525252] outline-none font-mono px-3 py-3 mt-1 uppercase tracking-widest pr-10" />
              {form.referral_code && refStatus && (
                <div className="absolute right-3 top-1/2 -translate-y-1/2 mt-0.5">
                  {refStatus.valid
                    ? <CheckCircle2 className="w-4 h-4 text-[#00ff66]" data-testid="ref-valid"/>
                    : <XCircle className="w-4 h-4 text-[#ff3333]" data-testid="ref-invalid"/>}
                </div>
              )}
            </div>
            {form.referral_code && refStatus && !refStatus.valid && (
              <p className="text-[10px] text-[#ff3333] font-mono mt-1">// Invalid code — registration will still work with default 3-day trial</p>
            )}
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
            {busy ? "Creating account…" : `Start ${trialDays}-Day Free Trial →`}
          </button>
          <p className="text-[10px] font-mono text-[#525252] mt-2 leading-relaxed">
            // One account per device. Multiple signups from the same phone are blocked to keep the trial fair.
          </p>
        </form>
        <p className="mt-6 text-sm text-[#a3a3a3] font-mono">
          Already have an account? <Link to="/login" className="text-[#00ff66] hover:underline">Login</Link>
        </p>
      </main>
      <EmrizFooter />
    </div>
  );
}
