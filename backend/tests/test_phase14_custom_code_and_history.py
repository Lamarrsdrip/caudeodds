"""Phase 14 — Custom referral codes + expired-user history preview.

Product rules added on 2026-05-13:
  - Users can pick a custom referral code/word via PUT /api/referral/code
    (4-20 alphanumeric chars, must contain a letter, reserved words blocked).
  - Expired-subscription users can call /api/slip/history and see redacted
    slip results (per-leg odds + W/L visible, picks hidden) so they're
    motivated to resubscribe. Sportybet code stays hidden.
"""
import os
import uuid
import requests

BASE = (os.environ.get("REACT_APP_BACKEND_URL") or "http://localhost:8001").rstrip("/")


def _email(prefix="ph14"):
    return f"{prefix}_{uuid.uuid4().hex[:10]}@test.com".lower()


def _register():
    email = _email()
    body = {
        "email": email,
        "password": "testpass123",
        "name": "Ph14",
        "age_18_plus": True,
        "accept_terms": True,
        "device_fingerprint": f"fp-{uuid.uuid4().hex}",
    }
    r = requests.post(f"{BASE}/api/auth/register", json=body, timeout=15)
    assert r.status_code == 200, r.text
    return email, r.json()["access_token"]


def _put_code(token, code):
    return requests.put(
        f"{BASE}/api/referral/code",
        headers={"Authorization": f"Bearer {token}"},
        json={"code": code},
        timeout=10,
    )


# ---- Custom referral code tests ----

def test_set_valid_custom_code():
    _, token = _register()
    suffix = uuid.uuid4().hex[:6].upper()
    code = f"BRAND{suffix}"
    r = _put_code(token, code)
    assert r.status_code == 200, r.text
    assert r.json()["code"] == code

    me = requests.get(f"{BASE}/api/referral/me",
                      headers={"Authorization": f"Bearer {token}"}, timeout=10).json()
    assert me["code"] == code
    assert f"ref={code}" in me["share_link"]


def test_custom_code_normalizes_input():
    _, token = _register()
    suffix = uuid.uuid4().hex[:5]
    # lowercase + spaces + symbols → cleaned to A-Z0-9
    r = _put_code(token, f"  my-code {suffix}  ")
    assert r.status_code == 200, r.text
    code = r.json()["code"]
    assert code == f"MYCODE{suffix.upper()}"


def test_custom_code_too_short_rejected():
    _, token = _register()
    r = _put_code(token, "ab")
    assert r.status_code == 400
    assert "4" in r.json()["detail"] or "short" in r.json()["detail"].lower()


def test_custom_code_too_long_rejected():
    _, token = _register()
    r = _put_code(token, "X" * 21)
    assert r.status_code == 400


def test_custom_code_digits_only_rejected():
    _, token = _register()
    r = _put_code(token, "12345678")
    assert r.status_code == 400
    assert "letter" in r.json()["detail"].lower()


def test_custom_code_reserved_word_rejected():
    _, token = _register()
    r = _put_code(token, "ADMIN")
    assert r.status_code == 400
    assert "reserved" in r.json()["detail"].lower()


def test_custom_code_collision_rejected():
    _, t1 = _register()
    _, t2 = _register()
    code = f"UNIQ{uuid.uuid4().hex[:6].upper()}"
    r1 = _put_code(t1, code)
    assert r1.status_code == 200
    r2 = _put_code(t2, code)
    assert r2.status_code == 409
    assert "taken" in r2.json()["detail"].lower()


def test_user_can_resave_same_code():
    _, token = _register()
    code = f"SELF{uuid.uuid4().hex[:6].upper()}"
    r1 = _put_code(token, code)
    assert r1.status_code == 200
    r2 = _put_code(token, code)  # same user, same code
    assert r2.status_code == 200


# ---- Expired-user history preview tests ----

def _expire_user(email):
    """Set this user's trial/sub to a date in the past so they're 'expired'."""
    import asyncio
    from datetime import datetime, timezone, timedelta
    from motor.motor_asyncio import AsyncIOMotorClient
    from dotenv import load_dotenv

    load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

    async def _do():
        c = AsyncIOMotorClient(os.environ["MONGO_URL"])
        db = c[os.environ["DB_NAME"]]
        past = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()
        await db.users.update_one(
            {"email": email},
            {"$set": {
                "trial_ends_at": past,
                "subscription_ends_at": None,
                "subscription_status": "expired",
            }},
        )
    asyncio.run(_do())


def test_expired_user_can_fetch_slip_history():
    """Previously this returned 402 — now it returns 200 with redacted data."""
    email, token = _register()
    _expire_user(email)
    # Reissue the token by logging in (subscription_status was changed)
    login = requests.post(f"{BASE}/api/auth/login",
                          json={"email": email, "password": "testpass123"}, timeout=10)
    assert login.status_code == 200
    token = login.json()["access_token"]

    r = requests.get(f"{BASE}/api/slip/history",
                     headers={"Authorization": f"Bearer {token}"}, timeout=15)
    assert r.status_code == 200, r.text
    body = r.json()
    assert isinstance(body, list)
    # If there are slips in the DB, each must be locked + redacted
    for slip in body:
        assert slip.get("locked") is True, "Expired-user slip must be locked"
        # SportyBet code MUST be hidden
        assert slip.get("sportybet_code") in ("", None)
        # Combined odds is exposed (price is fine without the picks)
        assert slip.get("combined_odds", 0) > 0
        for leg in slip.get("legs", []):
            # Bet redacted
            assert "Locked" in leg["match"]
            assert "Locked" in leg["selection_label"]
            assert "Locked" in leg["market"]
            # Odds exposed
            assert leg.get("odds") is None or leg["odds"] > 0
            # Per-leg result is exposed (won/lost/void/pending)
            assert leg.get("status") in ("won", "lost", "void", "pending")
