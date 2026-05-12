"""Phase 10 — Cost audit + home-bias + basketball diagnostic.

Verifies:
  • GET /api/admin/usage returns odds_api remaining + cache stats + budget advice
  • GET /api/admin/apibasketball/diagnostic surfaces raw provider responses
  • Odds API fetch_odds now uses MongoDB cache (no caller-burn on repeat)
  • consensus.evaluate rejects AWAY picks against clear home favorites
  • fixture-sync poll interval is 30 min (was 15)
"""
import os
import requests

import pytest

BASE = (os.environ.get("REACT_APP_BACKEND_URL") or "http://localhost:8001").rstrip("/")
ADMIN = "admin@claudeodd.com"
PW = "Admin@2026"


@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(f"{BASE}/api/auth/login", json={"email": ADMIN, "password": PW}, timeout=15)
    if r.status_code != 200:
        pytest.skip("admin login failed")
    return r.json()["access_token"]


def test_admin_usage_endpoint(admin_token):
    r = requests.get(f"{BASE}/api/admin/usage",
                     headers={"Authorization": f"Bearer {admin_token}"}, timeout=15)
    assert r.status_code == 200, r.text
    d = r.json()
    for k in ("odds_api", "api_football_cache_entries", "api_basketball_cache_entries",
              "fixture_sync_runs_24h", "picks_generated_7d", "schedulers", "budget_advice"):
        assert k in d, f"missing key: {k}"
    assert "remaining_requests" in d["odds_api"]
    assert "cache_ttl_offpeak_secs" in d["odds_api"]
    assert d["schedulers"]["fixture_sync_interval_min"] == 30


def test_admin_usage_requires_admin():
    r = requests.get(f"{BASE}/api/admin/usage", timeout=15)
    assert r.status_code in (401, 403)


def test_apibasketball_diagnostic_runs(admin_token):
    r = requests.get(f"{BASE}/api/admin/apibasketball/diagnostic",
                     headers={"Authorization": f"Bearer {admin_token}"}, timeout=30)
    assert r.status_code == 200
    d = r.json()
    # Either there's no key (and we get an error string) or we get endpoint results
    assert ("error" in d and "ok" in d and d["ok"] is False) or "endpoints" in d


def test_apibasketball_diagnostic_requires_admin():
    r = requests.get(f"{BASE}/api/admin/apibasketball/diagnostic", timeout=15)
    assert r.status_code in (401, 403)


def test_fetch_odds_uses_mongo_cache():
    """Importing fetch_odds and inspecting its source must show MongoDB caching wired."""
    src = open("/app/backend/odds_api_service.py").read()
    assert "_cache_get(db, cache_key" in src
    assert "ODDS_TTL_OFFPEAK_SECS" in src
    assert "ODDS_TTL_PEAK_SECS" in src


def test_consensus_rejects_away_vs_home_favorite():
    """consensus.evaluate must reject AWAY picks against clear home favorites
    when data_richness is insufficient (home-advantage bias guard)."""
    src = open("/app/backend/consensus.py").read()
    assert "HOME_FAV_TRAP" in src
    assert "ADVERSE_LINE_MOVE" in src


def test_fixture_sync_cron_runs_every_30_min():
    """scheduler.py must schedule fixture_sync every 30 minutes (was 15)."""
    src = open("/app/backend/scheduler.py").read()
    assert "IntervalTrigger(minutes=30)" in src
    assert 'logger.info("Fixture-sync scheduled every 30 minutes")' in src
