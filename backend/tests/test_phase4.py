"""Phase-4 backend tests: admin config (odds_api/cron/push), VAPID public config,
push subscribe/test, slip broadcast, strategy cap enforcement.
"""
import os
import pytest
import requests
from pymongo import MongoClient

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/") or "http://localhost:8001"
ADMIN_EMAIL = "admin@claudeodd.com"
ADMIN_PASS = "Admin@2026"

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "test_database")


@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"email": ADMIN_EMAIL, "password": ADMIN_PASS}, timeout=15)
    if r.status_code != 200:
        pytest.skip(f"Admin login failed: {r.status_code} {r.text}")
    return r.json()["access_token"]


@pytest.fixture(scope="module")
def auth_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def db():
    return MongoClient(MONGO_URL)[DB_NAME]


# ------------------ Public config (VAPID) ------------------

class TestPublicConfig:
    def test_public_config_returns_vapid_public_key(self):
        r = requests.get(f"{BASE_URL}/api/public/config", timeout=15)
        assert r.status_code == 200
        data = r.json()
        assert "vapid_public_key" in data
        assert "push_enabled" in data
        assert isinstance(data["push_enabled"], bool)
        vk = data["vapid_public_key"]
        # P-256 uncompressed pubkey b64url ~= 87 chars and starts with 'B'
        assert isinstance(vk, str) and len(vk) >= 80
        assert vk.startswith("B"), f"VAPID public key should start with 'B', got '{vk[:5]}'"


# ------------------ Admin Config (odds_api/cron/push fields) ------------------

class TestAdminConfigFields:
    def test_admin_get_config_has_new_fields(self, auth_headers):
        r = requests.get(f"{BASE_URL}/api/admin/config", headers=auth_headers, timeout=15)
        assert r.status_code == 200
        cfg = r.json()
        for f in ["odds_api_provider", "odds_api_base_url", "odds_api_key",
                  "cron_enabled", "cron_hour_utc", "cron_minute_utc",
                  "push_enabled", "push_subject_email"]:
            assert f in cfg, f"missing field {f}"

    def test_admin_set_odds_api_key_then_masked_on_get(self, auth_headers):
        # First get baseline
        r0 = requests.get(f"{BASE_URL}/api/admin/config", headers=auth_headers, timeout=15)
        cfg = r0.json()
        original_provider = cfg.get("odds_api_provider", "the_odds_api")
        original_hour = cfg.get("cron_hour_utc", 8)

        cfg["odds_api_key"] = "NEWTESTKEY123"
        cfg["odds_api_base_url"] = "https://api.the-odds-api.com/v4"
        cfg["odds_api_provider"] = "the_odds_api"
        # Set cron hour to test reschedule
        cfg["cron_hour_utc"] = 9

        r1 = requests.post(f"{BASE_URL}/api/admin/config", headers=auth_headers,
                           json=cfg, timeout=20)
        assert r1.status_code == 200, r1.text

        r2 = requests.get(f"{BASE_URL}/api/admin/config", headers=auth_headers, timeout=15)
        assert r2.status_code == 200
        new_cfg = r2.json()
        # Masked
        masked = new_cfg["odds_api_key"]
        assert masked.startswith("****"), f"odds_api_key not masked: {masked}"
        assert masked.endswith("Y123"), f"odds_api_key mask should keep last 4 ('Y123'), got '{masked}'"
        assert new_cfg["cron_hour_utc"] == 9

        # Restore: re-post with masked value (shouldn't overwrite secret) and original hour
        new_cfg["cron_hour_utc"] = original_hour
        new_cfg["odds_api_provider"] = original_provider
        r3 = requests.post(f"{BASE_URL}/api/admin/config", headers=auth_headers,
                           json=new_cfg, timeout=20)
        assert r3.status_code == 200


# ------------------ Push subscribe ------------------

class TestPushSubscribe:
    def test_push_subscribe_empty_returns_400(self, auth_headers):
        r = requests.post(f"{BASE_URL}/api/push/subscribe",
                          headers=auth_headers, json={}, timeout=15)
        assert r.status_code == 400
        body = r.json()
        # detail or message
        assert "Invalid push subscription" in str(body)

    def test_push_subscribe_valid_creates_doc(self, auth_headers, db):
        endpoint = "https://fcm.googleapis.com/fcm/send/test_phase4_pytest"
        payload = {
            "subscription": {
                "endpoint": endpoint,
                "keys": {
                    "p256dh": "BNcRdReoSwfQzsXPInXxdXOh1ku4j-c7XQz7w_HgU3X0YK0rQDWmPpqMfgLcUHuvRJW3LL5SpV0M-uw5fIQ_l7c",
                    "auth": "tBHItJI5svbpez7KI4CCXg",
                },
            }
        }
        r = requests.post(f"{BASE_URL}/api/push/subscribe",
                          headers=auth_headers, json=payload, timeout=15)
        assert r.status_code == 200, r.text
        assert r.json().get("ok") is True
        # Verify in DB
        doc = db.push_subscriptions.find_one({"endpoint": endpoint})
        assert doc is not None
        assert doc.get("p256dh", "").startswith("BNcRd")
        # cleanup
        db.push_subscriptions.delete_one({"endpoint": endpoint})


# ------------------ Admin push test ------------------

class TestAdminPushTest:
    def test_admin_push_test_returns_counts(self, auth_headers):
        r = requests.post(f"{BASE_URL}/api/admin/push/test",
                          headers=auth_headers, json={}, timeout=30)
        assert r.status_code == 200
        body = r.json()
        for k in ("sent", "invalid", "failed", "total"):
            assert k in body
            assert isinstance(body[k], int)

    def test_admin_push_test_with_title_body(self, auth_headers):
        r = requests.post(f"{BASE_URL}/api/admin/push/test",
                          headers=auth_headers,
                          json={"title": "Test", "body": "Body"}, timeout=30)
        assert r.status_code == 200


# ------------------ Slip code broadcast ------------------

class TestSlipCodeBroadcast:
    def test_set_slip_code_no_error(self, auth_headers):
        # Use a fresh code different from any current value
        from datetime import date
        today = date.today().isoformat()
        r = requests.post(f"{BASE_URL}/api/admin/slip/code",
                          headers=auth_headers,
                          json={"code": "TST4PH", "date": today}, timeout=15)
        assert r.status_code == 200
        assert r.json().get("code") == "TST4PH"

        # Same call again — should succeed (idempotent), no broadcast fired but no error
        r2 = requests.post(f"{BASE_URL}/api/admin/slip/code",
                           headers=auth_headers,
                           json={"code": "TST4PH", "date": today}, timeout=15)
        assert r2.status_code == 200


# ------------------ Strategy cap ------------------

class TestStrategyCap:
    def test_slip_today_respects_cap(self, auth_headers):
        r = requests.get(f"{BASE_URL}/api/slip/today", headers=auth_headers, timeout=20)
        assert r.status_code == 200
        body = r.json()
        slip = body.get("slip")
        if slip is None:
            pytest.skip("No slip available today — cannot verify cap")
        assert slip["leg_count"] <= 5, f"leg_count {slip['leg_count']} > 5"
        assert slip["combined_odds"] <= 5.0 + 1e-6, f"combined_odds {slip['combined_odds']} > 5.0"
        assert slip["leg_count"] == len(slip["legs"])


# ------------------ Regression auth ------------------

class TestRegression:
    def test_login_works(self):
        r = requests.post(f"{BASE_URL}/api/auth/login",
                          json={"email": ADMIN_EMAIL, "password": ADMIN_PASS}, timeout=15)
        assert r.status_code == 200
        assert "access_token" in r.json()

    def test_auth_me(self, auth_headers):
        r = requests.get(f"{BASE_URL}/api/auth/me", headers=auth_headers, timeout=15)
        assert r.status_code == 200
        assert r.json().get("role") == "admin"

    def test_admin_users(self, auth_headers):
        r = requests.get(f"{BASE_URL}/api/admin/users", headers=auth_headers, timeout=15)
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_admin_payments(self, auth_headers):
        r = requests.get(f"{BASE_URL}/api/admin/payments", headers=auth_headers, timeout=15)
        assert r.status_code == 200

    def test_admin_predictions(self, auth_headers):
        r = requests.get(f"{BASE_URL}/api/admin/predictions", headers=auth_headers, timeout=15)
        assert r.status_code == 200
