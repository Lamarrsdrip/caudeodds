import React, { useEffect, useState } from "react";
import AppHeader from "@/components/AppHeader";
import EmrizFooter from "@/components/EmrizFooter";
import { api, formatApiError } from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";
import { toast } from "sonner";
import { CreditCard, Loader2, Upload, Building2, CheckCircle2, Clock, ShieldCheck, WalletCards } from "lucide-react";

function FlutterwavePane() {
  const [busy, setBusy] = useState(false);
  const launch = async () => {
    setBusy(true);
    try {
      const r = await api.flwInit();
      window.location.href = r.checkout_link;
    } catch (e) {
      toast.error(formatApiError(e));
      setBusy(false);
    }
  };
  return (
    <div className="co-card p-5 sm:p-6 space-y-4" data-testid="pay-flutterwave">
      <div className="flex items-center gap-3">
        <CreditCard className="w-5 h-5 text-[#00ff66]" />
        <div>
          <div className="font-heading font-bold">Pay with Card / Bank (Flutterwave)</div>
          <div className="font-mono text-[10px] uppercase tracking-widest text-[#525252]">// Instant activation · NGN cards · Bank transfer · USSD</div>
        </div>
      </div>
      <p className="text-sm text-[#a3a3a3] leading-relaxed">Hosted secure checkout by Flutterwave. Subscription activates the instant payment is verified.</p>
      <button onClick={launch} disabled={busy} data-testid="flw-pay-btn" className="w-full sm:w-auto co-primary-action rounded-[6px] font-mono uppercase tracking-widest text-xs px-6 py-3 inline-flex items-center justify-center gap-2 disabled:opacity-50 min-h-[46px]">
        {busy ? <Loader2 className="w-4 h-4 animate-spin"/> : null}
        Pay Now via Flutterwave
      </button>
    </div>
  );
}

function BankTransferPane({ cfg, onSubmitted }) {
  const [proof, setProof] = useState(null);
  const [sender, setSender] = useState("");
  const [reference, setReference] = useState("");
  const [busy, setBusy] = useState(false);

  const handleFile = (file) => {
    if (!file) return;
    if (file.size > 3_000_000) return toast.error("File too large (max 3MB)");
    const reader = new FileReader();
    reader.onload = () => setProof(reader.result);
    reader.readAsDataURL(file);
  };

  const submit = async () => {
    if (!proof) return toast.error("Upload your transfer receipt");
    if (!sender) return toast.error("Enter sender name (matching the bank transfer)");
    if (!reference) return toast.error("Enter the transfer reference / narration");
    setBusy(true);
    try {
      await api.bankTransfer({
        amount: cfg?.price_ngn || 5000,
        proof_data_url: proof,
        sender_name: sender,
        reference,
      });
      toast.success("Submitted. Admin will verify within a few hours.");
      setProof(null); setSender(""); setReference("");
      onSubmitted?.();
    } catch (e) {
      toast.error(formatApiError(e));
    } finally { setBusy(false); }
  };

  return (
    <div className="co-card p-5 sm:p-6 space-y-4" data-testid="pay-bank">
      <div className="flex items-center gap-3">
        <Building2 className="w-5 h-5 text-[#00ff66]" />
        <div>
          <div className="font-heading font-bold">Manual Bank Transfer</div>
          <div className="font-mono text-[10px] uppercase tracking-widest text-[#525252]">// Verified by admin · Activates within hours</div>
        </div>
      </div>

      {(cfg?.bank_account_number) ? (
        <div className="border border-[#26313a] rounded-[8px] p-4 space-y-1 font-mono text-sm bg-[#0a0a0a]">
          <div><span className="text-[#525252]">Bank:</span> {cfg.bank_name}</div>
          <div><span className="text-[#525252]">Account #:</span> {cfg.bank_account_number}</div>
          <div><span className="text-[#525252]">Account Name:</span> {cfg.bank_account_name}</div>
          <div className="text-xs text-[#a3a3a3] mt-2">{cfg.bank_instructions}</div>
        </div>
      ) : (
        <div className="border border-[#ff9900] p-4 text-xs text-[#ff9900] font-mono">
          // Bank details not yet configured by admin. Use Flutterwave for now.
        </div>
      )}

      <div className="space-y-3">
        <div>
          <label className="font-mono text-[10px] uppercase tracking-widest text-[#525252]">Sender Name (must match transfer)</label>
          <input value={sender} onChange={e => setSender(e.target.value)} data-testid="bank-sender" className="w-full bg-[#0a0a0a] border border-[#26313a] focus:border-[#00ff66] outline-none font-mono px-3 py-3 mt-1 rounded-[6px]" />
        </div>
        <div>
          <label className="font-mono text-[10px] uppercase tracking-widest text-[#525252]">Transfer Reference / Narration</label>
          <input value={reference} onChange={e => setReference(e.target.value)} data-testid="bank-ref" className="w-full bg-[#0a0a0a] border border-[#26313a] focus:border-[#00ff66] outline-none font-mono px-3 py-3 mt-1 rounded-[6px]" />
        </div>
        <div>
          <label className="font-mono text-[10px] uppercase tracking-widest text-[#525252]">Upload Receipt (image, max 3MB)</label>
          <input type="file" accept="image/*" onChange={e => handleFile(e.target.files?.[0])} data-testid="bank-proof"
                 className="w-full bg-[#0a0a0a] border border-[#26313a] file:bg-[#26313a] file:border-0 file:text-[#f5f5f5] file:px-3 file:py-2 file:font-mono file:text-[10px] file:uppercase file:tracking-widest file:mr-3 px-3 py-2 mt-1 rounded-[6px]" />
          {proof && <div className="text-xs text-[#00ff66] font-mono mt-2 inline-flex items-center gap-1"><CheckCircle2 className="w-3.5 h-3.5"/> Receipt loaded</div>}
        </div>
      </div>

      <button onClick={submit} disabled={busy} data-testid="bank-submit" className="w-full sm:w-auto bg-[#f5f5f5] text-[#050505] font-mono uppercase tracking-widest text-xs px-6 py-3 hover:bg-[#00ff66] inline-flex items-center justify-center gap-2 disabled:opacity-50 rounded-[6px] min-h-[46px]">
        {busy ? <Loader2 className="w-4 h-4 animate-spin"/> : <Upload className="w-4 h-4"/>}
        Submit for Verification
      </button>
    </div>
  );
}

export default function Subscription() {
  const { user, refresh } = useAuth();
  const [cfg, setCfg] = useState(null);
  const [pays, setPays] = useState([]);
  const ends = user?.subscription_ends_at || user?.trial_ends_at;
  const daysLeft = ends ? Math.max(0, Math.ceil((new Date(ends) - new Date()) / (1000 * 60 * 60 * 24))) : 0;
  const active = user?.subscription_status === "active";
  const trial = user?.subscription_status === "trial";

  useEffect(() => {
    api.publicConfig().then(setCfg);
    api.myPayments().then(setPays).catch(() => setPays([]));
  }, []);

  return (
    <div className="co-app-shell text-[#f5f5f5]">
      <AppHeader />
      <main className="max-w-[1100px] mx-auto px-4 sm:px-6 py-6 sm:py-10 pb-28 space-y-6 sm:space-y-8">
        <section className="co-soft-band rounded-[8px] p-5 sm:p-7">
          <div className="flex items-start justify-between gap-4 flex-wrap">
            <div>
              <div className="font-mono text-[10px] uppercase tracking-widest text-[#667482] mb-2">Plan control</div>
              <h1 className="font-heading font-black text-3xl sm:text-5xl tracking-tight" data-testid="sub-title">Subscription</h1>
              <p className="text-sm sm:text-base text-[#aeb8c2] mt-3 leading-relaxed">
                Manage payment, trial status, and access to daily slips from one clean mobile screen.
              </p>
            </div>
            <span className="w-14 h-14 rounded-[8px] bg-[#00ff66] text-[#050607] grid place-items-center shrink-0">
              <WalletCards className="w-7 h-7" />
            </span>
          </div>
          <div className="grid grid-cols-3 gap-2 mt-5">
            <div className="co-stat-tile p-3">
              <div className="font-mono text-[9px] uppercase tracking-widest text-[#667482]">Status</div>
              <div className={`font-mono text-lg sm:text-xl mt-2 ${active ? "text-[#00ff66]" : trial ? "text-[#ffb800]" : "text-[#ff3333]"}`}>
                {user?.subscription_status || "none"}
              </div>
            </div>
            <div className="co-stat-tile p-3">
              <div className="font-mono text-[9px] uppercase tracking-widest text-[#667482]">Days</div>
              <div className="font-mono text-lg sm:text-xl mt-2">{daysLeft}</div>
            </div>
            <div className="co-stat-tile p-3">
              <div className="font-mono text-[9px] uppercase tracking-widest text-[#667482]">Price</div>
              <div className="font-mono text-lg sm:text-xl mt-2">₦{(cfg?.price_ngn || 5000).toLocaleString()}</div>
            </div>
          </div>
        </section>

        {user?.subscription_status === "active" && (
          <div className="co-card p-5 border-[#00ff66] flex items-center gap-3" data-testid="sub-active-card">
            <CheckCircle2 className="w-5 h-5 text-[#00ff66] shrink-0"/>
            <div>
              <div className="font-heading font-bold">You're subscribed</div>
              <div className="font-mono text-xs text-[#a3a3a3]">Renews on {new Date(user.subscription_ends_at).toLocaleDateString()}</div>
            </div>
          </div>
        )}
        {trial && (
          <div className="co-card p-5 border-[#ffb800] flex items-center gap-3" data-testid="sub-trial-card">
            <Clock className="w-5 h-5 text-[#ffb800] shrink-0"/>
            <div>
              <div className="font-heading font-bold">Trial active</div>
              <div className="font-mono text-xs text-[#a3a3a3]">{daysLeft} day{daysLeft === 1 ? "" : "s"} left. Subscribe before expiry to keep daily slips unlocked.</div>
            </div>
          </div>
        )}

        <div className="grid md:grid-cols-2 gap-6">
          <FlutterwavePane />
          <BankTransferPane cfg={cfg} onSubmitted={() => { api.myPayments().then(setPays); refresh(); }}/>
        </div>

        {/* Payment history */}
        <div>
          <div className="flex items-center gap-2 mb-3">
            <ShieldCheck className="w-5 h-5 text-[#00ff66]" />
            <h2 className="font-heading font-bold text-xl">My Payments</h2>
          </div>
          <div className="co-card overflow-x-auto hidden sm:block">
            <table className="w-full text-sm">
              <thead><tr className="border-b border-[#262626]">
                {["Date","Method","Amount","Status","Reference"].map(h => <th key={h} className="text-left font-mono text-[10px] uppercase tracking-widest text-[#525252] px-3 py-3">{h}</th>)}
              </tr></thead>
              <tbody>
                {pays.length === 0 ? <tr><td colSpan={5} className="text-center py-8 text-[#525252] font-mono text-xs uppercase tracking-widest">No payments yet</td></tr> :
                  pays.map(p => (
                    <tr key={p.id} className="border-b border-[#1a1a1a]">
                      <td className="px-3 py-3 font-mono text-xs">{new Date(p.created_at).toLocaleDateString()}</td>
                      <td className="px-3 py-3 font-mono text-xs">{p.method}</td>
                      <td className="px-3 py-3 font-mono">₦{p.amount.toLocaleString()}</td>
                      <td className="px-3 py-3"><span className={`co-tag ${p.status === "successful" ? "co-tag-pos" : p.status === "rejected" ? "co-tag-neg" : "co-tag-warn"}`}>{p.status.toUpperCase()}</span></td>
                      <td className="px-3 py-3 font-mono text-xs text-[#a3a3a3]">{p.tx_ref || p.reference || "—"}</td>
                    </tr>
                  ))}
              </tbody>
            </table>
          </div>
          <div className="sm:hidden space-y-2">
            {pays.length === 0 ? (
              <div className="co-card p-8 text-center text-[#525252] font-mono text-xs uppercase tracking-widest">No payments yet</div>
            ) : pays.map(p => (
              <div key={p.id} className="co-card p-4" data-testid={`payment-card-${p.id}`}>
                <div className="flex items-center justify-between gap-3">
                  <div className="font-mono text-xs text-[#667482]">{new Date(p.created_at).toLocaleDateString()}</div>
                  <span className={`co-tag ${p.status === "successful" ? "co-tag-pos" : p.status === "rejected" ? "co-tag-neg" : "co-tag-warn"}`}>{p.status.toUpperCase()}</span>
                </div>
                <div className="font-heading font-bold text-lg mt-2">₦{p.amount.toLocaleString()}</div>
                <div className="font-mono text-[10px] uppercase tracking-widest text-[#667482] mt-1">{p.method} · {p.tx_ref || p.reference || "No reference"}</div>
              </div>
            ))}
          </div>
        </div>
      </main>
      <EmrizFooter />
    </div>
  );
}
