import React, { useEffect, useState } from "react";
import { toast } from "sonner";
import { Shield, Mail, Activity as ActivityIcon, CheckCircle2, XCircle, Send, Lock, RotateCw } from "lucide-react";
import { api, formatApiError, tokenStore } from "@/lib/api";

/**
 * Admin Security Center
 * ─────────────────────
 * One-stop page for the production-critical admin controls:
 *   1. Change password (force-logs out other sessions via password_version bump)
 *   2. SMTP test (verify credentials without sending)
 *   3. SMTP send-test (deliver a real email and surface delivery status)
 *   4. Recent email logs (last 50 sent/failed)
 *   5. Login activity log (every success + failure with ip/ua)
 */
export default function AdminSecurity() {
  return (
    <div className="space-y-6" data-testid="admin-security-view">
      <div className="flex items-center gap-3">
        <Shield className="w-6 h-6 text-[#00ff66]" />
        <h1 className="font-heading font-black text-2xl sm:text-3xl tracking-tight">SECURITY CENTER</h1>
      </div>
      <p className="text-sm text-[#a3a3a3] max-w-2xl">
        Password management, SMTP health, and login-activity auditing. All settings here
        persist permanently in the database — they survive backend redeploys.
      </p>

      <ChangePasswordCard />
      <SmtpCard />
      <BulkEmailCard />
      <EmailLogsCard />
      <LoginActivityCard />
    </div>
  );
}

// ── 1. Change Password ──────────────────────────────────────────────────────

function ChangePasswordCard() {
  const [current, setCurrent] = useState("");
  const [next1, setNext1] = useState("");
  const [next2, setNext2] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async (e) => {
    e?.preventDefault();
    if (next1.length < 8) return toast.error("New password must be at least 8 characters.");
    if (next1 !== next2) return toast.error("New passwords don't match.");
    setBusy(true);
    try {
      const r = await api.changePassword(current, next1);
      // Re-store the new token so this tab stays signed in
      if (r.access_token) tokenStore.set(r.access_token);
      toast.success(r.message || "Password updated.");
      setCurrent(""); setNext1(""); setNext2("");
    } catch (e) {
      toast.error(formatApiError(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <form onSubmit={submit} className="co-card p-5 space-y-3" data-testid="change-password-card">
      <div className="flex items-center gap-2">
        <Lock className="w-4 h-4 text-[#00ff66]" />
        <div className="font-heading font-bold">Change Password</div>
      </div>
      <p className="text-xs text-[#525252] leading-relaxed">
        Changing your password immediately signs out every other browser / device using this account.
        New password is hashed (bcrypt) and persists across redeploys.
      </p>
      <div className="grid sm:grid-cols-3 gap-3">
        <input type="password" value={current} onChange={(e) => setCurrent(e.target.value)}
               placeholder="Current password" required minLength={1}
               data-testid="pw-current"
               className="bg-[#0a0a0a] border border-[#262626] focus:border-[#00ff66] outline-none px-3 py-2 font-mono text-sm" />
        <input type="password" value={next1} onChange={(e) => setNext1(e.target.value)}
               placeholder="New password (≥8 chars)" required minLength={8}
               data-testid="pw-new"
               className="bg-[#0a0a0a] border border-[#262626] focus:border-[#00ff66] outline-none px-3 py-2 font-mono text-sm" />
        <input type="password" value={next2} onChange={(e) => setNext2(e.target.value)}
               placeholder="Confirm new password" required minLength={8}
               data-testid="pw-confirm"
               className="bg-[#0a0a0a] border border-[#262626] focus:border-[#00ff66] outline-none px-3 py-2 font-mono text-sm" />
      </div>
      <button type="submit" disabled={busy} data-testid="pw-submit"
              className="bg-[#00ff66] text-[#050505] font-mono text-xs uppercase tracking-widest px-5 py-2 hover:bg-[#f5f5f5] disabled:opacity-50">
        {busy ? "Updating…" : "Update Password"}
      </button>
    </form>
  );
}

// ── 2. SMTP test + send-test ────────────────────────────────────────────────

function SmtpCard() {
  const [status, setStatus] = useState(null); // null | {ok, error_class, message, ...}
  const [busy, setBusy] = useState(false);
  const [testTo, setTestTo] = useState("");
  const [sending, setSending] = useState(false);

  const testConn = async () => {
    setBusy(true); setStatus(null);
    try {
      const r = await api.adminSmtpTest();
      setStatus(r);
      if (r.ok) toast.success(r.message); else toast.error(r.message);
    } catch (e) { toast.error(formatApiError(e)); }
    finally { setBusy(false); }
  };

  const sendTest = async () => {
    setSending(true);
    try {
      const r = await api.adminSmtpSendTest(testTo);
      if (r.status === "sent") toast.success(`Test email sent to ${r.to}`);
      else toast.error(`Send failed: ${r.error || r.error_class}`);
    } catch (e) { toast.error(formatApiError(e)); }
    finally { setSending(false); }
  };

  return (
    <div className="co-card p-5 space-y-4" data-testid="smtp-card">
      <div className="flex items-center gap-2">
        <Mail className="w-4 h-4 text-[#00ff66]" />
        <div className="font-heading font-bold">Google / SMTP Email Setup</div>
      </div>
      <p className="text-xs text-[#525252] leading-relaxed">
        Configure SMTP credentials in <strong>Configuration → SMTP settings</strong> first
        (Gmail: host <code>smtp.gmail.com</code>, port <code>587</code>, an <a className="text-[#00ff66] underline" href="https://myaccount.google.com/apppasswords" target="_blank" rel="noopener noreferrer">App Password</a>).
        Then click Test below to verify it works — you'll see <span className="text-[#00ff66]">Connected ✅</span> or a clear failure reason.
      </p>

      <div className="flex items-center gap-2 flex-wrap">
        <button onClick={testConn} disabled={busy} data-testid="smtp-test-btn"
                className="border border-[#262626] hover:bg-[#1a1a1a] font-mono text-xs uppercase tracking-widest px-4 py-2 inline-flex items-center gap-2 disabled:opacity-50">
          <RotateCw className={`w-3.5 h-3.5 ${busy ? "animate-spin" : ""}`} />
          {busy ? "Testing…" : "Test SMTP Connection"}
        </button>
        <input value={testTo} onChange={(e) => setTestTo(e.target.value)}
               placeholder="recipient@example.com (blank → your admin email)"
               data-testid="smtp-test-to"
               className="bg-[#0a0a0a] border border-[#262626] focus:border-[#00ff66] outline-none px-3 py-2 font-mono text-xs flex-1 min-w-[240px]" />
        <button onClick={sendTest} disabled={sending} data-testid="smtp-send-btn"
                className="bg-[#00ff66] text-[#050505] font-mono text-xs uppercase tracking-widest px-4 py-2 inline-flex items-center gap-2 hover:bg-[#f5f5f5] disabled:opacity-50">
          <Send className="w-3.5 h-3.5" />
          {sending ? "Sending…" : "Send Test Email"}
        </button>
      </div>

      {status && (
        <div className={`border-l-4 p-3 ${status.ok ? "border-l-[#00ff66] bg-[#00ff66]/5" : "border-l-[#ff3333] bg-[#ff3333]/5"}`} data-testid="smtp-status">
          <div className="flex items-center gap-2 mb-1">
            {status.ok
              ? <><CheckCircle2 className="w-4 h-4 text-[#00ff66]" /><span className="font-mono text-[11px] uppercase tracking-widest text-[#00ff66] font-bold">Connected ✅</span></>
              : <><XCircle className="w-4 h-4 text-[#ff3333]" /><span className="font-mono text-[11px] uppercase tracking-widest text-[#ff3333] font-bold">Failed ❌ · {status.error_class}</span></>}
          </div>
          <p className="text-xs text-[#a3a3a3] leading-relaxed">{status.message}</p>
          <p className="text-[10px] text-[#525252] mt-2 font-mono">{status.host || "—"}:{status.port || "—"} · {status.user || "—"}</p>
        </div>
      )}
    </div>
  );
}

function BulkEmailCard() {
  const [subject, setSubject] = useState("");
  const [message, setMessage] = useState("");
  const [audience, setAudience] = useState("active");
  const [preview, setPreview] = useState("");
  const [busy, setBusy] = useState(false);

  const payload = { subject, message, audience };
  const previewEmail = async () => {
    setBusy(true);
    try {
      const r = await api.adminBulkEmail({ ...payload, preview: true });
      setPreview(r.preview || "");
    } catch (e) { toast.error(formatApiError(e)); }
    finally { setBusy(false); }
  };
  const sendBulk = async () => {
    if (!window.confirm(`Send this announcement to ${audience} users?`)) return;
    setBusy(true);
    try {
      const r = await api.adminBulkEmail(payload);
      if (r.failed) toast.error(`Sent ${r.sent}, failed ${r.failed}`);
      else toast.success(`Announcement sent to ${r.sent} users`);
    } catch (e) { toast.error(formatApiError(e)); }
    finally { setBusy(false); }
  };

  return (
    <div className="co-card p-5 space-y-4" data-testid="bulk-email-card">
      <div className="flex items-center gap-2">
        <Send className="w-4 h-4 text-[#00ff66]" />
        <div className="font-heading font-bold">Bulk Announcement</div>
      </div>
      <div className="grid sm:grid-cols-[160px_1fr] gap-3">
        <select value={audience} onChange={(e) => setAudience(e.target.value)}
                className="bg-[#0a0a0a] border border-[#262626] focus:border-[#00ff66] outline-none px-3 py-2 font-mono text-xs">
          <option value="active">Active users</option>
          <option value="trial">Trial users</option>
          <option value="all">All users</option>
        </select>
        <input value={subject} onChange={(e) => setSubject(e.target.value)}
               placeholder="Subject"
               className="bg-[#0a0a0a] border border-[#262626] focus:border-[#00ff66] outline-none px-3 py-2 font-mono text-xs" />
      </div>
      <textarea value={message} onChange={(e) => setMessage(e.target.value)}
                placeholder="Write announcement, subscription update, promo, or important notice..."
                rows={5}
                className="w-full bg-[#0a0a0a] border border-[#262626] focus:border-[#00ff66] outline-none px-3 py-2 font-mono text-xs" />
      <div className="flex flex-wrap gap-2">
        <button onClick={previewEmail} disabled={busy}
                className="border border-[#262626] hover:bg-[#1a1a1a] font-mono text-xs uppercase tracking-widest px-4 py-2 disabled:opacity-50">
          Preview
        </button>
        <button onClick={sendBulk} disabled={busy}
                className="bg-[#00ff66] text-[#050505] font-mono text-xs uppercase tracking-widest px-4 py-2 hover:bg-[#f5f5f5] disabled:opacity-50">
          Send Announcement
        </button>
      </div>
      {preview && (
        <div className="border border-[#262626] bg-black/30 p-3">
          <div className="font-mono text-[10px] uppercase tracking-widest text-[#667482] mb-2">Email preview</div>
          <div className="max-h-72 overflow-auto" dangerouslySetInnerHTML={{ __html: preview }} />
        </div>
      )}
    </div>
  );
}

// ── 3. Email logs ───────────────────────────────────────────────────────────

function EmailLogsCard() {
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(true);

  const refresh = () => {
    setLoading(true);
    api.adminEmailLogs(50).then((d) => { setLogs(d); setLoading(false); }).catch(() => setLoading(false));
  };
  useEffect(() => { refresh(); }, []);

  return (
    <div className="co-card p-5" data-testid="email-logs-card">
      <div className="flex items-center justify-between mb-3 flex-wrap gap-2">
        <div className="flex items-center gap-2">
          <Mail className="w-4 h-4 text-[#00ff66]" />
          <div className="font-heading font-bold">Email Delivery Log</div>
        </div>
        <button onClick={refresh} className="font-mono text-[10px] uppercase tracking-widest text-[#a3a3a3] hover:text-[#00ff66]">Refresh</button>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead><tr className="border-b border-[#262626]">
            {["When", "To", "Subject", "Kind", "Status", "Error"].map(h =>
              <th key={h} className="text-left font-mono text-[10px] uppercase tracking-widest text-[#525252] px-2 py-2">{h}</th>)}
          </tr></thead>
          <tbody>
            {loading ? <tr><td colSpan={6} className="px-2 py-4 text-center text-[#525252] font-mono text-xs">Loading…</td></tr>
              : logs.length === 0 ? <tr><td colSpan={6} className="px-2 py-6 text-center text-[#525252] font-mono text-xs uppercase tracking-widest">No emails sent yet</td></tr>
              : logs.map(l => (
                <tr key={l.id} className="border-b border-[#1a1a1a]">
                  <td className="px-2 py-2 font-mono text-xs text-[#a3a3a3]">{new Date(l.sent_at).toLocaleString()}</td>
                  <td className="px-2 py-2 font-mono text-xs">{l.to}</td>
                  <td className="px-2 py-2 text-xs">{l.subject}</td>
                  <td className="px-2 py-2"><span className="co-tag">{l.kind}</span></td>
                  <td className="px-2 py-2">
                    <span className={`co-tag ${l.status === "sent" ? "co-tag-pos" : "co-tag-neg"}`}>{l.status}</span>
                  </td>
                  <td className="px-2 py-2 text-[11px] text-[#ff3333] max-w-[260px] truncate" title={l.error || ""}>{l.error_class || ""}</td>
                </tr>
              ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ── 4. Login activity ───────────────────────────────────────────────────────

function LoginActivityCard() {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const refresh = () => {
    setLoading(true);
    api.adminActivity(100).then((d) => { setRows(d); setLoading(false); }).catch(() => setLoading(false));
  };
  useEffect(() => { refresh(); }, []);

  const successCount = rows.filter(r => r.success).length;
  const failCount = rows.length - successCount;

  return (
    <div className="co-card p-5" data-testid="activity-card">
      <div className="flex items-center justify-between mb-3 flex-wrap gap-2">
        <div className="flex items-center gap-2">
          <ActivityIcon className="w-4 h-4 text-[#00ff66]" />
          <div className="font-heading font-bold">Login Activity</div>
          <span className="co-tag co-tag-pos">{successCount} OK</span>
          {failCount > 0 && <span className="co-tag co-tag-neg">{failCount} FAILED</span>}
        </div>
        <button onClick={refresh} className="font-mono text-[10px] uppercase tracking-widest text-[#a3a3a3] hover:text-[#00ff66]">Refresh</button>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead><tr className="border-b border-[#262626]">
            {["When", "Email", "Result", "Reason", "IP", "User-Agent"].map(h =>
              <th key={h} className="text-left font-mono text-[10px] uppercase tracking-widest text-[#525252] px-2 py-2">{h}</th>)}
          </tr></thead>
          <tbody>
            {loading ? <tr><td colSpan={6} className="px-2 py-4 text-center text-[#525252] font-mono text-xs">Loading…</td></tr>
              : rows.length === 0 ? <tr><td colSpan={6} className="px-2 py-6 text-center text-[#525252] font-mono text-xs uppercase tracking-widest">No login activity yet</td></tr>
              : rows.map(r => (
                <tr key={r.id} className="border-b border-[#1a1a1a]">
                  <td className="px-2 py-2 font-mono text-xs text-[#a3a3a3] whitespace-nowrap">{new Date(r.ts).toLocaleString()}</td>
                  <td className="px-2 py-2 font-mono text-xs">{r.email}</td>
                  <td className="px-2 py-2">
                    <span className={`co-tag ${r.success ? "co-tag-pos" : "co-tag-neg"}`}>
                      {r.success ? "OK" : "FAILED"}
                    </span>
                  </td>
                  <td className="px-2 py-2 font-mono text-[11px] text-[#525252]">{r.reason || ""}</td>
                  <td className="px-2 py-2 font-mono text-[11px] text-[#525252]">{r.ip || "—"}</td>
                  <td className="px-2 py-2 text-[11px] text-[#525252] max-w-[280px] truncate" title={r.ua}>{r.ua || ""}</td>
                </tr>
              ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
