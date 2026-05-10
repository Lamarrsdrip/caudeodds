import React, { useEffect, useState } from "react";
import { Smartphone, Download, Plus, Share2, X } from "lucide-react";

const STORAGE_KEY = "claudeodds_install_dismissed_at";
const DISMISS_DAYS = 5;

function detectIOS() {
  if (typeof navigator === "undefined") return false;
  const ua = navigator.userAgent;
  const isIOSDevice = /iPad|iPhone|iPod/.test(ua);
  const isIPadOS = ua.includes("Mac") && navigator.maxTouchPoints > 1;
  return isIOSDevice || isIPadOS;
}

function isStandalone() {
  if (typeof window === "undefined") return false;
  return (
    window.matchMedia?.("(display-mode: standalone)").matches ||
    window.navigator.standalone === true
  );
}

function recentlyDismissed() {
  const at = localStorage.getItem(STORAGE_KEY);
  if (!at) return false;
  return Date.now() - parseInt(at, 10) < DISMISS_DAYS * 24 * 60 * 60 * 1000;
}

export default function InstallPrompt() {
  const [deferred, setDeferred] = useState(null);
  const [visible, setVisible] = useState(false);
  const [showFullIOS, setShowFullIOS] = useState(false);

  useEffect(() => {
    if (isStandalone() || recentlyDismissed()) return;

    if (detectIOS()) {
      const t = setTimeout(() => setVisible(true), 3500);
      return () => clearTimeout(t);
    }

    const handler = (e) => {
      e.preventDefault();
      setDeferred(e);
      setVisible(true);
    };
    window.addEventListener("beforeinstallprompt", handler);
    return () => window.removeEventListener("beforeinstallprompt", handler);
  }, []);

  const dismiss = () => {
    localStorage.setItem(STORAGE_KEY, String(Date.now()));
    setVisible(false);
    setShowFullIOS(false);
  };

  const installAndroid = async () => {
    if (!deferred) return;
    try {
      deferred.prompt();
      const { outcome } = await deferred.userChoice;
      if (outcome === "accepted") setVisible(false);
      else dismiss();
    } catch {
      dismiss();
    }
    setDeferred(null);
  };

  const ios = detectIOS();

  if (!visible && !showFullIOS) return null;

  // Android one-tap install banner
  if (!ios && deferred && visible) {
    return (
      <div className="fixed bottom-4 left-4 right-4 md:left-auto md:right-6 md:w-[380px] z-50" data-testid="install-banner-android">
        <div className="co-card p-4 flex items-center gap-3 border-[#00ff66]" style={{ boxShadow: "0 0 30px rgba(0,255,102,0.25)" }}>
          <div className="w-10 h-10 bg-[#00ff66] flex items-center justify-center shrink-0">
            <Download className="w-5 h-5 text-[#050505]" strokeWidth={2.5} />
          </div>
          <div className="flex-1 min-w-0">
            <div className="font-heading font-bold text-sm">Install ClaudeOdds App</div>
            <div className="font-mono text-[10px] uppercase tracking-widest text-[#525252]">// 1-tap install · Faster · Push alerts</div>
          </div>
          <button onClick={installAndroid} data-testid="install-now-btn" className="bg-[#00ff66] text-[#050505] font-mono uppercase tracking-widest text-[11px] px-4 py-2 hover:bg-[#f5f5f5] shrink-0">Install</button>
          <button onClick={dismiss} data-testid="install-dismiss" aria-label="Dismiss" className="text-[#525252] hover:text-[#a3a3a3] shrink-0 p-1">
            <X className="w-4 h-4" />
          </button>
        </div>
      </div>
    );
  }

  // iOS — show pill first; clicking pill opens the full instructions modal
  if (ios && showFullIOS) {
    return (
      <div className="fixed inset-0 bg-black/85 z-50 flex items-end sm:items-center justify-center p-4" onClick={dismiss}>
        <div onClick={(e) => e.stopPropagation()} className="co-card max-w-md w-full p-6 border-[#00ff66]" style={{ boxShadow: "0 0 40px rgba(0,255,102,0.3)" }} data-testid="install-banner-ios">
          <div className="flex items-start justify-between mb-5">
            <div className="flex items-center gap-3">
              <div className="w-12 h-12 bg-[#00ff66] flex items-center justify-center shrink-0">
                <Smartphone className="w-6 h-6 text-[#050505]" strokeWidth={2.5} />
              </div>
              <div>
                <div className="font-heading font-black text-lg">Install ClaudeOdds</div>
                <div className="font-mono text-[10px] uppercase tracking-widest text-[#525252]">// Add to your iPhone Home Screen</div>
              </div>
            </div>
            <button onClick={dismiss} aria-label="Close" className="text-[#525252] hover:text-[#f5f5f5] p-1"><X className="w-5 h-5" /></button>
          </div>
          <ol className="space-y-3">
            <li className="flex items-start gap-3"><span className="font-mono text-[10px] bg-[#262626] text-[#a3a3a3] w-6 h-6 flex items-center justify-center shrink-0 font-bold">1</span><div className="text-sm flex-1">Tap the <span className="inline-flex items-center gap-1 font-bold"><Share2 className="w-4 h-4 text-[#00ff66] inline"/> Share</span> button at the bottom of Safari.</div></li>
            <li className="flex items-start gap-3"><span className="font-mono text-[10px] bg-[#262626] text-[#a3a3a3] w-6 h-6 flex items-center justify-center shrink-0 font-bold">2</span><div className="text-sm flex-1">Scroll and tap <span className="inline-flex items-center gap-1 font-bold"><Plus className="w-4 h-4 text-[#00ff66] inline"/> Add to Home Screen</span>.</div></li>
            <li className="flex items-start gap-3"><span className="font-mono text-[10px] bg-[#262626] text-[#a3a3a3] w-6 h-6 flex items-center justify-center shrink-0 font-bold">3</span><div className="text-sm flex-1">Tap <span className="font-bold">Add</span>. Open ClaudeOdds from your Home Screen like a native app.</div></li>
          </ol>
          <button onClick={dismiss} data-testid="install-ios-got-it" className="w-full mt-6 bg-[#00ff66] text-[#050505] font-mono uppercase tracking-widest text-xs py-3 hover:bg-[#f5f5f5]">Got it</button>
        </div>
      </div>
    );
  }

  if (ios && visible) {
    return (
      <button onClick={() => setShowFullIOS(true)} data-testid="install-ios-pill" className="fixed bottom-4 left-4 right-4 md:left-auto md:right-6 md:w-auto z-40 co-card flex items-center gap-3 px-4 py-3 border-[#00ff66] hover:bg-[#1a1a1a]" style={{ boxShadow: "0 0 20px rgba(0,255,102,0.2)" }}>
        <div className="w-8 h-8 bg-[#00ff66] flex items-center justify-center shrink-0"><Smartphone className="w-4 h-4 text-[#050505]" strokeWidth={2.5} /></div>
        <div className="text-left flex-1">
          <div className="font-heading font-bold text-sm">Install on iPhone</div>
          <div className="font-mono text-[10px] uppercase tracking-widest text-[#525252]">// Tap for instructions</div>
        </div>
        <X onClick={(e) => { e.stopPropagation(); dismiss(); }} className="w-4 h-4 text-[#525252] hover:text-[#a3a3a3]"/>
      </button>
    );
  }

  return null;
}
