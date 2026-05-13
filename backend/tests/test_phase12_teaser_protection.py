"""Phase 12 — Teaser protection + WIN/LOSS labels + admin button split.

User requirement: NEVER leak exact pick data to public/unauthenticated users.
Public payload must hide team names, exact odds, exact confidence so the pick
cannot be reverse-engineered.
"""
import os
import requests

BASE = (os.environ.get("REACT_APP_BACKEND_URL") or "http://localhost:8001").rstrip("/")


def test_unauthenticated_slip_today_locks_team_names():
    """Public/unauth GET /api/slip/today MUST NOT expose real team names."""
    r = requests.get(f"{BASE}/api/slip/today", timeout=15)
    assert r.status_code == 200
    body = r.json()
    if not body.get("slip"):
        # No slip today (e.g. early in the day) — endpoint is still safe by definition
        return
    slip = body["slip"]
    assert body.get("locked") is True, "Unauthenticated request must always be locked"
    for leg in slip.get("legs", []):
        assert leg["match"] in ("🔒 Locked", "Locked"), \
            f"Locked teaser must hide team names — got match='{leg['match']}'"
        # Exact odds must be NULL (only odds_range may be exposed)
        assert leg["odds"] is None, \
            f"Locked teaser must not expose exact decimal odds — got odds={leg['odds']}"
        # Confidence must be zeroed
        assert leg.get("confidence", 0) == 0, \
            f"Locked teaser must zero confidence — got {leg['confidence']}"
        # Selection label must be the unlock prompt
        assert "unlock" in leg["selection_label"].lower() or leg["market"] == "LOCKED"


def test_unauthenticated_slip_today_hides_combined_odds():
    """Combined odds must be bucketed into a range (never exact) for public."""
    r = requests.get(f"{BASE}/api/slip/today", timeout=15)
    assert r.status_code == 200
    body = r.json()
    if not body.get("slip"):
        return
    slip = body["slip"]
    if not body.get("locked"):
        return
    assert slip.get("combined_odds") is None
    assert slip.get("combined_odds_range") in ("2.0–3.0", "3.0–4.0", "4.0–5.0")
    # SportyBet code must NEVER be exposed publicly
    assert slip.get("sportybet_code") in ("", None)


def test_schedule_upcoming_includes_result_status_field():
    """Schedule fixtures must surface result_status (won/lost/void) for the UI
    to show WIN ✅ / LOSS ❌ / VOID ⚪ labels on finished matches."""
    r = requests.get(f"{BASE}/api/schedule/upcoming?days=3", timeout=15)
    assert r.status_code == 200
    for day in r.json()["schedule"]:
        for fx in day["fixtures"]:
            assert "result_status" in fx, "fixture row must carry result_status"
            assert fx["result_status"] in (None, "pending", "won", "lost", "void")
            assert "pick_id" in fx
