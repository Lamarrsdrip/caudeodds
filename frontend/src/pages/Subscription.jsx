import React, { useEffect, useState } from "react";
import AppHeader from "@/components/AppHeader";
import EmrizFooter from "@/components/EmrizFooter";
import { api } from "@/lib/api";

function FlutterwavePane({ onPaid }) {
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
    <div className="co-card p-6 space-y-4" data-testid="pay-flutterwave">
      <div className="flex items-center gap-3">
        <CreditCard className="w-5 h-5 text-[#00ff66]" />
        <div>
          <div className="font-heading font-bold">Pay with Card / Bank (Flutterwave)</div>
          <div className="font-mono text-[10px] uppercase tracking-widest text-[#525252]">// Instant activation · NGN cards · Bank transfer · USSD</div>
        </div>
      </div>
      <p className="text-sm text-[#a3a3a3]">Hosted secure checkout by Flutterwave. Subscription activates the instant payment is verified.</p>
      <button onClick={launch} disabled={busy} data-testid="flw-pay-btn" className="bg-[#00ff66] text-[#050505] font-mono uppercase tracking-widest text-xs px-6 py-3 hover:bg-[#f5f5f5] inline-flex items-center gap-2 disabled:opacity-50">
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
    <div className="co-card p-6 space-y-4" data-testid="pay-bank">
      <div className="flex items-center gap-3">
        <Building2 className="w-5 h-5 text-[#00ff66]" />
        <div>
          <div className="font-heading font-bold">Manual Bank Transfer</div>
          <div className="font-mono text-[10px] uppercase tracking-widest text-[#525252]">// Verified by admin · Activates within hours</div>
        </div>
      </div>

      {(cfg?.bank_account_number) ? (
        <div className="border border-[#262626] p-4 space-y-1 font-mono text-sm bg-[#0a0a0a]">
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
          <input value={sender} onChange={e => setSender(e.target.value)} data-testid="bank-sender" className="w-full bg-[#0a0a0a] border border-[#262626] focus:border-[#525252] outline-none font-mono px-3 py-2 mt-1" />
        </div>
        <div>
          <label className="font-mono text-[10px] uppercase tracking-widest text-[#525252]">Transfer Reference / Narration</label>
          <input value={reference} onChange={e => setReference(e.target.value)} data-testid="bank-ref" className="w-full bg-[#0a0a0a] border border-[#262626] focus:border-[#525252] outline-none font-mono px-3 py-2 mt-1" />
        </div>
        <div>
          <label className="font-mono text-[10px] uppercase tracking-widest text-[#525252]">Upload Receipt (image, max 3MB)</label>
          <input type="file" accept="image/*" onChange={e => handleFile(e.target.files?.[0])} data-testid="bank-proof"
                 className="w-full bg-[#0a0a0a] border border-[#262626] file:bg-[#262626] file:border-0 file:text-[#f5f5f5] file:px-3 file:py-2 file:font-mono file:text-[10px] file:uppercase file:tracking-widest file:mr-3 px-3 py-2 mt-1" />
          {proof && <div className="text-xs text-[#00ff66] font-mono mt-2 inline-flex items-center gap-1"><CheckCircle2 className="w-3.5 h-3.5"/> Receipt loaded</div>}
        </div>
      </div>

      <button onClick={submit} disabled={busy} data-testid="bank-submit" className="bg-[#f5f5f5] text-[#050505] font-mono uppercase tracking-widest text-xs px-6 py-3 hover:bg-[#00ff66] inline-flex items-center gap-2 disabled:opacity-50">
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

  useEffect(() => {
    api.publicConfig().then(setCfg);
    api.myPayments().then(setPays).catch(() => setPays([]));
  }, []);

  return (
    <div className="min-h-screen bg-[#050505] text-[#f5f5f5]">
      <AppHeader />
      <main className="max-w-[1100px] mx-auto px-6 py-10 space-y-8">
        <div>
          <h1 className="font-heading font-black text-4xl tracking-tight mb-2" data-testid="sub-title">SUBSCRIPTION</h1>
          <p className="font-mono text-[11px] uppercase tracking-widest text-[#525252]">// {cfg?.plan_label || "VIP Daily Slip"} · ₦{(cfg?.price_ngn || 5000).toLocaleString()} per month · Cancel anytime</p>
        </div>

        {user?.subscription_status === "active" && (
          <div className="co-card p-5 border-[#00ff66] flex items-center gap-3">
            <CheckCircle2 className="w-5 h-5 text-[#00ff66]"/>
            <div>
              <div className="font-heading font-bold">You're subscribed</div>
              <div className="font-mono text-xs text-[#a3a3a3]">Renews on {new Date(user.subscription_ends_at).toLocaleDateString()}</div>
            </div>
          </div>
        )}

        <div className="grid md:grid-cols-2 gap-6">
          <FlutterwavePane onPaid={refresh}/>
          <BankTransferPane cfg={cfg} onSubmitted={() => api.myPayments().then(setPays)}/>
        </div>

        {/* Payment history */}
        <div>
          <h2 className="font-heading font-bold text-xl mb-3">My Payments</h2>
          <div className="co-card overflow-x-auto">
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
        </div>
      </main>
      <EmrizFooter />
    </div>
  );
}
