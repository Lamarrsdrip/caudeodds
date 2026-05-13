"""Referral + device-fingerprint helpers for ClaudeOdds.

Trial abuse prevention:
  - Each registration must carry a unique `device_fingerprint`. We reject any
    new signup whose fingerprint already exists in the users collection.

Referral rewards (per product spec):
  - Referee (new user) gets 5-day trial instead of the default trial_days.
  - Referrer gets +1 day extension on their active subscription/trial per
    successful referral.
  - Each user's referrals_count is tracked and exposed via /api/referral/me.
"""
from __future__ import annotations

import secrets
import string
from datetime import datetime, timedelta, timezone

from motor.motor_asyncio import AsyncIOMotorDatabase


REFERRAL_TRIAL_DAYS = 5  # referee bonus trial length
REFERRER_BONUS_DAYS = 1  # extension added to referrer per signup


def _now() -> datetime:
    return datetime.now(timezone.utc)


def generate_referral_code(length: int = 8) -> str:
    """Short, unambiguous, URL-safe code. Avoid 0/O/1/I confusion."""
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    return "".join(secrets.choice(alphabet) for _ in range(length))


async def ensure_unique_code(db: AsyncIOMotorDatabase) -> str:
    """Generate a referral code that doesn't collide with existing users."""
    for _ in range(8):
        code = generate_referral_code()
        existing = await db.users.find_one({"referral_code": code}, {"_id": 0, "id": 1})
        if not existing:
            return code
    # Astronomically unlikely; fall back to a longer code.
    return generate_referral_code(12)


async def find_referrer(db: AsyncIOMotorDatabase, raw_code: str | None) -> dict | None:
    """Return the user dict for a referral code, or None if invalid/blank."""
    if not raw_code:
        return None
    code = raw_code.strip().upper()
    if not code:
        return None
    return await db.users.find_one(
        {"referral_code": code},
        {"_id": 0, "password_hash": 0},
    )


async def device_already_used(
    db: AsyncIOMotorDatabase, fingerprint: str | None
) -> bool:
    """True if this device fingerprint has already been used to register."""
    if not fingerprint:
        return False
    fp = fingerprint.strip()
    if len(fp) < 8:  # too short to be a real fingerprint — ignore
        return False
    existing = await db.users.find_one(
        {"device_fingerprint": fp},
        {"_id": 0, "id": 1},
    )
    return existing is not None


async def reward_referrer(db: AsyncIOMotorDatabase, referrer: dict) -> str | None:
    """Add REFERRER_BONUS_DAYS to the referrer's active sub or trial window.

    Extension rule:
      - If they have an active paid subscription_ends_at in the future → extend it
      - Else if they're on trial → extend trial_ends_at
      - Else (expired) → start a fresh 1-day "active" window from now so they
        get an immediate taste of value and come back to claim more.

    Returns the new ends_at ISO string or None on no-op.
    """
    if not referrer:
        return None
    n = _now()
    user_id = referrer["id"]
    sub_end = referrer.get("subscription_ends_at")
    trial_end = referrer.get("trial_ends_at")

    base = None
    target_field = None
    new_status = referrer.get("subscription_status", "none")

    # Active paid sub → extend it
    if sub_end:
        try:
            existing = datetime.fromisoformat(sub_end)
            if existing > n:
                base = existing
                target_field = "subscription_ends_at"
                new_status = "active"
        except Exception:
            pass

    # On trial → extend trial
    if base is None and trial_end:
        try:
            existing_trial = datetime.fromisoformat(trial_end)
            if existing_trial > n:
                base = existing_trial
                target_field = "trial_ends_at"
                new_status = "trial"
        except Exception:
            pass

    # Expired or never-paid → grant a short paid window so they see the value
    if base is None:
        base = n
        target_field = "subscription_ends_at"
        new_status = "active"

    new_ends = (base + timedelta(days=REFERRER_BONUS_DAYS)).isoformat()
    await db.users.update_one(
        {"id": user_id},
        {
            "$set": {target_field: new_ends, "subscription_status": new_status},
            "$inc": {"referrals_count": 1},
        },
    )
    return new_ends


async def list_referrals(db: AsyncIOMotorDatabase, referrer_id: str) -> list[dict]:
    """Return the list of users this referrer has invited (lightweight)."""
    cursor = db.users.find(
        {"referred_by_id": referrer_id},
        {"_id": 0, "email": 1, "name": 1, "created_at": 1},
    ).sort("created_at", -1).limit(200)
    return [u async for u in cursor]
