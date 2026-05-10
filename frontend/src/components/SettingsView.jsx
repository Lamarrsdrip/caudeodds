import React, { useState } from "react";
import { toast } from "sonner";

export default function SettingsView({ settings, onSave }) {
  const [form, setForm] = useState(settings);
  const update = (k, v) => setForm({ ...form, [k]: v });

  const save = async () => {
    await onSave(form);
    toast.success("Settings saved");
  };

  if (!form) return null;

  return (
    <div className="space-y-6 max-w-3xl" data-testid="settings-view">
      <h2 className="font-heading font-black text-3xl tracking-tight">SYSTEM SETTINGS</h2>

      <div className="co-card p-6 space-y-5">
        <div>
          <label className="font-mono text-[10px] uppercase tracking-widest text-[#525252]">Bankroll ($)</label>
          <input
            type="number"
            value={form.bankroll}
            onChange={e => update("bankroll", parseFloat(e.target.value))}
            data-testid="settings-bankroll"
            className="w-full bg-[#0a0a0a] border border-[#262626] focus:border-[#525252] outline-none font-mono px-3 py-2 mt-1 text-[#f5f5f5]"
          />
        </div>

        <div>
          <label className="font-mono text-[10px] uppercase tracking-widest text-[#525252]">
            Kelly Fraction (0–1, recommended 0.25 = quarter Kelly)
          </label>
          <input
            type="number" step="0.05" min="0" max="1"
            value={form.kelly_fraction}
            onChange={e => update("kelly_fraction", parseFloat(e.target.value))}
            data-testid="settings-kelly"
            className="w-full bg-[#0a0a0a] border border-[#262626] focus:border-[#525252] outline-none font-mono px-3 py-2 mt-1 text-[#f5f5f5]"
          />
        </div>

        <div className="grid grid-cols-3 gap-4">
          <div>
            <label className="font-mono text-[10px] uppercase tracking-widest text-[#525252]">Min Confidence %</label>
            <input
              type="number" min="0" max="100"
              value={form.min_confidence}
              onChange={e => update("min_confidence", parseFloat(e.target.value))}
              data-testid="settings-minconf"
              className="w-full bg-[#0a0a0a] border border-[#262626] focus:border-[#525252] outline-none font-mono px-3 py-2 mt-1"
            />
          </div>
          <div>
            <label className="font-mono text-[10px] uppercase tracking-widest text-[#525252]">Min Agreement %</label>
            <input
              type="number" min="0" max="100"
              value={form.min_agreement}
              onChange={e => update("min_agreement", parseFloat(e.target.value))}
              data-testid="settings-minagree"
              className="w-full bg-[#0a0a0a] border border-[#262626] focus:border-[#525252] outline-none font-mono px-3 py-2 mt-1"
            />
          </div>
          <div>
            <label className="font-mono text-[10px] uppercase tracking-widest text-[#525252]">Min EV (decimal)</label>
            <input
              type="number" step="0.01" min="0"
              value={form.min_ev}
              onChange={e => update("min_ev", parseFloat(e.target.value))}
              data-testid="settings-minev"
              className="w-full bg-[#0a0a0a] border border-[#262626] focus:border-[#525252] outline-none font-mono px-3 py-2 mt-1"
            />
          </div>
        </div>

        <div>
          <label className="font-mono text-[10px] uppercase tracking-widest text-[#525252]">Max Picks Per Day</label>
          <input
            type="number" min="1" max="10"
            value={form.max_picks_per_day}
            onChange={e => update("max_picks_per_day", parseInt(e.target.value))}
            data-testid="settings-maxpicks"
            className="w-full bg-[#0a0a0a] border border-[#262626] focus:border-[#525252] outline-none font-mono px-3 py-2 mt-1"
          />
        </div>

        <div>
          <label className="font-mono text-[10px] uppercase tracking-widest text-[#525252]">Sport Filter</label>
          <div className="flex gap-2 mt-1">
            {["all", "football", "basketball"].map(s => (
              <button
                key={s}
                onClick={() => update("sport_filter", s)}
                data-testid={`settings-sport-${s}`}
                className={`font-mono uppercase tracking-widest text-[10px] px-4 py-2 border ${
                  form.sport_filter === s ? "bg-[#f5f5f5] text-[#050505] border-[#f5f5f5]" : "border-[#262626] text-[#a3a3a3] hover:bg-[#1a1a1a]"
                }`}
              >{s}</button>
            ))}
          </div>
        </div>

        <button
          onClick={save}
          data-testid="settings-save"
          className="bg-[#f5f5f5] text-[#050505] font-mono uppercase tracking-widest text-xs px-6 py-3 hover:bg-[#00ff66] transition-colors"
        >
          Save Settings
        </button>
      </div>

      <div className="co-card p-6 bg-grid">
        <h3 className="font-heading font-bold mb-3">Discipline Reminders</h3>
        <ul className="text-xs text-[#a3a3a3] space-y-2 font-mono">
          <li>— Quarter Kelly (0.25) is recommended for most bettors. Full Kelly maximizes growth but with high variance.</li>
          <li>— Lowering Min Confidence below 70% will produce more picks but worse expected value.</li>
          <li>— Min EV of 0.04 = require at least 4% expected value over fair odds. Increase for fewer, higher-quality picks.</li>
          <li>— The system caps any single bet at 5% of bankroll regardless of Kelly recommendation.</li>
        </ul>
      </div>
    </div>
  );
}
