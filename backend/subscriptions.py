"""Subscription state machine for CLAUDEODD.

Trial: 3 days from registration. Active: paid. Expired: lapsed.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from motor.motor_asyncio import AsyncIOMotorDatabase


def now() -> datetime:
    return datetime.now(timezone.utc)


def now_iso() -> str:
    return now().isoformat()


async def start_trial(db: AsyncIOMotorDatabase, user_id: str, days: int = 3) -> str:
    """Start a free trial. Returns trial_ends_at ISO string."""
    ends_at = (now() + timedelta(days=days)).isoformat()
    await db.users.update_one(
        {"id": user_id},
        {"$set": {
            "subscription_status": "trial",
            "trial_ends_at": ends_at,
            "subscription_ends_at": None,
        }},
    )
    return ends_at


async def activate_paid(db: AsyncIOMotorDatabase, user_id: str, days: int = 30, payment_id: str | None = None) -> str:
    """Activate or extend paid subscription. Returns subscription_ends_at."""
    user = await db.users.find_one({"id": user_id}, {"_id": 0})
    base = now()
    if user and user.get("subscription_ends_at"):
        try:
            existing = datetime.fromisoformat(user["subscription_ends_at"])
            if existing > base:
                base = existing  # extend
        except Exception:
            pass
    ends_at = (base + timedelta(days=days)).isoformat()
    update = {
        "subscription_status": "active",
        "subscription_ends_at": ends_at,
    }
    if payment_id:
        update["last_payment_id"] = payment_id
    await db.users.update_one({"id": user_id}, {"$set": update})
    return ends_at


async def refresh_status(db: AsyncIOMotorDatabase, user: dict) -> dict:
    """Recompute subscription status based on dates. Returns updated user dict."""
    n = now()
    sub_end_iso = user.get("subscription_ends_at")
    trial_end_iso = user.get("trial_ends_at")

    new_status = "none"
    sub_active = False
    if sub_end_iso:
        try:
            if datetime.fromisoformat(sub_end_iso) > n:
                new_status = "active"
                sub_active = True
        except Exception:
            pass
    if not sub_active and trial_end_iso:
        try:
            if datetime.fromisoformat(trial_end_iso) > n:
                new_status = "trial"
            else:
                new_status = "expired"
        except Exception:
            pass
    # If user previously had a paid sub that has now lapsed (no trial), still mark expired
    if new_status == "none" and sub_end_iso and not sub_active:
        new_status = "expired"
    if user.get("role") == "admin":
        new_status = "active"

    if new_status != user.get("subscription_status"):
        await db.users.update_one({"id": user["id"]}, {"$set": {"subscription_status": new_status}})
        user["subscription_status"] = new_status
    return user


def has_access(user: dict) -> bool:
    return user.get("subscription_status") in ("trial", "active") or user.get("role") == "admin"
