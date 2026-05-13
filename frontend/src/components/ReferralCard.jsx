import React, { useEffect, useState } from "react";
import { Gift, Copy, CheckCircle2, Users } from "lucide-react";
import { toast } from "sonner";
import { api } from "@/lib/api";

/**
 * Compact referral card for the user dashboard.
 * Shows the user's invite code, share link, total referrals count, and rewards.
 */
export default function ReferralCard() {
  const [data, setData] = useState(null);
  const [copiedField, setCopiedField] = useState(null);
  const [showList, setShowList] = useState(false);

  useEffect(() => {
    api.referralMe().then(setData).catch(() => setData(null));
  }, []);

  const copy = async (val, field) => {
    try {
      await navigator.clipboard.writeText(val);
      setCopiedField(field);
      toast.success(`${field === "code" ? "Code" : "Link"} copied`);
      setTimeout(() => setCopiedField(null), 2000);
    } catch {
      toast.error("Copy failed");
    }
  };

  if (!data) return null;

  return (
    <div className="co-card p-5" data-testid="referral-card">
      <div className="flex items-center gap-2 mb-3">
        <Gift className="w-4 h-4 text-[#00ff66]" />
        <h3 className="font-heading font-bold text-base">REFER & EARN</h3>
        <span className="ml-auto font-mono text-[10px] uppercase tracking-widest text-[#525252] inline-flex items-center gap-1">
          <Users className="w-3 h-3" />
          <span data-testid="ref-count">{data.count}</span> referred
        </span>
      </div>

      <p className="text-xs text-[#a3a3a3] leading-relaxed mb-4">
        Share your code. Friends get <span className="text-[#00ff66] font-bold">{data.rules.referee_trial_days} days</span> free instead of 3, and you get
        <span className="text-[#00ff66] font-bold"> +{data.rules.referrer_bonus_days} day</span> added to your subscription per signup.
      </p>

      <div className="space-y-2">
        <div className="flex items-center gap-2">
          <div className="flex-1 bg-[#0a0a0a] border border-[#262626] px-3 py-3 font-mono text-base tracking-[0.2em] font-bold" data-testid="ref-code">
            {data.code}
          </div>
          <button onClick={() => copy(data.code, "code")} data-testid="ref-copy-code"
                  className="border border-[#262626] hover:border-[#525252] active:bg-[#262626] font-mono text-[11px] uppercase tracking-widest px-4 py-3 inline-flex items-center gap-2 min-h-[44px]">
            {copiedField === "code" ? <><CheckCircle2 className="w-3.5 h-3.5 text-[#00ff66]"/> Copied</> : <><Copy className="w-3.5 h-3.5"/> Code</>}
          </button>
        </div>
        <div className="flex items-center gap-2">
          <div className="flex-1 bg-[#0a0a0a] border border-[#262626] px-3 py-3 font-mono text-xs text-[#a3a3a3] truncate" data-testid="ref-link">
            {data.share_link}
          </div>
          <button onClick={() => copy(data.share_link, "link")} data-testid="ref-copy-link"
                  className="bg-[#00ff66] text-[#050505] font-mono text-[11px] uppercase tracking-widest px-4 py-3 hover:bg-[#f5f5f5] inline-flex items-center gap-2 min-h-[44px]">
            {copiedField === "link" ? <><CheckCircle2 className="w-3.5 h-3.5"/> Copied</> : <><Copy className="w-3.5 h-3.5"/> Link</>}
          </button>
        </div>
      </div>

      {data.count > 0 && (
        <div className="mt-4">
          <button onClick={() => setShowList((s) => !s)} data-testid="ref-toggle-list"
                  className="font-mono text-[10px] uppercase tracking-widest text-[#a3a3a3] hover:text-[#00ff66]">
            {showList ? "Hide" : "Show"} the {data.count} {data.count === 1 ? "person" : "people"} you've referred →
          </button>
          {showList && (
            <ul className="mt-3 space-y-1.5" data-testid="ref-list">
              {data.referred.map((r) => (
                <li key={r.email} className="flex items-center justify-between border-b border-[#1a1a1a] pb-1.5">
                  <span className="font-mono text-xs text-[#a3a3a3]">{r.name || r.email}</span>
                  <span className="font-mono text-[10px] uppercase tracking-widest text-[#525252]">
                    {new Date(r.created_at).toLocaleDateString()}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}
