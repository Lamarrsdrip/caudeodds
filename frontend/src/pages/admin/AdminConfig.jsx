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
  { key: "odds_api", title: "Sports Data API (override / swap providers)", fields: [
    ["odds_api_provider", "Provider", "select", ["the_odds_api", "custom"]],
    ["odds_api_base_url", "API Base URL"],
    ["odds_api_key", "API Key", "password"],
  ], hint: "Leave key blank to use the THE_ODDS_API_KEY from backend/.env. Saving here overrides the env."},
  { key: "apifootball", title: "API-Football (real injuries / form / xG)", fields: [
    ["apifootball_base_url", "API Base URL"],
    ["apifootball_key", "API Key", "password"],
  ], hint: "Free tier: 100 req/day (≈1 pipeline run). Pro $19/mo: 7,500/day. Get key at api-football.com. When configured, AI is allowed up to ±6% probability shift; without it, only ±2% (very few picks)."},
  { key: "apibasketball", title: "API-Basketball (real form & H2H — NBA / EuroLeague)", fields: [
    ["apibasketball_base_url", "API Base URL"],
    ["apibasketball_key", "API Key", "password"],
  ], hint: "SEPARATE subscription from API-Football. Same vendor, $19/mo Pro. Get key at api-basketball.com. Without it, basketball stays on price-only data (orange Market-Data badge)."},
  { key: "llm", title: "AI Model Gateway", fields: [
    ["emergent_llm_key", "Emergent LLM Key", "password"],
  ], hint: "Required for prediction generation. Leave blank only if EMERGENT_LLM_KEY is configured in the backend environment."},
  { key: "cron", title: "Daily Auto-Generate (Cron)", fields: [
    ["cron_enabled", "Enabled", "bool"],
    ["cron_hour_utc", "Hour (UTC, 0-23)", "number"],
    ["cron_minute_utc", "Minute (0-59)", "number"],
    ["min_slip_data_richness", "Min slip data richness (0.0-1.0)", "number"],
  ], hint: "Default: 08:00 UTC = 09:00 Lagos. Min richness 0.4 = require partial intel before shipping a slip (refuses to publish price-only fakes). 0.7 = full intel only."},
  { key: "autosettle", title: "Auto-Settlement (Post-match results)", fields: [
    ["autosettle_enabled", "Enabled", "bool"],
    ["autosettle_interval_hours", "Sweep interval (hours)", "number"],
  ], hint: "Pulls final scores from API-Football and marks pending picks won/lost/void. Requires API-Football Pro. Default every 2 hours."},
  { key: "push", title: "Web Push Notifications", fields: [
    ["push_enabled", "Enabled", "bool"],
    ["push_subject_email", "VAPID Subject Email"],
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
  const [pushBusy, setPushBusy] = useState(false);
  const [afBusy, setAfBusy] = useState(false);
  const [afResult, setAfResult] = useState(null);
  const [abBusy, setAbBusy] = useState(false);
  const [abResult, setAbResult] = useState(null);
  const [settleBusy, setSettleBusy] = useState(false);

  useEffect(() => { api.adminConfig().then(setCfg); }, []);

  const upd = (k, v) => setCfg({ ...cfg, [k]: v });
  const save = async () => {
    try { const saved = await api.adminSaveConfig(cfg); setCfg(saved); toast.success("Configuration saved · cron rescheduled"); }
    catch (e) { toast.error(formatApiError(e)); }
  };

  const sendTestPush = async () => {
    setPushBusy(true);
    try {
      const r = await api.adminPushTest("ClaudeOdds — Test", "If you see this, push works.");
      toast.success(`Sent to ${r.sent}/${r.total} subscribers · invalid: ${r.invalid} · failed: ${r.failed}`);
    } catch (e) { toast.error(formatApiError(e)); }
    finally { setPushBusy(false); }
  };

  const runPreflight = async () => {
    setAfBusy(true); setAfResult(null);
    try {
      const r = await api.adminApifootballPreflight();
      setAfResult(r);
      if (r.ok) toast.success(`API-Football OK · ${r.sample_team} · ${r.requests}/${r.limit_day} used today`);
      else toast.error(r.error || "Pre-flight failed");
    } catch (e) { toast.error(formatApiError(e)); }
    finally { setAfBusy(false); }
  };

  const runBasketballPreflight = async () => {
    setAbBusy(true); setAbResult(null);
    try {
      const r = await api.adminApibasketballPreflight();
      setAbResult(r);
      if (r.ok) toast.success(`API-Basketball OK · ${r.sample_team} · ${r.requests}/${r.limit_day} used today`);
      else toast.error(r.error || "Pre-flight failed");
    } catch (e) { toast.error(formatApiError(e)); }
    finally { setAbBusy(false); }
  };

  const runSettleNow = async () => {
    setSettleBusy(true);
    try {
      const r = await api.adminSettleNow();
      toast.success(`Checked ${r.checked} · settled ${r.settled} · still pending ${r.still_pending} · skipped ${r.skipped}`);
    } catch (e) { toast.error(formatApiError(e)); }
    finally { setSettleBusy(false); }
  };

  if (!cfg) return null;

  return (
    <div className="space-y-6 max-w-3xl" data-testid="admin-config-view">
      <h1 className="font-heading font-black text-2xl sm:text-3xl tracking-tight">CONFIGURATION</h1>
      <p className="font-mono text-[10px] uppercase tracking-widest text-[#525252]">// Everything below is editable. Updates apply immediately.</p>

      {SECTIONS.map(sec => (
        <div key={sec.key} className="co-card p-5 sm:p-6 space-y-4" data-testid={`cfg-section-${sec.key}`}>
          <h2 className="font-heading font-bold text-lg">{sec.title}</h2>
          {sec.hint && <p className="font-mono text-[10px] text-[#525252] -mt-2">// {sec.hint}</p>}
          <div className="grid sm:grid-cols-2 gap-4">
            {sec.fields.map(([k, label, type, opts]) => (
              <div key={k} className={type === "textarea" ? "sm:col-span-2" : ""}>
                <label className="font-mono text-[10px] uppercase tracking-widest text-[#525252]">{label}</label>
                {type === "textarea" ? (
                  <textarea value={cfg[k] ?? ""} onChange={e => upd(k, e.target.value)} data-testid={`cfg-${k}`} rows={3}
                            className="w-full bg-[#0a0a0a] border border-[#262626] focus:border-[#525252] outline-none font-mono px-3 py-2 mt-1 text-sm"/>
                ) : type === "select" ? (
                  <select value={cfg[k] ?? opts[0]} onChange={e => upd(k, e.target.value)} data-testid={`cfg-${k}`}
                          className="w-full bg-[#0a0a0a] border border-[#262626] focus:border-[#525252] outline-none font-mono px-3 py-2 mt-1">
                    {opts.map(o => <option key={o} value={o}>{o}</option>)}
                  </select>
                ) : type === "bool" ? (
                  <select value={cfg[k] ? "true" : "false"} onChange={e => upd(k, e.target.value === "true")} data-testid={`cfg-${k}`}
                          className="w-full bg-[#0a0a0a] border border-[#262626] focus:border-[#525252] outline-none font-mono px-3 py-2 mt-1">
                    <option value="true">Enabled</option>
                    <option value="false">Disabled</option>
                  </select>
                ) : (
                  <input type={type === "number" ? "number" : type === "password" ? "password" : "text"}
                         value={cfg[k] ?? ""} onChange={e => upd(k, type === "number" ? parseFloat(e.target.value) || 0 : e.target.value)} data-testid={`cfg-${k}`}
                         className="w-full bg-[#0a0a0a] border border-[#262626] focus:border-[#525252] outline-none font-mono px-3 py-2 mt-1"/>
                )}
              </div>
            ))}
          </div>
          {sec.key === "autosettle" && (
            <button onClick={runSettleNow} disabled={settleBusy} data-testid="settle-now-btn"
                    className="bg-[#00ff66] text-[#050505] hover:bg-[#f5f5f5] font-mono text-[11px] uppercase tracking-widest px-4 py-2 disabled:opacity-50">
              {settleBusy ? "Settling…" : "Settle Pending Picks Now"}
            </button>
          )}
          {sec.key === "push" && (
            <button onClick={sendTestPush} disabled={pushBusy} data-testid="push-test-btn"
                    className="border border-[#262626] hover:bg-[#1a1a1a] font-mono text-[11px] uppercase tracking-widest px-4 py-2 disabled:opacity-50">
              {pushBusy ? "Sending…" : "Send Test Push to All Subscribers"}
            </button>
          )}
          {sec.key === "apifootball" && (
            <div className="space-y-3">
              <button onClick={runPreflight} disabled={afBusy} data-testid="apifootball-preflight-btn"
                      className="bg-[#00ff66] text-[#050505] hover:bg-[#f5f5f5] font-mono text-[11px] uppercase tracking-widest px-4 py-2 disabled:opacity-50">
                {afBusy ? "Checking…" : "Run Pre-flight Check"}
              </button>
              {afResult && (
                <div data-testid="apifootball-preflight-result" className={`p-4 border-l-4 ${afResult.ok ? "border-l-[#00ff66] bg-[#00ff66]/5" : "border-l-[#ff6b35] bg-[#ff6b35]/5"}`}>
                  <div className="font-heading font-bold text-sm mb-1">
                    {afResult.ok ? "✓ Live data wired in" : "✗ Cannot use this key for live predictions"}
                  </div>
                  <div className="font-mono text-[11px] text-[#a3a3a3] space-y-0.5">
                    <div>Key configured: {String(afResult.key_configured)}</div>
                    <div>Current season ({afResult.current_season}): {afResult.current_season_supported ? "✓ supported by your plan" : "✗ NOT in your plan"}</div>
                    {afResult.sample_team && <div>Sample team verified: {afResult.sample_team}</div>}
                    {afResult.requests !== null && <div>API quota today: {afResult.requests} / {afResult.limit_day}</div>}
                    {afResult.error && <div className="text-[#ff6b35] mt-2 leading-relaxed">{afResult.error}</div>}
                  </div>
                </div>
              )}
            </div>
          )}
          {sec.key === "apibasketball" && (
            <div className="space-y-3">
              <button onClick={runBasketballPreflight} disabled={abBusy} data-testid="apibasketball-preflight-btn"
                      className="bg-[#00ff66] text-[#050505] hover:bg-[#f5f5f5] font-mono text-[11px] uppercase tracking-widest px-4 py-2 disabled:opacity-50">
                {abBusy ? "Checking…" : "Run Pre-flight Check"}
              </button>
              {abResult && (
                <div data-testid="apibasketball-preflight-result" className={`p-4 border-l-4 ${abResult.ok ? "border-l-[#00ff66] bg-[#00ff66]/5" : "border-l-[#ff6b35] bg-[#ff6b35]/5"}`}>
                  <div className="font-heading font-bold text-sm mb-1">
                    {abResult.ok ? "✓ Live data wired in" : "✗ Cannot use this key for live predictions"}
                  </div>
                  <div className="font-mono text-[11px] text-[#a3a3a3] space-y-0.5">
                    <div>Key configured: {String(abResult.key_configured)}</div>
                    <div>Current season ({abResult.current_season}): {abResult.current_season_supported ? "✓ supported by your plan" : "✗ NOT in your plan"}</div>
                    {abResult.sample_team && <div>Sample team verified: {abResult.sample_team}</div>}
                    {abResult.requests !== null && <div>API quota today: {abResult.requests} / {abResult.limit_day}</div>}
                    {abResult.error && <div className="text-[#ff6b35] mt-2 leading-relaxed">{abResult.error}</div>}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      ))}

      <button onClick={save} data-testid="cfg-save" className="bg-[#00ff66] text-[#050505] font-mono uppercase tracking-widest text-xs px-6 py-3 hover:bg-[#f5f5f5] sticky bottom-0 sm:static">
        Save Configuration
      </button>
    </div>
  );
}
