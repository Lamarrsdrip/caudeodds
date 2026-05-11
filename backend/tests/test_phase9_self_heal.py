"""Phase 9 — Self-healing fixture pipeline.

Verifies the production bug-fix:
  • Legacy mistagged picks (kickoff date != pick.date) are deleted on self-heal
  • Orphan schedule entries (ai_status='ready' but pick_id missing in claudeodd_picks)
    are reset to ai_status='pending' so the next cron rebuilds the pick
  • Admin endpoint POST /api/admin/schedule/heal exposes this manually
  • Force Re-Generate now runs self-heal before the pipeline
"""
import os
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


def test_heal_endpoint_returns_counts(admin_token):
    r = requests.post(f"{BASE}/api/admin/schedule/heal",
                      headers={"Authorization": f"Bearer {admin_token}"}, timeout=30)
    assert r.status_code == 200, r.text
    d = r.json()
    assert "mistagged_dropped" in d and "orphans_reset" in d
    assert isinstance(d["mistagged_dropped"], int)
    assert isinstance(d["orphans_reset"], int)


def test_heal_endpoint_requires_admin():
    r = requests.post(f"{BASE}/api/admin/schedule/heal", timeout=15)
    assert r.status_code in (401, 403)


def test_self_heal_drops_mistagged_picks(admin_token):
    """Seed a pick whose kickoff date doesn't match its date label, then run
    heal and verify it's gone."""
    import pymongo
    from os import environ
    mongo = pymongo.MongoClient(environ.get("MONGO_URL", "mongodb://localhost:27017"))
    db = mongo[environ.get("DB_NAME", "test_database")]

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    tomorrow_ko = (datetime.now(timezone.utc) + timedelta(days=1, hours=18)).isoformat()
    pick_id = "phase9-mistag-test"
    db.claudeodd_picks.insert_one({
        "id": pick_id, "date": today, "kickoff": tomorrow_ko,
        "match": "Phase9 Mistag Test", "sport": "football",
        "league": "La Liga", "country": "Spain", "country_code": "ESP",
        "market": "DC", "selection_label": "Away or Draw",
        "odds": 3.23, "fair_prob": 0.55, "model_prob": 0.55,
        "confidence": 79, "edge_pct": 19.4, "expected_value": 0.194,
        "data_richness": 0.6, "reasoning": "test", "status": "pending",
    })
    try:
        r = requests.post(f"{BASE}/api/admin/schedule/heal",
                          headers={"Authorization": f"Bearer {admin_token}"}, timeout=30)
        assert r.status_code == 200
        # mistagged_dropped must be >=1 (this test row + any pre-existing)
        assert r.json()["mistagged_dropped"] >= 1
        # And the pick must be gone
        assert db.claudeodd_picks.find_one({"id": pick_id}) is None
    finally:
        db.claudeodd_picks.delete_one({"id": pick_id})


def test_self_heal_resets_orphan_schedule(admin_token):
    """Seed a schedule entry whose pick_id points to nothing. Verify heal
    resets ai_status back to 'pending' so the cron rebuilds it."""
    import pymongo
    from os import environ
    mongo = pymongo.MongoClient(environ.get("MONGO_URL", "mongodb://localhost:27017"))
    db = mongo[environ.get("DB_NAME", "test_database")]

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    sched_id = "phase9-orphan-test"
    db.claudeodd_schedule.insert_one({
        "id": sched_id, "date": today, "sport": "football",
        "league": "Premier League", "country": "England", "country_code": "GB",
        "home": "PhaseNineHome", "away": "PhaseNineAway",
        "kickoff": (datetime.now(timezone.utc) + timedelta(hours=4)).isoformat(),
        "odds_status": "available", "ai_status": "ready",
        "pick_id": "does-not-exist-pick-id-xyz",
        "first_seen_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    })
    try:
        r = requests.post(f"{BASE}/api/admin/schedule/heal",
                          headers={"Authorization": f"Bearer {admin_token}"}, timeout=30)
        assert r.status_code == 200
        assert r.json()["orphans_reset"] >= 1
        fixed = db.claudeodd_schedule.find_one({"id": sched_id})
        assert fixed["ai_status"] == "pending"
        assert fixed["pick_id"] is None
    finally:
        db.claudeodd_schedule.delete_one({"id": sched_id})
