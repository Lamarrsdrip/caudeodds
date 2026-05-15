import React, { useEffect, useState } from "react";
import { Bell, BellOff, BellRing } from "lucide-react";
import { toast } from "sonner";
import { api, formatApiError } from "@/lib/api";

function urlB64ToUint8Array(b64) {
  const padding = "=".repeat((4 - (b64.length % 4)) % 4);
  const base64 = (b64 + padding).replace(/-/g, "+").replace(/_/g, "/");
  const raw = window.atob(base64);
  const out = new Uint8Array(raw.length);
  for (let i = 0; i < raw.length; i++) out[i] = raw.charCodeAt(i);
  return out;
}

export default function PushOptIn({ vapidPublicKey, compact = false, onStatusChange }) {
  const [supported, setSupported] = useState(false);
  const [permission, setPermission] = useState(typeof Notification !== "undefined" ? Notification.permission : "default");
  const [subscribed, setSubscribed] = useState(false);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    const ok = "serviceWorker" in navigator && "PushManager" in window && "Notification" in window;
    setSupported(ok);
    if (!ok) {
      onStatusChange?.(false);
      return;
    }
    (async () => {
      try {
        const reg = await navigator.serviceWorker.register("/sw.js", { scope: "/" });
        await navigator.serviceWorker.ready;
        const sub = await reg.pushManager.getSubscription();
        setSubscribed(!!sub);
        onStatusChange?.(!!sub);
      } catch (e) {
        // SW failed to register (HTTP-only context, blocked, or sandboxed iframe).
        // Surface to console so admins debugging push can spot the cause; UI just hides.
        console.warn("Service worker registration failed:", e?.message || e);
        onStatusChange?.(false);
      }
    })();
  }, [onStatusChange]);

  if (!supported || !vapidPublicKey) return null;

  const enable = async () => {
    setBusy(true);
    try {
      const perm = await Notification.requestPermission();
      setPermission(perm);
      if (perm !== "granted") {
        toast.error("Notification permission denied");
        return;
      }
      const reg = await navigator.serviceWorker.ready;
      let sub = await reg.pushManager.getSubscription();
      if (!sub) {
        sub = await reg.pushManager.subscribe({
          userVisibleOnly: true,
          applicationServerKey: urlB64ToUint8Array(vapidPublicKey),
        });
      }
      await api.pushSubscribe(sub.toJSON());
      setSubscribed(true);
      onStatusChange?.(true);
      toast.success("Push notifications enabled — you'll get pinged when slips drop");
    } catch (e) {
      toast.error(formatApiError(e) || "Could not enable notifications");
    } finally { setBusy(false); }
  };

  const disable = async () => {
    setBusy(true);
    try {
      const reg = await navigator.serviceWorker.ready;
      const sub = await reg.pushManager.getSubscription();
      if (sub) {
        await api.pushUnsubscribe(sub.endpoint);
        await sub.unsubscribe();
      }
      setSubscribed(false);
      onStatusChange?.(false);
      toast.success("Notifications disabled");
    } catch (e) {
      toast.error(formatApiError(e) || "Could not disable notifications");
    } finally { setBusy(false); }
  };

  if (compact) {
    return subscribed ? (
      <button onClick={disable} disabled={busy} data-testid="push-toggle"
        className="inline-flex items-center gap-1 text-[10px] font-mono uppercase tracking-widest text-[#00ff66]">
        <BellRing className="w-3.5 h-3.5"/> ON
      </button>
    ) : (
      <button onClick={enable} disabled={busy} data-testid="push-toggle"
        className="inline-flex items-center gap-1 text-[10px] font-mono uppercase tracking-widest text-[#a3a3a3] hover:text-[#00ff66]">
        <Bell className="w-3.5 h-3.5"/> Enable Alerts
      </button>
    );
  }

  return (
    <div className="co-card p-4 flex items-center justify-between gap-3" data-testid="push-optin-card">
      <div className="flex items-center gap-3">
        <span className="w-10 h-10 rounded-[8px] bg-white/5 border border-white/10 grid place-items-center shrink-0">
          {subscribed ? <BellRing className="w-5 h-5 text-[#00ff66]"/> : <Bell className="w-5 h-5 text-[#aeb8c2]"/>}
        </span>
        <div>
          <div className="font-heading font-bold text-sm">
            {subscribed ? "Push notifications ON" : "Get pinged when today's slip drops"}
          </div>
          <div className="text-xs text-[#667482] font-mono">
            {subscribed ? "You'll be notified the moment the SportyBet code is live." : "Real-time alerts on your phone — no need to keep checking."}
          </div>
        </div>
      </div>
      {subscribed ? (
        <button onClick={disable} disabled={busy} data-testid="push-disable"
          className="co-secondary-action rounded-[6px] font-mono text-[11px] uppercase tracking-widest px-3 py-2 inline-flex items-center gap-1">
          <BellOff className="w-3.5 h-3.5"/> Off
        </button>
      ) : (
        <button onClick={enable} disabled={busy} data-testid="push-enable"
          className="co-primary-action rounded-[6px] font-mono text-[11px] uppercase tracking-widest px-4 py-2 disabled:opacity-50">
          {busy ? "Enabling…" : "Enable"}
        </button>
      )}
    </div>
  );
}
