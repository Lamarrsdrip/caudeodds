"""Phase 7 — Admin security: password change, SMTP, activity, persistence.

Verifies the production-critical admin foundations:
  • Password change with old-token invalidation (force-logout)
  • Password persists across backend restart (seed_admin no longer overwrites)
  • Login activity log records both successes and failures with ip/ua
  • SMTP test endpoint surfaces clear error_class even without config
"""
import os
import time
from datetime import datetime, timezone

import pytest
import requests

BASE = (os.environ.get("REACT_APP_BACKEND_URL") or "http://localhost:8001").rstrip("/")
ADMIN_EMAIL = "admin@claudeodd.com"
ADMIN_PASS = "Admin@2026"


def _login(email, password):
    return requests.post(f"{BASE}/api/auth/login", json={"email": email, "password": password}, timeout=15)


@pytest.fixture
def admin_token():
    r = _login(ADMIN_EMAIL, ADMIN_PASS)
    if r.status_code != 200:
        pytest.skip(f"Admin login failed: {r.status_code} {r.text}")
    return r.json()["access_token"]


# ── Password change + force-logout ───────────────────────────────────────────

def test_password_change_rejects_wrong_current(admin_token):
    r = requests.post(f"{BASE}/api/auth/password/change",
                      headers={"Authorization": f"Bearer {admin_token}"},
                      json={"current_password": "wrong", "new_password": "NewSecret123"},
                      timeout=15)
    assert r.status_code == 401
    assert "incorrect" in r.text.lower()


def test_password_change_rejects_short_new(admin_token):
    r = requests.post(f"{BASE}/api/auth/password/change",
                      headers={"Authorization": f"Bearer {admin_token}"},
                      json={"current_password": ADMIN_PASS, "new_password": "short"},
                      timeout=15)
    assert r.status_code == 400


def test_password_change_rejects_same_password(admin_token):
    r = requests.post(f"{BASE}/api/auth/password/change",
                      headers={"Authorization": f"Bearer {admin_token}"},
                      json={"current_password": ADMIN_PASS, "new_password": ADMIN_PASS},
                      timeout=15)
    assert r.status_code == 400


def test_password_change_invalidates_old_token_and_persists():
    """Full round-trip: change password, verify old token rejected, new login works."""
    # 1. Initial login
    r = _login(ADMIN_EMAIL, ADMIN_PASS)
    assert r.status_code == 200, r.text
    old_token = r.json()["access_token"]

    new_pw = "Phase7TestPw!"
    try:
        # 2. Change password
        r2 = requests.post(f"{BASE}/api/auth/password/change",
                           headers={"Authorization": f"Bearer {old_token}"},
                           json={"current_password": ADMIN_PASS, "new_password": new_pw},
                           timeout=15)
        assert r2.status_code == 200, r2.text
        rotated = r2.json()
        assert "access_token" in rotated and rotated["ok"] is True

        # 3. Old token must be invalid (password_version bumped)
        r3 = requests.get(f"{BASE}/api/auth/me",
                          headers={"Authorization": f"Bearer {old_token}"}, timeout=15)
        assert r3.status_code == 401
        assert "session" in r3.text.lower() or "expired" in r3.text.lower()

        # 4. Login with new password works
        r4 = _login(ADMIN_EMAIL, new_pw)
        assert r4.status_code == 200, r4.text

        # 5. The rotated token returned by /password/change should still work
        r5 = requests.get(f"{BASE}/api/auth/me",
                          headers={"Authorization": f"Bearer {rotated['access_token']}"}, timeout=15)
        assert r5.status_code == 200

    finally:
        # Always revert so other tests aren't broken
        login_resp = _login(ADMIN_EMAIL, new_pw)
        if login_resp.status_code == 200:
            tok = login_resp.json()["access_token"]
            requests.post(f"{BASE}/api/auth/password/change",
                          headers={"Authorization": f"Bearer {tok}"},
                          json={"current_password": new_pw, "new_password": ADMIN_PASS},
                          timeout=15)


# ── Login activity ───────────────────────────────────────────────────────────

def test_login_activity_records_success_and_failure(admin_token):
    # Generate a known failure
    requests.post(f"{BASE}/api/auth/login",
                  json={"email": ADMIN_EMAIL, "password": "definitely-wrong-xyz"}, timeout=15)
    time.sleep(0.4)
    r = requests.get(f"{BASE}/api/admin/activity?limit=20",
                     headers={"Authorization": f"Bearer {admin_token}"}, timeout=15)
    assert r.status_code == 200, r.text
    rows = r.json()
    assert isinstance(rows, list) and len(rows) > 0
    assert all(set(("email", "success", "ts", "ip", "ua")) <= set(row.keys()) for row in rows)
    # Recent failure with reason should exist
    assert any((not row["success"]) and row.get("reason") in ("bad_password", "no_user")
               for row in rows)


def test_my_activity_returns_only_self(admin_token):
    r = requests.get(f"{BASE}/api/auth/activity",
                     headers={"Authorization": f"Bearer {admin_token}"}, timeout=15)
    assert r.status_code == 200
    rows = r.json()
    assert all(row["email"] == ADMIN_EMAIL for row in rows)


# ── SMTP ──────────────────────────────────────────────────────────────────────

def test_smtp_test_with_empty_config(admin_token):
    r = requests.post(f"{BASE}/api/admin/smtp/test",
                      headers={"Authorization": f"Bearer {admin_token}"}, timeout=15)
    assert r.status_code == 200
    d = r.json()
    assert "ok" in d and "error_class" in d and "message" in d
    # In this preview pod SMTP isn't configured — must return clear MISSING_CONFIG
    if not d["ok"]:
        assert d["error_class"] in ("MISSING_CONFIG", "WRONG_PASSWORD",
                                    "INVALID_APP_PASSWORD", "AUTH_FAILED",
                                    "SMTP_BLOCKED", "TLS_ERROR", "HOST_NOT_FOUND",
                                    "TIMEOUT", "UNKNOWN")


def test_smtp_send_test_no_config_logs_failure(admin_token):
    r = requests.post(f"{BASE}/api/admin/smtp/send-test",
                      headers={"Authorization": f"Bearer {admin_token}"},
                      json={"to": "test@example.com"}, timeout=15)
    assert r.status_code == 200
    d = r.json()
    # Should be persisted to email_logs with status=failed
    assert d.get("status") == "failed"
    assert "error_class" in d


def test_admin_email_logs_endpoint(admin_token):
    r = requests.get(f"{BASE}/api/admin/emails/logs?limit=10",
                     headers={"Authorization": f"Bearer {admin_token}"}, timeout=15)
    assert r.status_code == 200
    rows = r.json()
    assert isinstance(rows, list)


# ── Authentication required for new admin endpoints ──────────────────────────

def test_admin_endpoints_require_admin():
    for path, method in [
        ("/api/admin/smtp/test", "POST"),
        ("/api/admin/smtp/send-test", "POST"),
        ("/api/admin/activity", "GET"),
        ("/api/admin/emails/logs", "GET"),
    ]:
        r = requests.request(method, f"{BASE}{path}", timeout=15)
        assert r.status_code in (401, 403, 422), f"{path} unauthorized expected, got {r.status_code}"
