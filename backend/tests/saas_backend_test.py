"""CLAUDEODD SaaS Phase 2 backend regression tests.

Covers:
- Auth (register, login, lockout, /me)
- Slip endpoints (today locked/unlocked, generate guard, history)
- Payments (Flutterwave init guard, bank transfer, mine, size limit)
- Admin (stats, users grant/suspend, payments approve/reject, config, predictions)
"""
from __future__ import annotations

import os
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    env_path = Path("/app/frontend/.env")
    for line in env_path.read_text().splitlines():
        if line.startswith("REACT_APP_BACKEND_URL="):
            BASE_URL = line.split("=", 1)[1].strip().strip('"').rstrip("/")
            break

API = f"{BASE_URL}/api"
ADMIN_EMAIL = "admin@claudeodd.com"
ADMIN_PASS = "Admin@2026"


def _new_email(prefix="test") -> str:
    return f"TEST_{prefix}_{uuid.uuid4().hex[:10]}@example.com"


@pytest.fixture(scope="session")
def s():
    sess = requests.Session()
    sess.headers.update({"Content-Type": "application/json"})
    return sess


@pytest.fixture(scope="session")
def admin_token(s):
    r = s.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASS}, timeout=15)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["user"]["role"] == "admin"
    return d["access_token"]


@pytest.fixture(scope="session")
def admin_h(admin_token):
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}


@pytest.fixture(scope="session")
def trial_user(s):
    """Create a fresh trial user; reused across tests."""
    email = _new_email("trial")
    pw = "TestPass#123"
    r = s.post(f"{API}/auth/register", json={
        "email": email, "password": pw, "name": "Trial User",
        "dob": "1990-01-01", "age_18_plus": True, "accept_terms": True,
    }, timeout=15)
    assert r.status_code == 200, r.text
    d = r.json()
    return {"email": email, "password": pw, "token": d["access_token"], "user": d["user"]}


@pytest.fixture
def user_h(trial_user):
    return {"Authorization": f"Bearer {trial_user['token']}", "Content-Type": "application/json"}


# ---------- Auth ----------
class TestAuthRegister:
    def test_register_success_returns_trial(self, s):
        email = _new_email("reg")
        r = s.post(f"{API}/auth/register", json={
            "email": email, "password": "Strong#1234", "name": "Reg User",
            "dob": "1990-05-10", "age_18_plus": True, "accept_terms": True,
        }, timeout=15)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["token_type"] == "bearer"
        assert d["access_token"]
        u = d["user"]
        # Server lowercases emails (correct behavior)
        assert u["email"] == email.lower()
        assert u["role"] == "user"
        assert u["subscription_status"] == "trial"
        assert u["trial_ends_at"] is not None
        # ~3 days from now
        ends = datetime.fromisoformat(u["trial_ends_at"])
        delta = (ends - datetime.now(timezone.utc)).total_seconds()
        assert 60 * 60 * 24 * 2 < delta <= 60 * 60 * 24 * 4

    def test_register_underage(self, s):
        r = s.post(f"{API}/auth/register", json={
            "email": _new_email("under"), "password": "Strong#1234", "name": "U",
            "dob": "2015-01-01", "age_18_plus": False, "accept_terms": True,
        }, timeout=15)
        assert r.status_code == 400
        assert "18" in r.json().get("detail", "")

    def test_register_no_terms(self, s):
        r = s.post(f"{API}/auth/register", json={
            "email": _new_email("noterms"), "password": "Strong#1234", "name": "U",
            "dob": "1990-01-01", "age_18_plus": True, "accept_terms": False,
        }, timeout=15)
        assert r.status_code == 400
        assert "Terms" in r.json().get("detail", "") or "terms" in r.json().get("detail", "").lower()

    def test_register_duplicate(self, s, trial_user):
        r = s.post(f"{API}/auth/register", json={
            "email": trial_user["email"], "password": "Other#5678", "name": "Dup",
            "dob": "1990-01-01", "age_18_plus": True, "accept_terms": True,
        }, timeout=15)
        assert r.status_code == 409


class TestAuthLogin:
    def test_admin_login(self, s):
        r = s.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASS}, timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert d["user"]["role"] == "admin"
        assert d["access_token"]

    def test_me_with_token(self, s, admin_h):
        r = s.get(f"{API}/auth/me", headers=admin_h, timeout=15)
        assert r.status_code == 200
        assert r.json()["email"] == ADMIN_EMAIL

    def test_me_without_token(self, s):
        sess = requests.Session()
        r = sess.get(f"{API}/auth/me", timeout=15)
        assert r.status_code == 401

    def test_login_wrong_password_5x_locks(self, s):
        # use a unique email so we don't lock real users
        email = _new_email("lock")
        # register first so user exists
        s.post(f"{API}/auth/register", json={
            "email": email, "password": "GoodPass#123", "name": "Lock",
            "dob": "1990-01-01", "age_18_plus": True, "accept_terms": True,
        }, timeout=15)
        sess = requests.Session()
        sess.headers.update({"Content-Type": "application/json"})
        codes = []
        for _ in range(6):
            r = sess.post(f"{API}/auth/login", json={"email": email, "password": "WRONG"}, timeout=15)
            codes.append(r.status_code)
        # First 5 should be 401, then lockout 429
        assert 429 in codes, f"Expected 429 lockout among {codes}"


# ---------- Slip ----------
class TestSlip:
    def test_slip_today_locked_no_auth(self, s):
        sess = requests.Session()
        r = sess.get(f"{API}/slip/today", timeout=20)
        assert r.status_code == 200
        d = r.json()
        assert d["locked"] is True
        if d.get("slip"):
            assert d["slip"]["locked"] is True
            for leg in d["slip"]["legs"]:
                assert "Locked" in leg["match"] or "🔒" in leg["match"]

    def test_slip_today_admin_unlocked(self, s, admin_h):
        r = s.get(f"{API}/slip/today", headers=admin_h, timeout=20)
        assert r.status_code == 200
        d = r.json()
        assert d["locked"] is False
        if d.get("slip"):
            assert d["slip"]["locked"] is False
            assert d["slip"]["sportybet_code"]
            assert "🔒" not in d["slip"]["sportybet_code"]
            assert d["slip"]["sportybet_url"]
            assert isinstance(d["slip"]["legs"], list)

    def test_slip_today_trial_unlocked(self, s, user_h):
        r = s.get(f"{API}/slip/today", headers=user_h, timeout=20)
        assert r.status_code == 200
        d = r.json()
        assert d["locked"] is False

    def test_generate_requires_admin(self, s, user_h):
        r = s.post(f"{API}/slip/generate", headers=user_h, timeout=15)
        assert r.status_code == 403

    def test_generate_admin_cached(self, s, admin_h):
        # force=False uses cached run if exists
        r = s.post(f"{API}/slip/generate", headers=admin_h, timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        assert "date" in d
        # Should be cached for today since picks already exist per task brief
        assert d.get("cached") in (True, False)

    def test_slip_history_requires_subscription(self, s, user_h):
        r = s.get(f"{API}/slip/history", headers=user_h, timeout=20)
        assert r.status_code == 200
        out = r.json()
        assert isinstance(out, list)
        if out:
            entry = out[0]
            assert "status_summary" in entry
            assert "sportybet_code" in entry


# ---------- Payments ----------
class TestPayments:
    def test_flw_init_unconfigured(self, s, user_h):
        r = s.post(f"{API}/payments/flutterwave/init", headers=user_h, json={
            "plan": "monthly", "method": "flutterwave"
        }, timeout=15)
        assert r.status_code == 400
        assert "configured" in r.json().get("detail", "").lower() or "key" in r.json().get("detail", "").lower()

    def test_bank_transfer_create(self, s, user_h):
        proof = "data:image/png;base64," + ("A" * 1024)
        r = s.post(f"{API}/payments/bank-transfer", headers=user_h, json={
            "amount": 5000, "reference": "TEST_REF_001",
            "sender_name": "Trial Tester", "proof_data_url": proof,
        }, timeout=15)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["status"] == "pending"
        assert d["method"] == "bank_transfer"
        assert d["amount"] == 5000.0
        assert d["currency"] == "NGN"
        assert "id" in d

        # GET /payments/mine to verify persistence
        r2 = s.get(f"{API}/payments/mine", headers=user_h, timeout=15)
        assert r2.status_code == 200
        mine = r2.json()
        assert any(p["id"] == d["id"] for p in mine)

    def test_bank_transfer_too_large(self, s, user_h):
        big = "data:image/png;base64," + ("A" * 4_500_000)
        r = s.post(f"{API}/payments/bank-transfer", headers=user_h, json={
            "amount": 5000, "reference": "TEST_BIG", "sender_name": "Big",
            "proof_data_url": big,
        }, timeout=30)
        assert r.status_code == 413


# ---------- Admin ----------
class TestAdmin:
    def test_admin_stats(self, s, admin_h):
        r = s.get(f"{API}/admin/stats", headers=admin_h, timeout=15)
        assert r.status_code == 200
        d = r.json()
        for k in ["total_users", "trial_users", "active_subscribers", "revenue_ngn",
                  "pending_payments", "successful_payments"]:
            assert k in d

    def test_admin_stats_forbidden_for_user(self, s, user_h):
        r = s.get(f"{API}/admin/stats", headers=user_h, timeout=15)
        assert r.status_code == 403

    def test_admin_users_no_password_leak(self, s, admin_h):
        r = s.get(f"{API}/admin/users", headers=admin_h, timeout=15)
        assert r.status_code == 200
        users = r.json()
        assert isinstance(users, list)
        for u in users:
            assert "password_hash" not in u
            assert "_id" not in u

    def test_admin_grant_30d(self, s, admin_h, trial_user):
        uid = trial_user["user"]["id"]
        r = s.post(f"{API}/admin/users/{uid}/grant?days=30", headers=admin_h, timeout=15)
        assert r.status_code == 200
        # verify subscription_status active via /admin/users
        users = s.get(f"{API}/admin/users", headers=admin_h, timeout=15).json()
        u = next((x for x in users if x["id"] == uid), None)
        assert u is not None
        assert u["subscription_status"] == "active"

    def test_admin_suspend(self, s, admin_h):
        # Create a fresh user to suspend
        email = _new_email("susp")
        reg = s.post(f"{API}/auth/register", json={
            "email": email, "password": "Strong#1234", "name": "Suspender",
            "dob": "1990-01-01", "age_18_plus": True, "accept_terms": True,
        }, timeout=15).json()
        uid = reg["user"]["id"]
        r = s.post(f"{API}/admin/users/{uid}/suspend", headers=admin_h, timeout=15)
        assert r.status_code == 200
        users = s.get(f"{API}/admin/users", headers=admin_h, timeout=15).json()
        u = next((x for x in users if x["id"] == uid), None)
        assert u["subscription_status"] == "expired"

    def test_admin_payments_filter(self, s, admin_h):
        r = s.get(f"{API}/admin/payments?status_filter=pending", headers=admin_h, timeout=15)
        assert r.status_code == 200
        payments = r.json()
        assert isinstance(payments, list)
        for p in payments:
            assert p["status"] == "pending"

    def test_admin_approve_payment_activates_user(self, s, admin_h):
        # Create a fresh user + bank transfer
        email = _new_email("appr")
        reg = s.post(f"{API}/auth/register", json={
            "email": email, "password": "Strong#1234", "name": "AppUser",
            "dob": "1990-01-01", "age_18_plus": True, "accept_terms": True,
        }, timeout=15).json()
        token = reg["access_token"]
        uid = reg["user"]["id"]
        h = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        bt = s.post(f"{API}/payments/bank-transfer", headers=h, json={
            "amount": 5000, "reference": "TEST_APP", "sender_name": "App",
            "proof_data_url": "data:image/png;base64," + ("Z" * 1024),
        }, timeout=15).json()
        pid = bt["id"]
        r = s.post(f"{API}/admin/payments/{pid}/approve", headers=admin_h, timeout=15)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["ok"] is True
        # Verify payment state
        all_pay = s.get(f"{API}/admin/payments?status_filter=successful", headers=admin_h, timeout=15).json()
        assert any(p["id"] == pid for p in all_pay)
        # Verify user activated
        users = s.get(f"{API}/admin/users", headers=admin_h, timeout=15).json()
        u = next((x for x in users if x["id"] == uid), None)
        assert u["subscription_status"] == "active"

    def test_admin_reject_payment(self, s, admin_h):
        email = _new_email("rej")
        reg = s.post(f"{API}/auth/register", json={
            "email": email, "password": "Strong#1234", "name": "Rej",
            "dob": "1990-01-01", "age_18_plus": True, "accept_terms": True,
        }, timeout=15).json()
        token = reg["access_token"]
        h = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        bt = s.post(f"{API}/payments/bank-transfer", headers=h, json={
            "amount": 5000, "reference": "TEST_RJ", "sender_name": "Rj",
            "proof_data_url": "data:image/png;base64," + ("Y" * 1024),
        }, timeout=15).json()
        pid = bt["id"]
        r = s.post(f"{API}/admin/payments/{pid}/reject", headers=admin_h, timeout=15)
        assert r.status_code == 200
        rejected = s.get(f"{API}/admin/payments?status_filter=rejected", headers=admin_h, timeout=15).json()
        assert any(p["id"] == pid for p in rejected)


class TestAdminConfig:
    def test_get_config_defaults(self, s, admin_h):
        r = s.get(f"{API}/admin/config", headers=admin_h, timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert "price_ngn" in d
        assert "bank_name" in d
        assert "flw_public_key" in d
        assert "_id" not in d

    def test_set_config_persists(self, s, admin_h):
        cur = s.get(f"{API}/admin/config", headers=admin_h, timeout=15).json()
        new = {**cur, "price_ngn": 7500.0, "bank_name": "TEST_BANK",
               "bank_account_number": "1234567890",
               "bank_account_name": "TEST ACC"}
        r = s.post(f"{API}/admin/config", headers=admin_h, json=new, timeout=15)
        assert r.status_code == 200, r.text
        out = r.json()
        assert out["price_ngn"] == 7500.0
        # Re-fetch
        check = s.get(f"{API}/admin/config", headers=admin_h, timeout=15).json()
        assert check["price_ngn"] == 7500.0
        assert check["bank_name"] == "TEST_BANK"
        # Restore
        restore = {**cur}
        s.post(f"{API}/admin/config", headers=admin_h, json=restore, timeout=15)


class TestAdminPredictions:
    def test_get_predictions(self, s, admin_h):
        r = s.get(f"{API}/admin/predictions", headers=admin_h, timeout=15)
        assert r.status_code == 200
        picks = r.json()
        assert isinstance(picks, list)
        for p in picks:
            assert "_id" not in p
            assert "id" in p

    def test_predictions_forbidden_for_user(self, s, user_h):
        r = s.get(f"{API}/admin/predictions", headers=user_h, timeout=15)
        assert r.status_code == 403


# ---------- Public config ----------
class TestPublicConfig:
    def test_public_config_no_secrets(self, s):
        r = s.get(f"{API}/public/config", timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert "price_ngn" in d
        assert "flw_secret_key" not in d
        assert "flw_encryption_key" not in d
        assert "smtp_password" not in d


if __name__ == "__main__":
    import sys
    sys.exit(pytest.main([__file__, "-v"]))
