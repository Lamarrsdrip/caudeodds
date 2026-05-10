import React, { useEffect, useState, useCallback } from "react";
import "@/App.css";
import { Toaster } from "@/components/ui/sonner";
import { toast } from "sonner";

import Header from "@/components/Header";
import SharpMarquee from "@/components/SharpMarquee";
import PicksBoard from "@/components/PicksBoard";
import HistoryTable from "@/components/HistoryTable";
import AnalyticsView from "@/components/AnalyticsView";
import RejectedLog from "@/components/RejectedLog";
import SettingsView from "@/components/SettingsView";
import { api } from "@/lib/api";

export default function App() {
  const [tab, setTab] = useState("picks");
  const [picks, setPicks] = useState([]);
  const [history, setHistory] = useState([]);
  const [rejected, setRejected] = useState([]);
  const [sharp, setSharp] = useState([]);
  const [roi, setRoi] = useState(null);
  const [parlay, setParlay] = useState(null);
  const [settings, setSettings] = useState(null);
  const [generating, setGenerating] = useState(false);
  const [lastRun, setLastRun] = useState(null);

  const refreshAll = useCallback(async () => {
    try {
      const [t, h, r, s, ro, p, cfg] = await Promise.all([
        api.today(), api.history({ limit: 200 }), api.rejected({ limit: 100 }),
        api.sharp(), api.roi(), api.parlay(), api.getConfig(),
      ]);
      setPicks(t); setHistory(h); setRejected(r); setSharp(s);
      setRoi(ro); setParlay(p); setSettings(cfg);
    } catch (e) {
      console.error("refresh failed", e);
    }
  }, []);

  useEffect(() => { refreshAll(); }, [refreshAll]);

  const handleGenerate = async () => {
    setGenerating(true);
    toast.loading("Running Claude + GPT ensemble…", { id: "gen" });
    try {
      const res = await api.generate(false);
      setLastRun({ fixtures_analyzed: res.fixtures_analyzed, rejected_count: res.rejected_count });
      if (res.cached) {
        toast.success(`Cached: ${res.picks.length} picks for ${res.date}`, { id: "gen" });
      } else {
        toast.success(`Generated ${res.picks.length} pick(s) from ${res.fixtures_analyzed} fixtures`, { id: "gen" });
      }
      await refreshAll();
    } catch (e) {
      toast.error(`Generation failed: ${e.response?.data?.detail || e.message}`, { id: "gen" });
    } finally {
      setGenerating(false);
    }
  };

  const handleSettle = async (id, result) => {
    try {
      await api.settle(id, result);
      toast.success(`Marked ${result}`);
      await refreshAll();
    } catch (e) {
      toast.error("Settle failed");
    }
  };

  const handleSaveSettings = async (s) => {
    const saved = await api.saveConfig(s);
    setSettings(saved);
  };

  return (
    <div className="App min-h-screen bg-[#050505] text-[#f5f5f5]">
      <Header
        roi={roi}
        parlay={parlay}
        onGenerate={handleGenerate}
        generating={generating}
        onTabChange={setTab}
        tab={tab}
      />
      <SharpMarquee signals={sharp} />

      <main className="px-6 py-8 max-w-[1500px] mx-auto">
        {tab === "picks" && (
          <PicksBoard picks={picks} parlay={parlay} onSettle={handleSettle} generating={generating} lastRun={lastRun} />
        )}
        {tab === "history" && <HistoryTable picks={history} onSettle={handleSettle} />}
        {tab === "analytics" && <AnalyticsView roi={roi} sharp={sharp} />}
        {tab === "rejected" && <RejectedLog rejected={rejected} />}
        {tab === "settings" && <SettingsView settings={settings} onSave={handleSaveSettings} />}
      </main>

      <footer className="border-t border-[#262626] mt-16 px-6 py-6 text-center">
        <div className="font-mono text-[10px] uppercase tracking-widest text-[#525252]">
          CLAUDEODD · Disciplined ensemble · Bet responsibly · No system guarantees profit
        </div>
      </footer>

      <Toaster theme="dark" position="bottom-right" />
    </div>
  );
}
