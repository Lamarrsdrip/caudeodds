"""Server: CLAUDEODD SaaS — auth, subscriptions, payments, admin, slips."""
from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request, status  # noqa: E402
from motor.motor_asyncio import AsyncIOMotorClient  # noqa: E402
from starlette.middleware.cors import CORSMiddleware  # noqa: E402

from auth import (  # noqa: E402
    admin_required,
    clear_failures,
    create_access_token,
    get_current_user_dep,
    hash_password,
    is_locked,
    record_failure,
    seed_admin,
    verify_password,
)
from consensus import select_top  # noqa: E402
from data_engine import generate_fixtures_for_date  # noqa: E402
from payments import (  # noqa: E402
    init_flutterwave_payment,
    get_flw_config,
    get_price_ngn,
    verify_flutterwave_tx,
    verify_webhook_signature,
)
from pipeline import run_pipeline, today_str  # noqa: E402
from saas_models import (  # noqa: E402
    AdminConfig,
    BankTransferProofPayload,
    CombinedSlip,
    LoginPayload,
    Payment,
    PaymentInitPayload,
    RegisterPayload,
    Subscription,
    TokenResponse,
    UserPublic,
)
from slip_builder import build_slip  # noqa: E402
from subscriptions import (  # noqa: E402
    activate_paid,
    has_access,
    refresh_status,
    start_trial,
)
from models import Pick, RejectionLog, SettlePayload, Settings  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("claudeodd.server")

mongo_url = os.environ["MONGO_URL"]
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ["DB_NAME"]]

# Collections
picks_col = db.claudeodd_picks
rej_col = db.claudeodd_rejections
runs_col = db.claudeodd_runs
settings_col = db.claudeodd_settings  # ensemble settings
admin_cfg_col = db.admin_config  # business config
users_col = db.users
sub_col = db.subscriptions
pay_col = db.payments
attempt_col = db.login_attempts

app = FastAPI(title="CLAUDEODD")
app.state.db = db


@app.on_event("startup")
async def on_startup():
    await users_col.create_index("email", unique=True)
    await users_col.create_index("id", unique=True)
    await pay_col.create_index("user_id")
    await pay_col.create_index("status")
    await seed_admin(db)
    logger.info("CLAUDEODD startup complete")


@app.on_event("shutdown")
async def on_shutdown():
    client.close()


api = APIRouter(prefix="/api")


# ------------------ Health ------------------

@api.get("/")
async def root():
    return {"app": "CLAUDEODD", "status": "ok", "version": "2.0"}


@api.get("/public/config")
async def public_config():
    cfg = await admin_cfg_col.find_one({"_id": "main"}, {"_id": 0}) or {}
    return {
        "price_ngn": cfg.get("price_ngn", 5000.0),
        "trial_days": cfg.get("trial_days", 3),
        "plan_label": cfg.get("plan_label", "VIP Daily Slip"),
        "brand_tagline": cfg.get("brand_tagline", "AI-quant betting intelligence — disciplined daily edge."),
        "sportybet_handle": cfg.get("sportybet_handle", "https://www.sportybet.com/ng/"),
        "bank_name": cfg.get("bank_name", ""),
        "bank_account_number": cfg.get("bank_account_number", ""),
        "bank_account_name": cfg.get("bank_account_name", ""),
        "bank_instructions": cfg.get("bank_instructions", ""),
        "flw_public_key": cfg.get("flw_public_key", ""),
    }


# ------------------ Auth ------------------

@api.post("/auth/register", response_model=TokenResponse)
async def auth_register(payload: RegisterPayload):
    if not payload.age_18_plus:
        raise HTTPException(status_code=400, detail="You must be 18+ to use CLAUDEODD")
    if not payload.accept_terms:
        raise HTTPException(status_code=400, detail="You must accept the Terms & Privacy Policy")

    email = payload.email.lower().strip()
    existing = await users_col.find_one({"email": email}, {"_id": 0})
    if existing:
        raise HTTPException(status_code=409, detail="Email already registered")

    user_id = str(uuid.uuid4())
    cfg = await admin_cfg_col.find_one({"_id": "main"}, {"_id": 0}) or {}
    trial_days = int(cfg.get("trial_days", 3))

    doc = {
        "id": user_id,
        "email": email,
        "name": payload.name.strip(),
        "role": "user",
        "password_hash": hash_password(payload.password),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "dob": payload.dob,
        "age_18_plus": True,
        "accepted_terms": True,
        "subscription_status": "trial",
        "trial_ends_at": None,
        "subscription_ends_at": None,
    }
    await users_col.insert_one(doc)
    trial_ends = await start_trial(db, user_id, days=trial_days)
    doc["trial_ends_at"] = trial_ends
    doc["subscription_status"] = "trial"
    doc.pop("password_hash", None)

    token = create_access_token(user_id, email, "user")
    return TokenResponse(
        access_token=token,
        user=UserPublic(
            id=user_id, email=email, name=doc["name"], role="user",
            dob=doc["dob"], created_at=doc["created_at"],
            subscription_status="trial", trial_ends_at=trial_ends,
            subscription_ends_at=None,
        ),
    )


@api.post("/auth/login", response_model=TokenResponse)
async def auth_login(payload: LoginPayload, request: Request):
    email = payload.email.lower().strip()
    identifier = email  # email-only: K8s ingress rotates client IPs across pods, so per-IP counters fragment

    if await is_locked(db, identifier):
        raise HTTPException(status_code=429, detail="Too many failed attempts. Try again in 15 minutes.")

    user = await users_col.find_one({"email": email}, {"_id": 0})
    if not user or not verify_password(payload.password, user.get("password_hash", "")):
        await record_failure(db, identifier)
        raise HTTPException(status_code=401, detail="Invalid email or password")

    await clear_failures(db, identifier)
    user = await refresh_status(db, user)
    token = create_access_token(user["id"], email, user.get("role", "user"))
    return TokenResponse(
        access_token=token,
        user=UserPublic(
            id=user["id"], email=email, name=user.get("name", ""), role=user.get("role", "user"),
            dob=user.get("dob"), created_at=user.get("created_at", ""),
            subscription_status=user.get("subscription_status", "none"),
            trial_ends_at=user.get("trial_ends_at"),
            subscription_ends_at=user.get("subscription_ends_at"),
        ),
    )


@api.get("/auth/me", response_model=UserPublic)
async def auth_me(user: dict = Depends(get_current_user_dep)):
    user = await refresh_status(db, user)
    return UserPublic(
        id=user["id"], email=user["email"], name=user.get("name", ""),
        role=user.get("role", "user"), dob=user.get("dob"), created_at=user.get("created_at", ""),
        subscription_status=user.get("subscription_status", "none"),
        trial_ends_at=user.get("trial_ends_at"),
        subscription_ends_at=user.get("subscription_ends_at"),
    )


@api.post("/auth/logout")
async def auth_logout(user: dict = Depends(get_current_user_dep)):
    return {"ok": True}


# ------------------ Daily Slip ------------------

@api.get("/slip/today")
async def slip_today(request: Request):
    """Public endpoint with locked teaser; full slip if user has access."""
    date_str = today_str()
    docs = await picks_col.find({"date": date_str}, {"_id": 0}).to_list(50)
    cfg = await admin_cfg_col.find_one({"_id": "main"}, {"_id": 0}) or {}
    sb_url = cfg.get("sportybet_handle", "https://www.sportybet.com/ng/")
    picks = [Pick(**d) for d in docs]
    slip = build_slip(date_str, picks, sportybet_url=sb_url)

    # Check user
    locked = True
    user = None
    auth_header = request.headers.get("Authorization") or ""
    token = auth_header[7:].strip() if auth_header.lower().startswith("bearer ") else None
    if token:
        try:
            from auth import decode_token
            payload = decode_token(token)
            user = await users_col.find_one({"id": payload["sub"]}, {"_id": 0, "password_hash": 0})
            if user:
                user = await refresh_status(db, user)
                locked = not has_access(user)
        except Exception:
            pass

    if not slip:
        return {"date": date_str, "slip": None, "locked": locked, "fixtures_analyzed": 0}

    # If locked, return a teaser (no leg details)
    if locked:
        teaser = slip.model_dump()
        teaser["legs"] = [{
            "match": "🔒 Locked", "league": leg.league, "sport": leg.sport,
            "market": "🔒", "selection_label": "Subscribe to unlock",
            "odds": leg.odds, "confidence": 0, "edge_pct": 0, "reasoning": "",
        } for leg in slip.legs]
        teaser["sportybet_code"] = "🔒 SB-XXXXXX-XXXX"
        teaser["summary"] = (
            f"{slip.leg_count}-leg slip ready. Subscribe to unlock the picks, the SportyBet booking code, "
            f"and the full AI ensemble reasoning."
        )
        teaser["locked"] = True
        return {"date": date_str, "slip": teaser, "locked": True}

    return {"date": date_str, "slip": slip.model_dump(), "locked": False}


@api.post("/slip/generate")
async def slip_generate(force: bool = False, _: dict = Depends(admin_required)):
    """Admin-triggered generation. Wraps the ensemble pipeline."""
    date_str = today_str()
    settings_doc = await settings_col.find_one({"_id": "main"}, {"_id": 0})
    settings = Settings(**settings_doc) if settings_doc else Settings()

    if not force:
        run = await runs_col.find_one({"_id": date_str}, {"_id": 0})
        if run:
            cached = await picks_col.find({"date": date_str}, {"_id": 0}).to_list(50)
            return {"date": date_str, "cached": True, "picks": len(cached)}

    picks, rejections, total = await run_pipeline(date_str, settings)
    if force:
        await picks_col.delete_many({"date": date_str})
        await rej_col.delete_many({"date": date_str})
    if picks:
        await picks_col.insert_many([p.model_dump() for p in picks])
    if rejections:
        await rej_col.insert_many([r.model_dump() for r in rejections])
    await runs_col.update_one(
        {"_id": date_str},
        {"$set": {"date": date_str, "rejected_count": len(rejections), "fixtures_analyzed": total,
                  "completed_at": datetime.now(timezone.utc).isoformat()}},
        upsert=True,
    )
    return {"date": date_str, "cached": False, "picks": len(picks), "rejected": len(rejections),
            "fixtures_analyzed": total}


@api.get("/slip/history")
async def slip_history(limit: int = 60, user: dict = Depends(get_current_user_dep)):
    """Past slips: aggregated per date."""
    user = await refresh_status(db, user)
    if not has_access(user):
        raise HTTPException(status_code=402, detail="Subscription required")
    docs = await picks_col.find({}, {"_id": 0}).sort("created_at", -1).to_list(2000)
    by_date: dict = {}
    for d in docs:
        by_date.setdefault(d["date"], []).append(d)
    cfg = await admin_cfg_col.find_one({"_id": "main"}, {"_id": 0}) or {}
    sb_url = cfg.get("sportybet_handle", "https://www.sportybet.com/ng/")
    out = []
    for date in sorted(by_date.keys(), reverse=True)[:limit]:
        picks = [Pick(**p) for p in by_date[date]]
        slip = build_slip(date, picks, sportybet_url=sb_url)
        if slip:
            d = slip.model_dump()
            # legs status from picks
            d["status_summary"] = {
                "won": sum(1 for p in picks if p.status == "won"),
                "lost": sum(1 for p in picks if p.status == "lost"),
                "void": sum(1 for p in picks if p.status == "void"),
                "pending": sum(1 for p in picks if p.status == "pending"),
            }
            out.append(d)
    return out


# ------------------ Payments ------------------

@api.post("/payments/flutterwave/init")
async def flw_init(payload: PaymentInitPayload, user: dict = Depends(get_current_user_dep)):
    redirect_url = f"{os.environ.get('FRONTEND_URL', '')}/payment/callback"
    res = await init_flutterwave_payment(db, user, redirect_url)
    if not res.get("ok"):
        raise HTTPException(status_code=400, detail=res.get("error", "Flutterwave init failed"))
    return res


@api.post("/payments/flutterwave/verify")
async def flw_verify(tx_ref: str, user: dict = Depends(get_current_user_dep)):
    payment = await pay_col.find_one({"tx_ref": tx_ref, "user_id": user["id"]}, {"_id": 0})
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")
    res = await verify_flutterwave_tx(db, tx_ref)
    if res.get("ok") and res.get("status") == "successful":
        await pay_col.update_one({"id": payment["id"]}, {"$set": {
            "status": "successful",
            "flutterwave_id": res.get("id"),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }})
        ends = await activate_paid(db, user["id"], days=30, payment_id=payment["id"])
        return {"ok": True, "status": "successful", "subscription_ends_at": ends}
    return {"ok": False, "status": res.get("status", "unknown"), "error": res.get("error")}


@api.post("/payments/flutterwave/webhook")
async def flw_webhook(request: Request):
    body = await request.body()
    sig = request.headers.get("verif-hash") or request.headers.get("x-flw-signature") or ""
    flw = await get_flw_config(db)
    if not verify_webhook_signature(flw["webhook_secret"], sig, body):
        raise HTTPException(status_code=401, detail="Invalid signature")
    import json
    payload = json.loads(body)
    tx_ref = (payload.get("data") or {}).get("tx_ref")
    status_code = (payload.get("data") or {}).get("status")
    if not tx_ref:
        return {"ok": False}
    payment = await pay_col.find_one({"tx_ref": tx_ref}, {"_id": 0})
    if not payment:
        return {"ok": False}
    if status_code == "successful":
        await pay_col.update_one({"id": payment["id"]}, {"$set": {
            "status": "successful",
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }})
        await activate_paid(db, payment["user_id"], days=30, payment_id=payment["id"])
    elif status_code == "failed":
        await pay_col.update_one({"id": payment["id"]}, {"$set": {
            "status": "failed", "updated_at": datetime.now(timezone.utc).isoformat()}})
    return {"ok": True}


@api.post("/payments/bank-transfer", response_model=Payment)
async def bank_transfer(payload: BankTransferProofPayload, user: dict = Depends(get_current_user_dep)):
    if len(payload.proof_data_url) > 4_000_000:
        raise HTTPException(status_code=413, detail="Proof image too large (max ~3MB)")
    amount = await get_price_ngn(db)
    p = Payment(
        user_id=user["id"], user_email=user["email"], amount=amount, currency="NGN",
        method="bank_transfer", status="pending",
        proof_data_url=payload.proof_data_url,
        sender_name=payload.sender_name,
        reference=payload.reference,
    )
    await pay_col.insert_one(p.model_dump())
    return p


@api.get("/payments/mine", response_model=List[Payment])
async def payments_mine(user: dict = Depends(get_current_user_dep)):
    docs = await pay_col.find({"user_id": user["id"]}, {"_id": 0}).sort("created_at", -1).to_list(50)
    return [Payment(**d) for d in docs]


# ------------------ Admin ------------------

@api.get("/admin/stats")
async def admin_stats(_: dict = Depends(admin_required)):
    total_users = await users_col.count_documents({})
    trial_users = await users_col.count_documents({"subscription_status": "trial"})
    active_users = await users_col.count_documents({"subscription_status": "active", "role": "user"})
    expired = await users_col.count_documents({"subscription_status": "expired"})
    pending_payments = await pay_col.count_documents({"status": "pending"})
    successful_payments = await pay_col.count_documents({"status": "successful"})
    revenue_docs = await pay_col.find({"status": "successful"}, {"_id": 0, "amount": 1}).to_list(10000)
    revenue = sum(d.get("amount", 0) for d in revenue_docs)
    return {
        "total_users": total_users,
        "trial_users": trial_users,
        "active_subscribers": active_users,
        "expired_subscribers": expired,
        "pending_payments": pending_payments,
        "successful_payments": successful_payments,
        "revenue_ngn": revenue,
    }


@api.get("/admin/users")
async def admin_users(limit: int = 200, _: dict = Depends(admin_required)):
    docs = await users_col.find({}, {"_id": 0, "password_hash": 0}).sort("created_at", -1).to_list(limit)
    return docs


@api.post("/admin/users/{user_id}/grant")
async def admin_grant(user_id: str, days: int = 30, _: dict = Depends(admin_required)):
    user = await users_col.find_one({"id": user_id}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    ends = await activate_paid(db, user_id, days=days)
    return {"ok": True, "subscription_ends_at": ends}


@api.post("/admin/users/{user_id}/suspend")
async def admin_suspend(user_id: str, _: dict = Depends(admin_required)):
    await users_col.update_one({"id": user_id}, {"$set": {
        "subscription_status": "expired",
        "trial_ends_at": None, "subscription_ends_at": None,
    }})
    return {"ok": True}


@api.get("/admin/payments")
async def admin_payments(status_filter: Optional[str] = None, _: dict = Depends(admin_required)):
    q = {}
    if status_filter and status_filter != "all":
        q["status"] = status_filter
    docs = await pay_col.find(q, {"_id": 0}).sort("created_at", -1).to_list(500)
    return docs


@api.post("/admin/payments/{payment_id}/approve")
async def admin_approve_payment(payment_id: str, note: str = "", _: dict = Depends(admin_required)):
    p = await pay_col.find_one({"id": payment_id}, {"_id": 0})
    if not p:
        raise HTTPException(status_code=404, detail="Payment not found")
    if p["status"] == "successful":
        return {"ok": True, "already": True}
    await pay_col.update_one({"id": payment_id}, {"$set": {
        "status": "successful", "admin_note": note,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }})
    ends = await activate_paid(db, p["user_id"], days=30, payment_id=payment_id)
    return {"ok": True, "subscription_ends_at": ends}


@api.post("/admin/payments/{payment_id}/reject")
async def admin_reject_payment(payment_id: str, note: str = "", _: dict = Depends(admin_required)):
    await pay_col.update_one({"id": payment_id}, {"$set": {
        "status": "rejected", "admin_note": note,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }})
    return {"ok": True}


@api.get("/admin/config", response_model=AdminConfig)
async def admin_get_config(_: dict = Depends(admin_required)):
    doc = await admin_cfg_col.find_one({"_id": "main"}, {"_id": 0}) or {}
    cfg = AdminConfig(**doc)
    # Mask secrets on GET so they're not echoed in admin UI logs / screenshots
    if cfg.flw_secret_key:
        cfg.flw_secret_key = "****" + cfg.flw_secret_key[-4:]
    if cfg.flw_encryption_key:
        cfg.flw_encryption_key = "****" + cfg.flw_encryption_key[-4:]
    if cfg.flw_webhook_secret:
        cfg.flw_webhook_secret = "****" + cfg.flw_webhook_secret[-4:]
    if cfg.smtp_password:
        cfg.smtp_password = "********"
    if cfg.telegram_bot_token:
        cfg.telegram_bot_token = "****" + cfg.telegram_bot_token[-4:]
    return cfg


@api.post("/admin/config", response_model=AdminConfig)
async def admin_set_config(cfg: AdminConfig, _: dict = Depends(admin_required)):
    cfg.updated_at = datetime.now(timezone.utc).isoformat()
    # Don't persist masked placeholders — re-load existing values for any field still masked
    existing = await admin_cfg_col.find_one({"_id": "main"}, {"_id": 0}) or {}
    payload = cfg.model_dump()
    for secret_field in ["flw_secret_key", "flw_encryption_key", "flw_webhook_secret", "smtp_password", "telegram_bot_token"]:
        v = payload.get(secret_field, "")
        if v and (v.startswith("****") or v == "********"):
            payload[secret_field] = existing.get(secret_field, "")
    await admin_cfg_col.update_one({"_id": "main"}, {"$set": payload}, upsert=True)
    return cfg


@api.get("/admin/predictions")
async def admin_predictions(date: Optional[str] = None, _: dict = Depends(admin_required)):
    q = {}
    if date:
        q["date"] = date
    docs = await picks_col.find(q, {"_id": 0}).sort("created_at", -1).to_list(500)
    return docs


@api.post("/admin/predictions/{pick_id}/settle")
async def admin_settle_pick(pick_id: str, payload: SettlePayload, _: dict = Depends(admin_required)):
    doc = await picks_col.find_one({"id": pick_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="not found")
    p = Pick(**doc)
    p.status = payload.result
    p.settled_at = datetime.now(timezone.utc).isoformat()
    await picks_col.update_one({"id": pick_id}, {"$set": p.model_dump()})
    return p


@api.get("/admin/rejected")
async def admin_rejected(date: Optional[str] = None, _: dict = Depends(admin_required)):
    q = {}
    if date:
        q["date"] = date
    docs = await rej_col.find(q, {"_id": 0}).sort("created_at", -1).to_list(200)
    return docs


# ------------------ Mount ------------------

app.include_router(api)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=False,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
