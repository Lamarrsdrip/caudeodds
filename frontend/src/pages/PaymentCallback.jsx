import React, { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { Loader2, CheckCircle2, XCircle } from "lucide-react";
import AppHeader from "@/components/AppHeader";
import { api } from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";

export default function PaymentCallback() {
  const [params] = useSearchParams();
  const nav = useNavigate();
  const { refresh } = useAuth();
  const [status, setStatus] = useState("verifying");
  const [msg, setMsg] = useState("Verifying your payment with Flutterwave…");

  useEffect(() => {
    const txRef = params.get("tx_ref");
    if (!txRef) { setStatus("error"); setMsg("Missing transaction reference"); return; }
    api.flwVerify(txRef).then(async (r) => {
      if (r.ok) {
        await refresh();
        setStatus("success");
        setMsg("Payment verified. Subscription active!");
        setTimeout(() => nav("/dashboard"), 2500);
      } else {
        setStatus("error");
        setMsg(r.error || "Verification failed. If you were charged, contact support.");
      }
    }).catch(e => { setStatus("error"); setMsg(e.message); });
  }, [params, nav, refresh]);

  return (
    <div className="min-h-screen bg-[#050505] text-[#f5f5f5]">
      <AppHeader />
      <main className="max-w-md mx-auto px-6 py-32 text-center" data-testid="pay-callback">
        {status === "verifying" && <Loader2 className="w-12 h-12 animate-spin mx-auto mb-4 text-[#00ff66]"/>}
        {status === "success" && <CheckCircle2 className="w-12 h-12 mx-auto mb-4 text-[#00ff66]"/>}
        {status === "error" && <XCircle className="w-12 h-12 mx-auto mb-4 text-[#ff3333]"/>}
        <h1 className="font-heading font-black text-2xl tracking-tight mb-2">{status.toUpperCase()}</h1>
        <p className="text-sm text-[#a3a3a3] font-mono">{msg}</p>
      </main>
    </div>
  );
}
