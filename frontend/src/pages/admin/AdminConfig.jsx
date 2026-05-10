import React, { useEffect, useState } from "react";
import { api, formatApiError } from "@/lib/api";
import { toast } from "sonner";

const SECTIONS = [
  { key: "pricing", title: "Pricing & Trial", fields: [
    ["price_ngn", "Monthly Price (NGN)", "number"],
    ["plan_label", "Plan Label"],
    ["trial_days", "Trial Days", "number"],
    ["brand_tagline", "Brand Tagline"],
    ["sportybet_handle", "SportyBet URL"],
  ]},
  { key: "bank", title: "Bank Transfer Details", fields: [
    ["bank_name", "Bank Name"],
    ["bank_account_number", "Account Number"],
    ["bank_account_name", "Account Name"],
    ["bank_instructions", "Instructions to user", "textarea"],
  ]},
  { key: "flw", title: "Flutterwave (NGN payments)", fields: [
    ["flw_environment", "Environment", "select", ["sandbox", "production"]],
    ["flw_public_key", "Public Key"],
    ["flw_secret_key", "Secret Key", "password"],
    ["flw_encryption_key", "Encryption Key"],
    ["flw_webhook_secret", "Webhook Secret Hash"],
  ]},
  { key: "smtp", title: "Email / SMTP (Phase 2)", fields: [
    ["smtp_host", "SMTP Host"],
    ["smtp_port", "Port", "number"],
    ["smtp_user", "Username"],
    ["smtp_password", "Password", "password"],
    ["smtp_from_email", "From Email"],
  ]},
  { key: "telegram", title: "Telegram (Phase 2)", fields: [
    ["telegram_bot_token", "Bot Token", "password"],
    ["telegram_channel_id", "Channel ID"],
  ]},
];

export default function AdminConfig() {
  const [cfg, setCfg] = useState(null);

  useEffect(() => { api.adminConfig().then(setCfg); }, []);

  const upd = (k, v) => setCfg({ ...cfg, [k]: v });
  const save = async () => {
    try { const saved = await api.adminSaveConfig(cfg); setCfg(saved); toast.success("Configuration saved"); }
    catch (e) { toast.error(formatApiError(e)); }
  };

  if (!cfg) return null;

  return (
    <div className="space-y-6 max-w-3xl" data-testid="admin-config-view">
      <h1 className="font-heading font-black text-3xl tracking-tight">CONFIGURATION</h1>
      <p className="font-mono text-[10px] uppercase tracking-widest text-[#525252]">// Everything below is editable. Updates apply immediately.</p>

      {SECTIONS.map(sec => (
        <div key={sec.key} className="co-card p-6 space-y-4" data-testid={`cfg-section-${sec.key}`}>
          <h2 className="font-heading font-bold text-lg">{sec.title}</h2>
          <div className="grid md:grid-cols-2 gap-4">
            {sec.fields.map(([k, label, type, opts]) => (
              <div key={k} className={type === "textarea" ? "md:col-span-2" : ""}>
                <label className="font-mono text-[10px] uppercase tracking-widest text-[#525252]">{label}</label>
                {type === "textarea" ? (
                  <textarea value={cfg[k] ?? ""} onChange={e => upd(k, e.target.value)} data-testid={`cfg-${k}`} rows={3}
                            className="w-full bg-[#0a0a0a] border border-[#262626] focus:border-[#525252] outline-none font-mono px-3 py-2 mt-1 text-sm"/>
                ) : type === "select" ? (
                  <select value={cfg[k] ?? opts[0]} onChange={e => upd(k, e.target.value)} data-testid={`cfg-${k}`}
                          className="w-full bg-[#0a0a0a] border border-[#262626] focus:border-[#525252] outline-none font-mono px-3 py-2 mt-1">
                    {opts.map(o => <option key={o} value={o}>{o}</option>)}
                  </select>
                ) : (
                  <input type={type === "number" ? "number" : type === "password" ? "password" : "text"}
                         value={cfg[k] ?? ""} onChange={e => upd(k, type === "number" ? parseFloat(e.target.value) || 0 : e.target.value)} data-testid={`cfg-${k}`}
                         className="w-full bg-[#0a0a0a] border border-[#262626] focus:border-[#525252] outline-none font-mono px-3 py-2 mt-1"/>
                )}
              </div>
            ))}
          </div>
        </div>
      ))}

      <button onClick={save} data-testid="cfg-save" className="bg-[#00ff66] text-[#050505] font-mono uppercase tracking-widest text-xs px-6 py-3 hover:bg-[#f5f5f5]">
        Save Configuration
      </button>
    </div>
  );
}
