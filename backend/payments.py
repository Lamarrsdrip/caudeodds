"""Payments module: Flutterwave + manual bank transfer.

Keys are loaded dynamically from MongoDB admin_config (admin can update at any
time). Falls back to env vars if DB is empty. All HTTP calls are async via
httpx.
"""
from __future__ import annotations

import hashlib
import hmac
import logging
import os
import uuid
from datetime import datetime, timezone

import httpx
from motor.motor_asyncio import AsyncIOMotorDatabase

logger = logging.getLogger("claudeodd.payments")

FLW_BASE = {
    "sandbox": "https://api.flutterwave.com/v3",  # sandbox uses same base + test keys
    "production": "https://api.flutterwave.com/v3",
}


async def get_flw_config(db: AsyncIOMotorDatabase) -> dict:
    cfg = await db.admin_config.find_one({"_id": "main"}, {"_id": 0}) or {}
    env = cfg.get("flw_environment", "sandbox")
    return {
        "environment": env,
        "public_key": cfg.get("flw_public_key") or os.environ.get("FLW_PUBLIC_KEY", ""),
        "secret_key": cfg.get("flw_secret_key") or os.environ.get("FLW_SECRET_KEY", ""),
        "encryption_key": cfg.get("flw_encryption_key") or os.environ.get("FLW_ENCRYPTION_KEY", ""),
        "webhook_secret": cfg.get("flw_webhook_secret") or os.environ.get("FLW_WEBHOOK_SECRET", ""),
        "base_url": FLW_BASE[env],
    }


async def get_price_ngn(db: AsyncIOMotorDatabase) -> float:
    cfg = await db.admin_config.find_one({"_id": "main"}, {"_id": 0}) or {}
    return float(cfg.get("price_ngn", 5000.0))


async def init_flutterwave_payment(
    db: AsyncIOMotorDatabase,
    user: dict,
    redirect_url: str,
) -> dict:
    """Create a Flutterwave Standard checkout session."""
    flw = await get_flw_config(db)
    if not flw["secret_key"]:
        return {
            "ok": False,
            "error": "Flutterwave keys not configured. Admin must add them in Admin → Config.",
        }

    amount = await get_price_ngn(db)
    tx_ref = f"co_{uuid.uuid4().hex[:16]}"

    payload = {
        "tx_ref": tx_ref,
        "amount": str(amount),
        "currency": "NGN",
        "redirect_url": redirect_url,
        "customer": {
            "email": user["email"],
            "name": user.get("name", "ClaudeOdds User"),
        },
        "customizations": {
            "title": "ClaudeOdds VIP",
            "description": "Monthly VIP Slip Subscription",
        },
        "meta": {"user_id": user["id"]},
    }
    headers = {
        "Authorization": f"Bearer {flw['secret_key']}",
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(f"{flw['base_url']}/payments", json=payload, headers=headers)
        if r.status_code != 200:
            logger.warning("Flutterwave init failed %s: %s", r.status_code, r.text[:300])
            return {"ok": False, "error": f"Flutterwave error: {r.status_code}"}
        data = r.json()
        link = (data.get("data") or {}).get("link")
        if not link:
            return {"ok": False, "error": "No checkout link returned"}
    except Exception as e:
        logger.exception("Flutterwave init exception")
        return {"ok": False, "error": f"Network error: {e}"}

    payment_doc = {
        "id": str(uuid.uuid4()),
        "user_id": user["id"],
        "user_email": user["email"],
        "amount": amount,
        "currency": "NGN",
        "method": "flutterwave",
        "status": "pending",
        "tx_ref": tx_ref,
        "flutterwave_link": link,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.payments.insert_one(payment_doc)
    return {"ok": True, "checkout_link": link, "tx_ref": tx_ref, "payment_id": payment_doc["id"]}


async def verify_flutterwave_tx(db: AsyncIOMotorDatabase, tx_ref: str) -> dict:
    flw = await get_flw_config(db)
    if not flw["secret_key"]:
        return {"ok": False, "error": "Flutterwave not configured"}
    headers = {"Authorization": f"Bearer {flw['secret_key']}"}
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.get(
                f"{flw['base_url']}/transactions/verify_by_reference",
                params={"tx_ref": tx_ref},
                headers=headers,
            )
        if r.status_code != 200:
            return {"ok": False, "error": f"Verify failed: {r.status_code}"}
        body = r.json()
        d = body.get("data") or {}
        return {"ok": True, "status": d.get("status"), "amount": d.get("amount"), "id": d.get("id")}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def verify_webhook_signature(secret: str, signature_header: str, raw_body: bytes) -> bool:
    """Flutterwave sends `verif-hash` header equal to the merchant's `secret_hash`.
    Some setups send raw secret directly; we support both: direct equality OR HMAC.
    """
    if not secret or not signature_header:
        return False
    if hmac.compare_digest(secret, signature_header):
        return True
    computed = hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(computed, signature_header)
