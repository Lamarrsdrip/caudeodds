"""Phase 12 — Teaser protection + WIN/LOSS labels + admin button split.

User requirement: Hide the BET (match, market, selection) so prospects can't
reverse-engineer the AI's pick. Keep the ODDS visible so they see the price
they'd be locking in. SportyBet booking code MUST stay hidden too.
"""
import os
import requests

BASE = (os.environ.get("REACT_APP_BACKEND_URL") or "http://localhost:8001").rstrip("/")


def test_unauthenticated_slip_today_locks_team_names():
    """Public/unauth GET /api/slip/today MUST NOT expose match, market, or selection."""
    r = requests.get(f"{BASE}/api/slip/today", timeout=15)
    assert r.status_code == 200
    body = r.json()
    if not body.get("slip"):
        # No slip today (e.g. early in the day) — endpoint is still safe by definition
        return
    slip = body["slip"]
    assert body.get("locked") is True, "Unauthenticated request must always be locked"
    for leg in slip.get("legs", []):
        # Match (teams) must be hidden
        assert leg["match"] in ("🔒 Locked", "Locked"), \
            f"Locked teaser must hide team names — got match='{leg['match']}'"
        # League must be hidden too (it narrows the game down)
        assert leg["league"] in ("🔒 Locked", "Locked", ""), \
            f"Locked teaser must hide league — got league='{leg['league']}'"
        # Market (bet type) must be hidden
        assert "Locked" in leg["market"] or leg["market"] == "LOCKED", \
            f"Locked teaser must hide market — got '{leg['market']}'"
        # Selection (side/outcome) must be hidden — must NOT contain
        # leakable phrases like "Double Chance", "Draw or Away", "Over"
        sel = (leg.get("selection_label") or "")
        assert "Locked" in sel or "unlock" in sel.lower(), \
            f"Locked teaser must hide selection — got '{sel}'"
        for leak in ("double chance", "draw or", "over 2", "under 2", "home win", "away win", "btts"):
            assert leak not in sel.lower(), \
                f"Locked teaser leaked selection content: '{sel}' contains '{leak}'"
        # Confidence must be zeroed
        assert leg.get("confidence", 0) == 0, \
            f"Locked teaser must zero confidence — got {leg['confidence']}"
        # Odds — by product spec — STAY visible so prospects see the price.
        # They must be a positive number (not the exact pick reverse-engineerable
        # without the match/market/side, which are all hidden above).
        assert leg.get("odds") is None or leg["odds"] > 0


def test_unauthenticated_slip_today_hides_sportybet_code():
    """SportyBet booking code MUST NEVER be exposed publicly."""
    r = requests.get(f"{BASE}/api/slip/today", timeout=15)
    assert r.status_code == 200
    body = r.json()
    if not body.get("slip"):
        return
    if not body.get("locked"):
        return
    slip = body["slip"]
    # Combined odds — exposed (price is fine without the picks)
    co = slip.get("combined_odds")
    assert co is None or co > 0
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
