"""Auth module: bcrypt + JWT + admin seed + brute force lockout."""
from __future__ import annotations

import logging
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
import jwt
from fastapi import Depends, HTTPException, Request, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from saas_models import UserPublic

logger = logging.getLogger("claudeodd.auth")

JWT_ALGO = "HS256"
ACCESS_TOKEN_TTL_HOURS = 24 * 7  # 7-day session
LOCKOUT_THRESHOLD = 5
LOCKOUT_MINUTES = 15


def hash_password(p: str) -> str:
    return bcrypt.hashpw(p.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


def jwt_secret() -> str:
    s = os.environ.get("JWT_SECRET")
    if not s:
        raise RuntimeError("JWT_SECRET not configured")
    return s


def create_access_token(user_id: str, email: str, role: str) -> str:
    payload = {
        "sub": user_id,
        "email": email,
        "role": role,
        "exp": datetime.now(timezone.utc) + timedelta(hours=ACCESS_TOKEN_TTL_HOURS),
        "iat": datetime.now(timezone.utc),
        "type": "access",
    }
    return jwt.encode(payload, jwt_secret(), algorithm=JWT_ALGO)


def decode_token(token: str) -> dict:
    return jwt.decode(token, jwt_secret(), algorithms=[JWT_ALGO])


def _user_to_public(u: dict) -> UserPublic:
    return UserPublic(
        id=u["id"],
        email=u["email"],
        name=u.get("name", ""),
        role=u.get("role", "user"),
        dob=u.get("dob"),
        created_at=u.get("created_at", ""),
        subscription_status=u.get("subscription_status", "none"),
        trial_ends_at=u.get("trial_ends_at"),
        subscription_ends_at=u.get("subscription_ends_at"),
    )


async def get_current_user_dep(request: Request) -> dict:
    """FastAPI dependency: returns the user dict (raw) or raises 401."""
    db: AsyncIOMotorDatabase = request.app.state.db
    token: Optional[str] = None

    # Authorization header
    auth_header = request.headers.get("Authorization") or ""
    if auth_header.lower().startswith("bearer "):
        token = auth_header[7:].strip()
    # Cookie fallback
    if not token:
        token = request.cookies.get("access_token")

    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    try:
        payload = decode_token(token)
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

    user = await db.users.find_one({"id": payload["sub"]}, {"_id": 0, "password_hash": 0})
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user


async def admin_required(user: dict = Depends(get_current_user_dep)) -> dict:
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


# ------------------ Brute force ------------------

async def is_locked(db: AsyncIOMotorDatabase, identifier: str) -> bool:
    rec = await db.login_attempts.find_one({"_id": identifier})
    if not rec:
        return False
    locked_until_iso = rec.get("locked_until")
    if not locked_until_iso:
        return False
    locked_until = datetime.fromisoformat(locked_until_iso)
    return datetime.now(timezone.utc) < locked_until


async def record_failure(db: AsyncIOMotorDatabase, identifier: str) -> None:
    rec = await db.login_attempts.find_one({"_id": identifier})
    count = (rec or {}).get("count", 0) + 1
    update = {"count": count, "last": datetime.now(timezone.utc).isoformat()}
    if count >= LOCKOUT_THRESHOLD:
        update["locked_until"] = (datetime.now(timezone.utc) + timedelta(minutes=LOCKOUT_MINUTES)).isoformat()
        update["count"] = 0  # reset after lockout window
    await db.login_attempts.update_one({"_id": identifier}, {"$set": update}, upsert=True)


async def clear_failures(db: AsyncIOMotorDatabase, identifier: str) -> None:
    await db.login_attempts.delete_one({"_id": identifier})


# ------------------ Seed admin ------------------

async def seed_admin(db: AsyncIOMotorDatabase) -> None:
    email = os.environ.get("ADMIN_EMAIL", "admin@claudeodd.com").lower().strip()
    pw = os.environ.get("ADMIN_PASSWORD", "Admin@2026")

    existing = await db.users.find_one({"email": email}, {"_id": 0})
    if existing is None:
        import uuid
        doc = {
            "id": str(uuid.uuid4()),
            "email": email,
            "name": "Super Admin",
            "role": "admin",
            "password_hash": hash_password(pw),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "subscription_status": "active",  # admin always has access
            "subscription_ends_at": (datetime.now(timezone.utc) + timedelta(days=3650)).isoformat(),
            "trial_ends_at": None,
            "dob": None,
            "age_18_plus": True,
            "accepted_terms": True,
        }
        await db.users.insert_one(doc)
        logger.info("Seeded admin user %s", email)
    elif not verify_password(pw, existing.get("password_hash", "")):
        await db.users.update_one(
            {"email": email},
            {"$set": {"password_hash": hash_password(pw), "role": "admin"}},
        )
        logger.info("Updated admin password for %s", email)


def random_secret(n: int = 32) -> str:
    return secrets.token_urlsafe(n)
