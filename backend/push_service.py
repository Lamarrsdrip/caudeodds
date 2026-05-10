"""Web Push notifications via VAPID for ClaudeOdds.

Sends notifications to subscribers when the admin publishes a SportyBet code
or when the daily slip is generated.

Storage: db.push_subscriptions = {user_id, endpoint, p256dh, auth, created_at, active}
        db.vapid_keys           = {private_key, public_key, subject_email, created_at, active}
"""
from __future__ import annotations

import asyncio
import base64
import json
import logging
import time
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import urlparse

import ecdsa
from pywebpush import WebPushException, webpush

logger = logging.getLogger("claudeodd.push")


def _b64url(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode("utf-8")


async def get_or_create_vapid(db, subject_email: str = "admin@claudeodd.com") -> dict:
    """Return active VAPID keypair, generating a new one if none exists."""
    doc = await db.vapid_keys.find_one({"active": True}, {"_id": 0})
    if doc:
        return doc
    pk = ecdsa.SigningKey.generate(curve=ecdsa.NIST256p)
    vk = pk.get_verifying_key()
    private_key = _b64url(pk.to_string())
    public_key = _b64url(b"\x04" + vk.to_string())
    doc = {
        "private_key": private_key,
        "public_key": public_key,
        "subject_email": subject_email,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "active": True,
    }
    await db.vapid_keys.insert_one(dict(doc))
    logger.info("Generated new VAPID keypair (public_key=%s…)", public_key[:20])
    return doc


async def get_public_key(db) -> str:
    vapid = await get_or_create_vapid(db)
    return vapid["public_key"]


async def save_subscription(db, user_id: str, subscription: dict, user_agent: str = "") -> dict:
    endpoint = subscription.get("endpoint")
    keys = subscription.get("keys") or {}
    p256dh = keys.get("p256dh")
    auth = keys.get("auth")
    if not (endpoint and p256dh and auth):
        raise ValueError("Invalid push subscription payload")
    doc = {
        "user_id": user_id,
        "endpoint": endpoint,
        "p256dh": p256dh,
        "auth": auth,
        "user_agent": user_agent[:300],
        "created_at": datetime.now(timezone.utc).isoformat(),
        "active": True,
    }
    await db.push_subscriptions.update_one(
        {"endpoint": endpoint},
        {"$set": doc},
        upsert=True,
    )
    return doc


async def remove_subscription(db, endpoint: str) -> int:
    res = await db.push_subscriptions.delete_one({"endpoint": endpoint})
    return res.deleted_count


def _send_one(sub: dict, payload: dict, vapid_priv: str, subject_email: str) -> str:
    """Synchronous send (run via asyncio.to_thread). Returns 'sent' / 'invalid' / 'failed'."""
    parsed = urlparse(sub["endpoint"])
    aud = f"{parsed.scheme}://{parsed.netloc}"
    claims = {
        "sub": f"mailto:{subject_email}",
        "aud": aud,
        "exp": int(time.time()) + 12 * 3600,
    }
    try:
        webpush(
            subscription_info={
                "endpoint": sub["endpoint"],
                "keys": {"p256dh": sub["p256dh"], "auth": sub["auth"]},
            },
            data=json.dumps(payload),
            vapid_private_key=vapid_priv,
            vapid_claims=claims,
            timeout=8,
        )
        return "sent"
    except WebPushException as e:
        msg = str(e)
        if "410" in msg or "404" in msg:
            return "invalid"
        logger.warning("Push delivery error: %s", msg[:200])
        return "failed"
    except Exception as e:
        logger.warning("Push delivery exception: %s", e)
        return "failed"


async def broadcast(db, title: str, body: str, url: str = "/dashboard",
                    user_filter: Optional[dict] = None) -> dict:
    """Broadcast a push to all active subscriptions (optionally filtered by user_id $in [..])."""
    vapid = await get_or_create_vapid(db)
    query = {"active": True}
    if user_filter:
        query.update(user_filter)
    subs = await db.push_subscriptions.find(query, {"_id": 0}).to_list(length=5000)
    if not subs:
        return {"sent": 0, "invalid": 0, "failed": 0, "total": 0}

    payload = {
        "title": title,
        "body": body,
        "url": url,
        "icon": "/icon-192.png",
        "badge": "/icon-192.png",
        "data": {"url": url, "ts": int(time.time() * 1000)},
    }

    async def _go(sub: dict) -> str:
        return await asyncio.to_thread(
            _send_one, sub, payload, vapid["private_key"], vapid.get("subject_email", "admin@claudeodd.com")
        )

    results = await asyncio.gather(*[_go(s) for s in subs], return_exceptions=False)
    sent = sum(1 for r in results if r == "sent")
    invalid = sum(1 for r in results if r == "invalid")
    failed = sum(1 for r in results if r == "failed")
    # Cleanup invalid endpoints
    invalid_endpoints = [subs[i]["endpoint"] for i, r in enumerate(results) if r == "invalid"]
    if invalid_endpoints:
        await db.push_subscriptions.update_many(
            {"endpoint": {"$in": invalid_endpoints}},
            {"$set": {"active": False}},
        )
    logger.info("Push broadcast — sent=%d invalid=%d failed=%d total=%d", sent, invalid, failed, len(subs))
    return {"sent": sent, "invalid": invalid, "failed": failed, "total": len(subs)}
