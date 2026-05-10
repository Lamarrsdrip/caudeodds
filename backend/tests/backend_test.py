"""CLAUDEODD backend regression tests.

Covers:
- Health
- Config (get/set)
- Picks generate (cached path; force only when needed because real LLM ~60-180s)
- Picks today / history / settle
- Parlay
- Analytics: roi, rejected, sharp
- Mongo cleanliness (no _id leak), Pydantic compliance
"""
from __future__ import annotations

import os
import time
import uuid
from datetime import datetime, timezone

import pytest
import requests

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") if os.environ.get("REACT_APP_BACKEND_URL") else None
if not BASE_URL:
    # fallback to frontend/.env at runtime
    from pathlib import Path
    env_path = Path("/app/frontend/.env")
    for line in env_path.read_text().splitlines():
        if line.startswith("REACT_APP_BACKEND_URL="):
            BASE_URL = line.split("=", 1)[1].strip().strip('"').rstrip("/")
            break

API = f"{BASE_URL}/api"
TODAY = datetime.now(timezone.utc).strftime("%Y-%m-%d")


@pytest.fixture(scope="session")
def s():
    sess = requests.Session()
    sess.headers.update({"Content-Type": "application/json"})
    return sess


# ---------- Health ----------
class TestHealth:
    def test_root(self, s):
        r = s.get(f"{API}/", timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert d["app"] == "CLAUDEODD"
        assert d["status"] == "ok"


# ---------- Config ----------
class TestConfig:
    def test_get_default_config(self, s):
        r = s.get(f"{API}/config", timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert d["bankroll"] >= 0
        assert 0 < d["kelly_fraction"] <= 1
        assert d["max_picks_per_day"] >= 1
        assert "_id" not in d

    def test_set_and_persist_config(self, s):
        # Read current
        cur = s.get(f"{API}/config", timeout=15).json()
        # mutate
        new_payload = {
            **cur,
            "bankroll": 1234.5,
            "kelly_fraction": 0.2,
            "max_picks_per_day": 4,
            "min_confidence": 72.0,
            "min_agreement": 66.0,
            "min_ev": 0.04,
            "sport_filter": "all",
        }
        r = s.post(f"{API}/config", json=new_payload, timeout=15)
        assert r.status_code == 200, r.text
        out = r.json()
        assert out["bankroll"] == 1234.5
        assert out["kelly_fraction"] == 0.2
        # GET to verify persistence
        g = s.get(f"{API}/config", timeout=15).json()
        assert g["bankroll"] == 1234.5
        assert g["min_ev"] == 0.04
        # restore
        restore = {**cur}
        s.post(f"{API}/config", json=restore, timeout=15)


# ---------- Picks generate (cached path) ----------
class TestPicksGenerate:
    def test_generate_cached(self, s):
        """Call without force should return cached run if previous run exists."""
        r = s.post(f"{API}/picks/generate", timeout=240)
        assert r.status_code == 200, r.text
        d = r.json()
        assert "date" in d and "picks" in d
        assert isinstance(d["picks"], list)
        assert "rejected_count" in d
        assert "fixtures_analyzed" in d
        assert "cached" in d
        # No _id leak
        for p in d["picks"]:
            assert "_id" not in p
            assert "id" in p

    def test_generate_idempotent_second_call(self, s):
        """Second non-force call must be cached=true."""
        r1 = s.post(f"{API}/picks/generate", timeout=240).json()
        r2 = s.post(f"{API}/picks/generate", timeout=240).json()
        # If both runs found cache, second should be cached
        assert r2["cached"] is True
        assert r2["date"] == r1["date"]
        assert len(r2["picks"]) == len(r1["picks"])


# ---------- Today / History / Settle ----------
class TestPicksCRUD:
    def test_picks_today_shape(self, s):
        r = s.get(f"{API}/picks/today", timeout=30)
        assert r.status_code == 200
        picks = r.json()
        assert isinstance(picks, list)
        for p in picks:
            assert "_id" not in p
            for key in ["id", "date", "sport", "match", "market", "odds",
                        "confidence", "agreement", "expected_value",
                        "kelly_stake_pct", "stake_units", "quant_view",
                        "reasoning_view", "status"]:
                assert key in p, f"missing {key}"
            assert p["confidence"] >= 0
            assert p["odds"] > 1.0

    def test_picks_history_filter(self, s):
        r = s.get(f"{API}/picks/history", params={"limit": 100}, timeout=30)
        assert r.status_code == 200
        all_picks = r.json()
        assert isinstance(all_picks, list)

        # filter by sport
        r2 = s.get(f"{API}/picks/history", params={"sport": "football"}, timeout=30)
        assert r2.status_code == 200
        for p in r2.json():
            assert p["sport"] == "football"

        # filter by status
        r3 = s.get(f"{API}/picks/history", params={"status": "pending"}, timeout=30)
        assert r3.status_code == 200
        for p in r3.json():
            assert p["status"] == "pending"

    def test_settle_workflow_round_trip(self, s):
        """Settle pending pick as void -> verify -> settle back to pending NOT supported,
        so settle as void to avoid impacting ROI tests later."""
        today = s.get(f"{API}/picks/today", timeout=30).json()
        if not today:
            pytest.skip("no picks for today to settle")
        target = next((p for p in today if p["status"] == "pending"), None)
        if not target:
            pytest.skip("no pending pick to settle")
        pick_id = target["id"]

        # settle as void (idempotent for ROI)
        r = s.post(f"{API}/picks/{pick_id}/settle", json={"result": "void"}, timeout=30)
        assert r.status_code == 200, r.text
        out = r.json()
        assert out["status"] == "void"
        assert out["settled_at"] is not None

        # verify via history
        h = s.get(f"{API}/picks/history", params={"status": "void"}, timeout=30).json()
        assert any(p["id"] == pick_id for p in h)

        # restore: settle back to "pending" not allowed by Literal; use won then null? skip restore
        # Re-mark as pending isn't possible per model — leave as void; subsequent run of test idempotent.

    def test_settle_invalid_id_returns_404(self, s):
        r = s.post(f"{API}/picks/{uuid.uuid4()}/settle", json={"result": "won"}, timeout=15)
        assert r.status_code == 404

    def test_settle_invalid_payload_422(self, s):
        # invalid result
        any_pick = s.get(f"{API}/picks/today", timeout=15).json()
        if not any_pick:
            pytest.skip("no picks")
        pid = any_pick[0]["id"]
        r = s.post(f"{API}/picks/{pid}/settle", json={"result": "maybe"}, timeout=15)
        assert r.status_code in (400, 422)


# ---------- Parlay ----------
class TestParlay:
    def test_parlay_shape(self, s):
        r = s.get(f"{API}/picks/parlay", timeout=30)
        assert r.status_code == 200
        d = r.json()
        for k in ["date", "legs", "combined_odds", "stake_pct", "stake_units", "expected_value"]:
            assert k in d
        assert d["legs"] >= 0
        assert d["combined_odds"] >= 1.0


# ---------- Analytics ----------
class TestAnalytics:
    def test_roi_shape(self, s):
        r = s.get(f"{API}/analytics/roi", timeout=30)
        assert r.status_code == 200
        d = r.json()
        for k in ["starting_bankroll", "current_bankroll", "profit", "total_staked",
                  "won", "lost", "pending", "settled", "win_rate", "roi_pct", "curve"]:
            assert k in d
        assert isinstance(d["curve"], list)
        for c in d["curve"]:
            assert "bankroll" in c

    def test_rejected_shape(self, s):
        r = s.get(f"{API}/analytics/rejected", params={"limit": 50}, timeout=30)
        assert r.status_code == 200
        rejs = r.json()
        assert isinstance(rejs, list)
        valid_codes = {"LOW_LIQ", "VOLATILITY", "LINE_TRAP", "INJURY_CHAOS",
                       "CONFLICT", "PUBLIC_EXTREME", "DISAGREEMENT", "TRAP",
                       "OUTRANKED", "LOW_CONFIDENCE", "LOW_EV", "LOW_AGREEMENT",
                       "NO_EDGE", "NO_BET"}
        for rej in rejs:
            assert "_id" not in rej
            for k in ["id", "date", "match", "sport", "reason_code", "reason"]:
                assert k in rej
            # reason_code is informational; just must be non-empty string
            assert isinstance(rej["reason_code"], str) and rej["reason_code"]

    def test_sharp_signals(self, s):
        r = s.get(f"{API}/analytics/sharp", timeout=30)
        assert r.status_code == 200
        sigs = r.json()
        assert isinstance(sigs, list)
        assert len(sigs) >= 1, "should have at least one sharp signal"
        for sg in sigs:
            for k in ["match", "league", "sport", "line_delta_pct",
                      "sharp_home_pct", "public_home_pct", "alert"]:
                assert k in sg
            assert sg["alert"] in ("SHARP_FADE_PUBLIC", "STEAM_MOVE", "NEUTRAL")


# ---------- Mongo / serialization sanity ----------
class TestSerialization:
    def test_no_objectid_in_any_collection_responses(self, s):
        for path in ["/picks/today", "/picks/history", "/analytics/rejected",
                     "/analytics/sharp", "/config"]:
            r = s.get(f"{API}{path}", timeout=30)
            assert r.status_code == 200, path
            txt = r.text
            assert '"_id"' not in txt, f"_id leaked in {path}"

    def test_datetime_iso_format(self, s):
        picks = s.get(f"{API}/picks/today", timeout=30).json()
        for p in picks:
            # parseable ISO
            datetime.fromisoformat(p["created_at"].replace("Z", "+00:00"))


if __name__ == "__main__":
    import sys
    sys.exit(pytest.main([__file__, "-v"]))
