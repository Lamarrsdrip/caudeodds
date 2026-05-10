"""Phase 5 — PWA auto-update, Public ROI tracker, Next-day rollover.

These verify the new endpoints introduced in iter_6:
  • GET /api/public/roi
  • GET /api/slip/today   — rollover + is_tomorrow flag
  • POST /api/slip/generate  — date=tomorrow / date=YYYY-MM-DD support
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


def test_public_roi_endpoint_shape():
    r = requests.get(f"{BASE}/api/public/roi?days=30", timeout=15)
    assert r.status_code == 200, r.text
    data = r.json()
    assert "totals" in data and "history" in data
    t = data["totals"]
    for k in ("slips_settled", "won", "lost", "void", "pending",
              "profit_units", "roi_pct", "win_rate_pct"):
        assert k in t, f"missing key: {k}"
    assert data["window_days"] == 30
    datetime.strptime(data["from"], "%Y-%m-%d")
    datetime.strptime(data["to"], "%Y-%m-%d")


def test_public_roi_days_clamp():
    r1 = requests.get(f"{BASE}/api/public/roi?days=0", timeout=15)
    r2 = requests.get(f"{BASE}/api/public/roi?days=1000", timeout=15)
    assert r1.status_code == 200 and r2.status_code == 200
    assert r1.json()["window_days"] == 1
    assert r2.json()["window_days"] == 365


def test_slip_today_includes_is_tomorrow_flag():
    r = requests.get(f"{BASE}/api/slip/today", timeout=15)
    assert r.status_code == 200
    d = r.json()
    assert "is_tomorrow" in d
    assert isinstance(d["is_tomorrow"], bool)


def test_slip_generate_rejects_invalid_date(admin_token):
    r = requests.post(
        f"{BASE}/api/slip/generate?date=not-a-date",
        headers={"Authorization": f"Bearer {admin_token}"},
        timeout=15,
    )
    assert r.status_code == 400, r.text
    assert "YYYY-MM-DD" in r.text


def test_slip_generate_accepts_tomorrow(admin_token):
    r = requests.post(
        f"{BASE}/api/slip/generate?date=tomorrow",
        headers={"Authorization": f"Bearer {admin_token}"},
        timeout=15,
    )
    assert r.status_code == 200, r.text
    d = r.json()
    tomorrow = (datetime.now(timezone.utc) + timedelta(days=1)).strftime("%Y-%m-%d")
    assert d["date"] == tomorrow
    assert d["status"] in ("running", "completed")


def test_slip_generate_accepts_explicit_iso_date(admin_token):
    target = (datetime.now(timezone.utc) + timedelta(days=2)).strftime("%Y-%m-%d")
    r = requests.post(
        f"{BASE}/api/slip/generate?date={target}",
        headers={"Authorization": f"Bearer {admin_token}"},
        timeout=15,
    )
    assert r.status_code == 200, r.text
    assert r.json()["date"] == target


def test_public_roi_no_auth_required():
    r = requests.get(f"{BASE}/api/public/roi", timeout=15)
    assert r.status_code == 200


def test_public_roi_outcome_math_consistency():
    """If there's history, P/L matches win/loss math."""
    r = requests.get(f"{BASE}/api/public/roi?days=365", timeout=15)
    assert r.status_code == 200
    data = r.json()
    t = data["totals"]
    # ROI = profit/settled*100 ; if no settled slips both must be 0
    if t["slips_settled"] == 0:
        assert t["roi_pct"] == 0.0
        assert t["profit_units"] == 0.0
    # win + lost + void must equal slips_settled
    assert t["won"] + t["lost"] + t["void"] == t["slips_settled"]
    # ROI sign matches profit sign
    if t["profit_units"] > 0:
        assert t["roi_pct"] > 0
    elif t["profit_units"] < 0:
        assert t["roi_pct"] < 0
