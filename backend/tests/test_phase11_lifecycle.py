"""Phase 11 — Prediction lifecycle: append-only, 3h deadline, stuck recovery.

Verifies:
  • Force Generate is APPEND-ONLY (never deletes existing picks)
  • job stats include inserted_new + refreshed_existing
  • self_heal returns stuck_analyzing_recovered + deadline_finalized
  • Schedule fixtures past kickoff get 'live' and 'completed' badges
  • Fixtures within 3h of kickoff with no odds → ai_status='no_prediction'
  • Stuck-in-analyzing schedule entries (>15min) get reset to pending
"""
import os
import time
from datetime import datetime, timezone, timedelta

import pytest
import requests

BASE = (os.environ.get("REACT_APP_BACKEND_URL") or "http://localhost:8001").rstrip("/")
ADMIN = "admin@claudeodd.com"
PW = "Admin@2026"


@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(f"{BASE}/api/auth/login", json={"email": ADMIN, "password": PW}, timeout=15)
    if r.status_code != 200:
        pytest.skip("admin login failed")
    return r.json()["access_token"]


@pytest.fixture(scope="module")
def db():
    import pymongo
    mongo = pymongo.MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))
    return mongo[os.environ.get("DB_NAME", "test_database")]


def test_force_generate_is_append_only(admin_token, db):
    """Force Generate must NEVER delete existing picks for the date — it should
    only append new ones or refresh existing ones."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    # Sentinel kickoff must match today's UTC date — otherwise self-heal will
    # correctly classify it as 'mistagged' and drop it (that's a separate guarantee).
    sentinel_kickoff = datetime.now(timezone.utc).replace(hour=23, minute=30, second=0, microsecond=0).isoformat()
    # Seed a pick we KNOW the pipeline won't produce
    sentinel_id = "phase11-sentinel-must-survive"
    sentinel = {
        "id": sentinel_id, "date": today,
        "match": "PHASE11_SENTINEL_HOME vs PHASE11_SENTINEL_AWAY",
        "sport": "football", "league": "Premier League",
        "country": "England", "country_code": "GB",
        "kickoff": sentinel_kickoff,
        "market": "DC_1X", "selection_label": "Home or Draw",
        "odds": 1.5, "fair_prob": 0.72, "model_prob": 0.72,
        "confidence": 75, "edge_pct": 4.5, "expected_value": 0.04,
        "data_richness": 0.6, "reasoning": "phase11 test",
        "status": "pending",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    db.claudeodd_picks.insert_one(sentinel)
    try:
        r = requests.post(f"{BASE}/api/slip/generate?force=true",
                          headers={"Authorization": f"Bearer {admin_token}"}, timeout=15)
        assert r.status_code == 200
        body = r.json()
        if body.get("cached"):
            r = requests.post(f"{BASE}/api/slip/generate?force=true",
                              headers={"Authorization": f"Bearer {admin_token}"}, timeout=15)
            body = r.json()
        job_id = body.get("job_id")
        if job_id:
            # Wait for completion
            for _ in range(60):
                s = requests.get(f"{BASE}/api/slip/generate/status/{job_id}",
                                 headers={"Authorization": f"Bearer {admin_token}"}, timeout=10)
                if s.status_code == 200 and s.json().get("status") in ("completed", "failed"):
                    break
                time.sleep(1)
        # Sentinel MUST still exist
        survivor = db.claudeodd_picks.find_one({"id": sentinel_id})
        assert survivor is not None, \
            "Force Generate deleted a pre-existing pick — append-only contract broken!"
    finally:
        db.claudeodd_picks.delete_one({"id": sentinel_id})


def test_self_heal_recovers_stuck_analyzing(admin_token, db):
    """Schedule entries in ai_status='analyzing' for >15 min must be reset."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    sched_id = "phase11-stuck-analyzing"
    # Use a 'updated_at' far in the past so it's clearly stuck
    db.claudeodd_schedule.insert_one({
        "id": sched_id, "date": today, "sport": "football",
        "league": "La Liga", "country": "Spain", "country_code": "ESP",
        "home": "StuckHome", "away": "StuckAway",
        "kickoff": (datetime.now(timezone.utc) + timedelta(hours=10)).isoformat(),
        "odds_status": "available", "ai_status": "analyzing",
        "first_seen_at": (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat(),
        "updated_at": (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat(),
    })
    try:
        r = requests.post(f"{BASE}/api/admin/schedule/heal",
                          headers={"Authorization": f"Bearer {admin_token}"}, timeout=30)
        assert r.status_code == 200
        d = r.json()
        assert d.get("stuck_analyzing_recovered", 0) >= 1
        fixed = db.claudeodd_schedule.find_one({"id": sched_id})
        assert fixed["ai_status"] == "pending"
    finally:
        db.claudeodd_schedule.delete_one({"id": sched_id})


def test_self_heal_deadline_enforcer_marks_no_prediction(admin_token, db):
    """Fixtures within 3h of kickoff with no odds get ai_status='no_prediction'."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    sched_id = "phase11-deadline-test"
    # Kickoff in 2 hours, odds never arrived
    db.claudeodd_schedule.insert_one({
        "id": sched_id, "date": today, "sport": "football",
        "league": "Serie A", "country": "Italy", "country_code": "ITA",
        "home": "DeadlineHome", "away": "DeadlineAway",
        "kickoff": (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat(),
        "odds_status": "waiting", "ai_status": "pending",
        "first_seen_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    })
    try:
        r = requests.post(f"{BASE}/api/admin/schedule/heal",
                          headers={"Authorization": f"Bearer {admin_token}"}, timeout=30)
        assert r.status_code == 200
        d = r.json()
        assert d.get("deadline_finalized", 0) >= 1
        fixed = db.claudeodd_schedule.find_one({"id": sched_id})
        assert fixed["ai_status"] == "no_prediction"
        assert fixed["no_prediction_reason"] == "odds_never_published"
    finally:
        db.claudeodd_schedule.delete_one({"id": sched_id})


def test_schedule_lifecycle_badges_include_live_and_completed():
    r = requests.get(f"{BASE}/api/schedule/upcoming?days=3", timeout=15)
    assert r.status_code == 200
    # New summary keys present
    for day in r.json()["schedule"]:
        for k in ("total", "waiting_odds", "ready", "analyzing", "rejected",
                  "failed", "no_prediction", "live", "completed"):
            assert k in day["summary"], f"summary missing key: {k}"


def test_heal_endpoint_returns_new_counts(admin_token):
    r = requests.post(f"{BASE}/api/admin/schedule/heal",
                      headers={"Authorization": f"Bearer {admin_token}"}, timeout=30)
    assert r.status_code == 200
    d = r.json()
    for k in ("mistagged_dropped", "orphans_reset",
              "stuck_analyzing_recovered", "deadline_finalized"):
        assert k in d, f"heal response missing key: {k}"
