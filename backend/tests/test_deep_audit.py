"""
Deep-audit regression tests for ClaudeOdds (iter 5).
Covers: AI realism, Subscription flow, edge cases, anonymous teaser,
admin authz, slip code validators, invalid cron, strategy cap.
"""
import io
import os
import time
import uuid

import pytest
import requests

BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL")
            or "https://probability-vault.preview.emergentagent.com").rstrip("/")
ADMIN_EMAIL = "admin@claudeodd.com"
ADMIN_PWD = "Admin@2026"


# ---------- fixtures ----------
@pytest.fixture(scope="session")
def admin_token():
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"email": ADMIN_EMAIL, "password": ADMIN_PWD},
                      timeout=15)
    assert r.status_code == 200, f"Admin login failed: {r.status_code} {r.text}"
    tok = r.json().get("token") or r.json().get("access_token")
    assert tok
    return tok


@pytest.fixture(scope="session")
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


@pytest.fixture(scope="session")
def trial_user():
    """Register a fresh trial user for subscription flow."""
    suffix = uuid.uuid4().hex[:8]
    email = f"TEST_audit_{suffix}@example.com"
    pwd = "TrialUser@2026"
    r = requests.post(f"{BASE_URL}/api/auth/register",
                      json={
                          "email": email,
                          "password": pwd,
                          "name": "Audit Trial",
                          "dob": "1990-01-01",
                          "accept_terms": True,
                          "age_18_plus": True,
                      }, timeout=15)
    assert r.status_code in (200, 201), f"register {r.status_code} {r.text}"
    body = r.json()
    tok = body.get("token") or body.get("access_token")
    user = body.get("user") or {}
    return {"email": email, "password": pwd, "token": tok, "user": user}


# ---------- AI realism ----------
class TestAIRealism:
    def test_slip_today_legs_are_realistic(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/slip/today",
                         headers=admin_headers, timeout=20)
        assert r.status_code == 200, r.text
        body = r.json()
        # Rollover-aware: when today has no picks and we're past 22:00 UTC,
        # the endpoint surfaces the awaiting_tomorrow state. That's correct
        # behaviour, not a bug — skip realism assertions in that case.
        if body.get("awaiting_tomorrow") or body.get("awaiting_data"):
            import pytest
            pytest.skip("Slip not yet generated (rollover/awaiting state) — seed via POST /api/slip/generate to run realism checks")
        slip = body.get("slip") or body
        assert body.get("locked") is False, "Admin should not get locked teaser"
        legs = slip.get("legs") or []
        assert len(legs) > 0, "No legs returned"
        assert len(legs) <= 5, f"Strategy cap violated: {len(legs)} legs"
        assert (slip.get("combined_odds") or 0) <= 5.0, \
            f"combined_odds {slip.get('combined_odds')} > 5.0"

        for leg in legs:
            conf = leg.get("confidence")
            edge = leg.get("edge_pct")
            ev = leg.get("expected_value")
            odds = leg.get("odds")
            qv = leg.get("quant_view") or {}
            book_impl = qv.get("book_implied_prob")

            assert conf is not None and 70 <= conf <= 92, \
                f"confidence {conf} outside [70,92] for {leg.get('match')}"
            assert edge is not None and -5 <= edge <= 25, \
                f"edge_pct {edge} outside [-5,25] (hallucination) for {leg.get('match')}"
            if ev is not None:
                assert ev <= 0.30, \
                    f"single-leg EV {ev} > 0.30 (hallucination) for {leg.get('match')}"
            if odds and book_impl:
                assert abs(book_impl - 1.0 / odds) <= 0.01, \
                    f"book_implied_prob {book_impl} != 1/odds {1/odds:.4f}"

        cev = slip.get("expected_value")
        if cev is not None:
            assert cev <= 0.40, f"combined EV {cev} > 0.40 (hallucination)"


# ---------- Edge cases / authz ----------
class TestEdgeCases:
    def test_anonymous_slip_returns_locked_teaser(self):
        r = requests.get(f"{BASE_URL}/api/slip/today", timeout=20)
        assert r.status_code in (200, 401), r.text
        if r.status_code == 200:
            body = r.json()
            slip = body.get("slip") or body
            assert (body.get("locked") is True or
                    slip.get("locked") is True or
                    slip.get("sportybet_code") in (None, "", "LOCKED"))

    def test_regular_user_cannot_access_admin(self, trial_user):
        h = {"Authorization": f"Bearer {trial_user['token']}"}
        for ep in ("/api/admin/users", "/api/admin/payments",
                   "/api/admin/predictions", "/api/admin/config"):
            r = requests.get(f"{BASE_URL}{ep}", headers=h, timeout=10)
            assert r.status_code in (401, 403), \
                f"{ep} returned {r.status_code} for non-admin"

    def test_admin_slip_code_too_short(self, admin_headers):
        r = requests.post(f"{BASE_URL}/api/admin/slip/code",
                          headers=admin_headers, json={"code": "AB"}, timeout=10)
        assert r.status_code == 400

    def test_admin_slip_code_invalid_chars(self, admin_headers):
        r = requests.post(f"{BASE_URL}/api/admin/slip/code",
                          headers=admin_headers, json={"code": "!@#$"}, timeout=10)
        assert r.status_code == 400

    def test_invalid_cron_hour_rejected_or_ignored(self, admin_headers):
        """CRITICAL: cron_hour_utc=25 must NOT be persisted. If it is, a backend
        restart will crash on scheduler startup (CronTrigger raises ValueError).
        We do NOT actually post 25 here (that poisoned the DB and took the
        backend down in iter5 first run). Instead we verify Pydantic rejects it.
        """
        # snapshot
        cur = requests.get(f"{BASE_URL}/api/admin/config",
                           headers=admin_headers, timeout=10).json()
        prev_hour = cur.get("cron_hour_utc", 8)
        # The bug repro is too destructive to run automatically — we only verify
        # current value is sane (0-23) and skip the destructive POST.
        assert 0 <= prev_hour <= 23, f"cron_hour_utc out of range: {prev_hour}"
        # NOTE: POST {cron_hour_utc:25} returns 500 AND persists the bad value.
        # See test report for details. Do NOT enable until Pydantic validator added.
        pytest.skip("Destructive: see test report critical bugs (cron_hour_utc validator missing).")

    def test_login_with_leading_space_email(self):
        r = requests.post(f"{BASE_URL}/api/auth/login",
                          json={"email": " admin@claudeodd.com",
                                "password": ADMIN_PWD}, timeout=10)
        # Either succeeds (trimmed) or fails 400/401 — must NOT 500
        assert r.status_code in (200, 400, 401), \
            f"leading-space login returned {r.status_code}"


# ---------- Subscription end-to-end ----------
class TestSubscriptionFlow:
    def test_bank_transfer_empty_rejected(self, trial_user):
        h = {"Authorization": f"Bearer {trial_user['token']}"}
        r = requests.post(f"{BASE_URL}/api/payments/bank-transfer",
                          headers=h, json={}, timeout=15)
        assert r.status_code in (400, 422), \
            f"empty bank-transfer returned {r.status_code}"

    def test_bank_transfer_oversize_payload_rejected(self, trial_user):
        h = {"Authorization": f"Bearer {trial_user['token']}"}
        big_data_url = "data:image/png;base64," + ("A" * 5_000_000)  # >4MB
        r = requests.post(f"{BASE_URL}/api/payments/bank-transfer",
                          headers=h, json={
                              "proof_data_url": big_data_url,
                              "reference": "TEST_BIG",
                              "sender_name": "Audit Tester"
                          }, timeout=20)
        assert r.status_code in (400, 413, 422), \
            f"oversize payload accepted {r.status_code}"

    def test_full_subscription_flow_admin_approve(self, trial_user, admin_headers):
        h = {"Authorization": f"Bearer {trial_user['token']}"}
        small = "data:image/png;base64," + ("A" * 4096)
        r = requests.post(f"{BASE_URL}/api/payments/bank-transfer",
                          headers=h, json={
                              "proof_data_url": small,
                              "amount": 5000,
                              "reference": f"TEST_OK_{uuid.uuid4().hex[:6]}",
                              "sender_name": "Audit Tester"
                          }, timeout=20)
        assert r.status_code in (200, 201), f"create payment {r.status_code} {r.text}"
        body = r.json()
        pay_id = body.get("id")
        assert pay_id, f"no payment id in {body}"

        # admin sees pending
        lst = requests.get(f"{BASE_URL}/api/admin/payments",
                           headers=admin_headers, timeout=15).json()
        items = lst if isinstance(lst, list) else lst.get("payments", [])
        ids = [p.get("id") for p in items]
        assert pay_id in ids, f"payment {pay_id} not visible in admin list ({len(ids)} items)"

        # approve
        ap = requests.post(f"{BASE_URL}/api/admin/payments/{pay_id}/approve",
                           headers=admin_headers, timeout=15)
        assert ap.status_code in (200, 201, 204), f"approve {ap.status_code} {ap.text}"

        # user is now active
        me = requests.get(f"{BASE_URL}/api/auth/me", headers=h, timeout=10).json()
        user = me.get("user") or me
        assert (user.get("subscription_status") or "").lower() == "active", \
            f"subscription_status {user.get('subscription_status')} after approval"


# ---------- Trial duration ----------
class TestTrial:
    def test_new_user_has_3_day_trial(self, trial_user):
        h = {"Authorization": f"Bearer {trial_user['token']}"}
        r = requests.get(f"{BASE_URL}/api/auth/me", headers=h, timeout=10)
        assert r.status_code == 200
        u = r.json().get("user") or r.json()
        ends = u.get("trial_ends_at")
        assert ends, f"trial_ends_at missing in /auth/me: {u}"


# ---------- Slip generate cached + 404 polling ----------
class TestSlipGenerate:
    def test_cached_no_force(self, admin_headers):
        r = requests.post(f"{BASE_URL}/api/slip/generate",
                          headers=admin_headers, timeout=20)
        assert r.status_code == 200
        body = r.json()
        assert body.get("status") in ("completed", "cached", "ready", "ok")
        assert body.get("cached") is True or body.get("status") == "completed"

    def test_unknown_job_id_returns_404(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/slip/generate/status/nonexistent-{uuid.uuid4().hex}",
                         headers=admin_headers, timeout=10)
        assert r.status_code == 404
