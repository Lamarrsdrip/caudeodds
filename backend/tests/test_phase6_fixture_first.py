"""Phase 6 — Fixture-first pipeline (schedule independent of odds).

Verifies the new schedule sync + status badges that solve the "empty until
bookmakers publish odds" UX problem.
"""
import os
from datetime import datetime, timezone, timedelta

import pytest
import requests

BASE = (os.environ.get("REACT_APP_BACKEND_URL") or "http://localhost:8001").rstrip("/")
ADMIN_EMAIL = "admin@claudeodd.com"
ADMIN_PASS = "Admin@2026"


@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(f"{BASE}/api/auth/login",
                      json={"email": ADMIN_EMAIL, "password": ADMIN_PASS}, timeout=15)
    if r.status_code != 200:
        pytest.skip(f"Admin login failed: {r.status_code} {r.text}")
    return r.json()["access_token"]


def test_schedule_upcoming_no_date_returns_multiday():
    r = requests.get(f"{BASE}/api/schedule/upcoming?days=3", timeout=20)
    assert r.status_code == 200, r.text
    d = r.json()
    assert "days" in d and d["days"] == 3
    assert "schedule" in d and isinstance(d["schedule"], list)
    assert len(d["schedule"]) == 3
    for day in d["schedule"]:
        assert "date" in day and "summary" in day and "fixtures" in day
        assert all(k in day["summary"] for k in
                   ("total", "waiting_odds", "ready", "analyzing", "rejected", "failed"))


def test_schedule_upcoming_specific_date():
    tomorrow = (datetime.now(timezone.utc) + timedelta(days=1)).strftime("%Y-%m-%d")
    r = requests.get(f"{BASE}/api/schedule/upcoming?date={tomorrow}", timeout=15)
    assert r.status_code == 200
    d = r.json()
    assert d["date"] == tomorrow
    assert "summary" in d and "fixtures" in d


def test_schedule_upcoming_rejects_bad_date():
    r = requests.get(f"{BASE}/api/schedule/upcoming?date=not-a-date", timeout=15)
    assert r.status_code == 400
    assert "YYYY-MM-DD" in r.text


def test_schedule_upcoming_days_clamped():
    r1 = requests.get(f"{BASE}/api/schedule/upcoming?days=0", timeout=15)
    r2 = requests.get(f"{BASE}/api/schedule/upcoming?days=99", timeout=15)
    assert r1.status_code == 200 and r1.json()["days"] == 1
    assert r2.status_code == 200 and r2.json()["days"] == 7


def test_admin_schedule_sync_authn(admin_token):
    # Anonymous should be denied
    r = requests.post(f"{BASE}/api/admin/schedule/sync", timeout=15)
    assert r.status_code in (401, 403)
    # Admin should succeed
    r2 = requests.post(f"{BASE}/api/admin/schedule/sync",
                       headers={"Authorization": f"Bearer {admin_token}"}, timeout=60)
    assert r2.status_code == 200, r2.text
    out = r2.json()
    # Should be a dict keyed by ISO date with schedule/odds/ai counts
    assert isinstance(out, dict)
    for date_key, stats in out.items():
        datetime.strptime(date_key, "%Y-%m-%d")
        assert "schedule" in stats and "odds" in stats and "ai" in stats


def test_fixture_status_badges_present():
    """Every fixture in the schedule must carry a recognised badge."""
    r = requests.get(f"{BASE}/api/schedule/upcoming?days=3", timeout=15)
    assert r.status_code == 200
    valid_badges = {"waiting", "analyzing", "ready", "rejected", "failed",
                    "no_prediction", "live", "completed"}
    for day in r.json()["schedule"]:
        for fx in day["fixtures"]:
            assert fx["badge"] in valid_badges, f"Unknown badge: {fx['badge']}"
            assert "odds_status" in fx and fx["odds_status"] in ("waiting", "available")
            assert "ai_status" in fx
            assert "kickoff" in fx and "home" in fx and "away" in fx
