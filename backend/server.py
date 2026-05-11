"""Server: CLAUDEODD SaaS — auth, subscriptions, payments, admin, slips."""
from __future__ import annotations

import asyncio
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
from pipeline import run_pipeline, today_str, tomorrow_str  # noqa: E402
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
slip_codes_col = db.claudeodd_slip_codes  # admin-set SportyBet booking codes per date
jobs_col = db.claudeodd_jobs  # background pipeline job tracking

app = FastAPI(title="CLAUDEODD")
app.state.db = db


@app.on_event("startup")
async def on_startup():
    await users_col.create_index("email", unique=True)
    await users_col.create_index("id", unique=True)
    await pay_col.create_index("user_id")
    await pay_col.create_index("status")
    await picks_col.create_index("date")
    await picks_col.create_index([("date", -1), ("created_at", -1)])
    await rej_col.create_index("date")
    await db.push_subscriptions.create_index("endpoint", unique=True)
    await db.push_subscriptions.create_index("user_id")
    await seed_admin(db)
    # Reap any zombie pipeline jobs left from a previous restart so subsequent
    # Force Re-Generate calls aren't blocked by a permanently "running" row.
    reaped = await jobs_col.update_many(
        {"status": "running"},
        {"$set": {
            "status": "failed",
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "error": "interrupted by backend restart",
        }},
    )
    if reaped.modified_count:
        logger.info("Reaped %d zombie pipeline jobs from previous run", reaped.modified_count)
    # Sync admin config into runtime caches (odds API key/url) and start cron
    cfg = await admin_cfg_col.find_one({"_id": "main"}, {"_id": 0}) or {}
    from odds_api_service import set_runtime_config as set_odds_runtime
    from apifootball_service import set_runtime_config as set_af_runtime
    from apibasketball_service import set_runtime_config as set_ab_runtime
    set_odds_runtime(
        odds_api_key=cfg.get("odds_api_key", ""),
        odds_api_base_url=cfg.get("odds_api_base_url", ""),
    )
    set_af_runtime(
        apifootball_key=cfg.get("apifootball_key", ""),
        apifootball_base_url=cfg.get("apifootball_base_url", ""),
    )
    set_ab_runtime(
        apibasketball_key=cfg.get("apibasketball_key", ""),
        apibasketball_base_url=cfg.get("apibasketball_base_url", ""),
    )
    from scheduler import configure_scheduler
    sched_status = await configure_scheduler(db)
    logger.info("ClaudeOdds startup complete · scheduler=%s", sched_status)


@app.on_event("shutdown")
async def on_shutdown():
    from scheduler import shutdown as sched_shutdown
    sched_shutdown()
    client.close()


api = APIRouter(prefix="/api")


# ------------------ Health ------------------

@api.get("/")
async def root():
    return {"app": "ClaudeOdds", "status": "ok", "version": "2.1"}


@api.get("/public/config")
async def public_config():
    cfg = await admin_cfg_col.find_one({"_id": "main"}, {"_id": 0}) or {}
    from push_service import get_public_key
    try:
        vapid_public = await get_public_key(db)
    except Exception:
        vapid_public = ""
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
        "vapid_public_key": vapid_public,
        "push_enabled": cfg.get("push_enabled", True),
    }


@api.get("/public/roi")
async def public_roi(days: int = 30):
    """Public-facing ROI tracker. Aggregates settled slips over the last N days
    so visitors can see real, honest performance (no marketing fluff).

    Per-date slip outcome rules (1 unit flat stake per slip):
      • won  → all legs won (treat void legs as neutral; if all legs are void,
                slip is void)
      • lost → any leg lost
      • void → 100% of legs are void
      • pending → none of the above (still waiting on a leg)

    Profit per won slip = (combined_odds - 1) units.
    Loss per lost slip  = -1 unit.
    Void slips contribute 0 P/L.
    """
    from datetime import timedelta
    days = 30 if days is None else int(days)
    days = max(1, min(days, 365))
    end = datetime.now(timezone.utc).date()
    start = end - timedelta(days=days - 1)
    start_str, end_str = start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")

    docs = await picks_col.find(
        {"date": {"$gte": start_str, "$lte": end_str}},
        {"_id": 0},
    ).to_list(5000)

    cfg = await admin_cfg_col.find_one({"_id": "main"}, {"_id": 0}) or {}
    sb_url = cfg.get("sportybet_handle", "https://www.sportybet.com/ng/")
    code_docs = await slip_codes_col.find({}, {"_id": 1, "code": 1}).to_list(2000)
    code_by_date = {d["_id"]: d.get("code", "") for d in code_docs}

    by_date: dict = {}
    for d in docs:
        by_date.setdefault(d["date"], []).append(d)

    history: list = []
    won = lost = void = pending = 0
    profit = 0.0
    for date in sorted(by_date.keys(), reverse=True):
        picks_d = [Pick(**p) for p in by_date[date]]
        slip = build_slip(date, picks_d, sportybet_url=sb_url,
                          manual_code=code_by_date.get(date, ""))
        if not slip or not slip.legs:
            continue

        statuses = [p.status for p in picks_d]
        if any(s == "lost" for s in statuses):
            outcome = "lost"
        elif all(s == "void" for s in statuses):
            outcome = "void"
        elif all(s in ("won", "void") for s in statuses) and any(s == "won" for s in statuses):
            outcome = "won"
        else:
            outcome = "pending"

        if outcome == "won":
            won += 1
            profit += (slip.combined_odds - 1.0)
        elif outcome == "lost":
            lost += 1
            profit -= 1.0
        elif outcome == "void":
            void += 1
        else:
            pending += 1

        history.append({
            "date": date,
            "leg_count": slip.leg_count,
            "combined_odds": round(slip.combined_odds, 2),
            "outcome": outcome,
            "won_legs": sum(1 for s in statuses if s == "won"),
            "lost_legs": sum(1 for s in statuses if s == "lost"),
            "void_legs": sum(1 for s in statuses if s == "void"),
            "pending_legs": sum(1 for s in statuses if s == "pending"),
            "total_legs": len(statuses),
        })

    settled = won + lost + void
    roi_pct = (profit / settled * 100.0) if settled > 0 else 0.0
    win_rate = (won / settled * 100.0) if settled > 0 else 0.0

    return {
        "window_days": days,
        "from": start_str,
        "to": end_str,
        "totals": {
            "slips_settled": settled,
            "won": won,
            "lost": lost,
            "void": void,
            "pending": pending,
            "profit_units": round(profit, 2),
            "roi_pct": round(roi_pct, 1),
            "win_rate_pct": round(win_rate, 1),
        },
        "history": history[:60],
    }


# ------------------ Auth ------------------

@api.post("/auth/register", response_model=TokenResponse)
async def auth_register(payload: RegisterPayload):
    if not payload.age_18_plus:
        raise HTTPException(status_code=400, detail="You must be 18+ to use ClaudeOdds")
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

    # Fire-and-forget welcome email (does not block registration on SMTP outages).
    # We always invoke send_email even when SMTP is unconfigured so the attempt
    # is auditable in /api/admin/emails/logs (MISSING_CONFIG classification).
    async def _send_welcome():
        try:
            cfg_doc = await admin_cfg_col.find_one({"_id": "main"}, {"_id": 0}) or {}
            from email_service import send_email, template_welcome
            subject, html = template_welcome(payload.name.strip())
            await send_email(db, cfg_doc, email, subject, html, kind="welcome",
                             meta={"user_id": user_id})
        except Exception as e:
            logger.warning("Welcome email failed for %s: %s", email, e)
    asyncio.create_task(_send_welcome())

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
    ip = request.headers.get("x-forwarded-for", "").split(",")[0].strip() or request.client.host if request.client else ""
    ua = (request.headers.get("user-agent") or "")[:300]

    async def _log_activity(user_id, success, reason=None):
        try:
            await db.login_activity.insert_one({
                "id": str(uuid.uuid4()),
                "user_id": user_id,
                "email": email,
                "ip": ip,
                "ua": ua,
                "success": success,
                "reason": reason,
                "ts": datetime.now(timezone.utc).isoformat(),
            })
        except Exception as e:
            logger.debug("login_activity log failed: %s", e)

    if await is_locked(db, identifier):
        await _log_activity(None, False, "locked_out")
        raise HTTPException(status_code=429, detail="Too many failed attempts. Try again in 15 minutes.")

    user = await users_col.find_one({"email": email}, {"_id": 0})
    if not user or not verify_password(payload.password, user.get("password_hash", "")):
        await record_failure(db, identifier)
        await _log_activity(user.get("id") if user else None, False,
                            "bad_password" if user else "no_user")
        raise HTTPException(status_code=401, detail="Invalid email or password")

    await clear_failures(db, identifier)
    user = await refresh_status(db, user)
    pwv = int(user.get("password_version", 1) or 1)
    token = create_access_token(user["id"], email, user.get("role", "user"), password_version=pwv)
    await _log_activity(user["id"], True, None)
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


# ------------------ Password change + SMTP + activity log ------------------

@api.post("/auth/password/change")
async def auth_password_change(payload: dict, request: Request, user: dict = Depends(get_current_user_dep)):
    """Change the logged-in user's password. Bumps password_version which
    INVALIDATES every existing JWT for this user (force-logout other sessions).
    Sends a confirmation email if SMTP is configured.

    Body: { current_password, new_password }
    """
    current = (payload.get("current_password") or "")
    new_pw = (payload.get("new_password") or "")
    if len(new_pw) < 8 or len(new_pw) > 128:
        raise HTTPException(status_code=400, detail="New password must be 8-128 characters")
    if new_pw == current:
        raise HTTPException(status_code=400, detail="New password must differ from current")

    # Re-fetch with the hash since get_current_user_dep strips it
    full = await users_col.find_one({"id": user["id"]}, {"_id": 0})
    if not full or not verify_password(current, full.get("password_hash", "")):
        raise HTTPException(status_code=401, detail="Current password is incorrect")

    new_pwv = int(full.get("password_version", 1) or 1) + 1
    await users_col.update_one(
        {"id": user["id"]},
        {"$set": {
            "password_hash": hash_password(new_pw),
            "password_version": new_pwv,
            "password_changed_at": datetime.now(timezone.utc).isoformat(),
        }},
    )
    new_token = create_access_token(user["id"], user["email"], user.get("role", "user"), password_version=new_pwv)

    ip = request.headers.get("x-forwarded-for", "").split(",")[0].strip() or (request.client.host if request.client else "")
    # Fire-and-forget confirmation email
    async def _send_confirm():
        try:
            cfg_doc = await admin_cfg_col.find_one({"_id": "main"}, {"_id": 0}) or {}
            if not cfg_doc.get("smtp_host"):
                return
            from email_service import send_email, template_password_changed
            subject, html = template_password_changed(
                user.get("name", "there"),
                datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
                ip,
            )
            await send_email(db, cfg_doc, user["email"], subject, html,
                             kind="password_changed", meta={"user_id": user["id"]})
        except Exception as e:
            logger.warning("Password-changed email failed: %s", e)
    asyncio.create_task(_send_confirm())

    return {"ok": True, "access_token": new_token,
            "message": "Password updated. All other sessions have been signed out."}


@api.post("/admin/smtp/test")
async def admin_smtp_test(_: dict = Depends(admin_required)):
    """Verify SMTP connectivity without sending an email."""
    cfg_doc = await admin_cfg_col.find_one({"_id": "main"}, {"_id": 0}) or {}
    from email_service import test_smtp_connection
    return await test_smtp_connection(cfg_doc)


@api.post("/admin/smtp/send-test")
async def admin_smtp_send_test(payload: dict, admin: dict = Depends(admin_required)):
    """Send a test email to the supplied recipient (default: admin's own email)."""
    cfg_doc = await admin_cfg_col.find_one({"_id": "main"}, {"_id": 0}) or {}
    to = (payload.get("to") or admin["email"]).strip()
    from email_service import send_email, template_test
    subject, html = template_test()
    log = await send_email(db, cfg_doc, to, subject, html, kind="smtp_test",
                           meta={"triggered_by": admin["id"]})
    return log


@api.get("/admin/emails/logs")
async def admin_email_logs(limit: int = 100, _: dict = Depends(admin_required)):
    limit = max(1, min(int(limit or 100), 500))
    docs = await db.email_logs.find({}, {"_id": 0}).sort("sent_at", -1).to_list(limit)
    return docs


@api.get("/admin/activity")
async def admin_activity(user_id: Optional[str] = None, limit: int = 100,
                          _: dict = Depends(admin_required)):
    """Login activity log — both successes and failures, with ip/ua/timestamp."""
    limit = max(1, min(int(limit or 100), 500))
    q = {"user_id": user_id} if user_id else {}
    docs = await db.login_activity.find(q, {"_id": 0}).sort("ts", -1).to_list(limit)
    return docs


@api.get("/auth/activity")
async def my_activity(limit: int = 20, user: dict = Depends(get_current_user_dep)):
    """A user's own login history."""
    limit = max(1, min(int(limit or 20), 50))
    docs = await db.login_activity.find({"user_id": user["id"]}, {"_id": 0}).sort("ts", -1).to_list(limit)
    return docs


# ------------------ Daily Slip ------------------

# Schedule collection — fixture-first pipeline (separated from picks)
schedule_col = db.claudeodd_schedule


@api.get("/schedule/upcoming")
async def schedule_upcoming(date: Optional[str] = None, days: int = 3):
    """Public-facing fixture schedule. Shows ALL upcoming matches even before
    bookmakers publish odds — solves the 'empty dashboard until evening' UX
    problem. Each fixture carries a status badge:
       waiting   → match scheduled, odds not yet posted
       analyzing → odds available, AI is processing
       ready     → AI complete, pick exists (slip-eligible)
       rejected  → AI ran but rejected (no-bet / failed gates)

    Query params:
      date  — single YYYY-MM-DD (default: today). When set, `days` is ignored.
      days  — when no date, return next N days (max 7) starting today.
    """
    from fixture_sync_service import get_upcoming_schedule
    if date:
        try:
            datetime.strptime(date, "%Y-%m-%d")
        except ValueError:
            raise HTTPException(status_code=400, detail="date must be YYYY-MM-DD")
        return await get_upcoming_schedule(db, date)
    days_in = 3 if days is None else int(days)
    days_in = max(1, min(days_in, 7))
    from datetime import timedelta
    today = datetime.now(timezone.utc).date()
    out = []
    for i in range(days_in):
        d = (today + timedelta(days=i)).strftime("%Y-%m-%d")
        out.append(await get_upcoming_schedule(db, d))
    return {"days": days_in, "schedule": out}


@api.post("/admin/schedule/sync")
async def admin_schedule_sync(_: dict = Depends(admin_required)):
    """Trigger the fixture-first pipeline on demand (admin). Returns counts.
    Also self-heals legacy mistagged picks and orphan schedule entries."""
    from fixture_sync_service import run_full_cycle
    return await run_full_cycle(db)


@api.post("/admin/schedule/heal")
async def admin_schedule_heal(_: dict = Depends(admin_required)):
    """One-shot self-heal: drops mistagged picks (kickoff date != pick date)
    and resets orphan 'ready' schedule entries so the next cron regenerates
    the missing picks. Use this if you see today's picks vanishing or
    tomorrow's matches showing under today on /admin/predictions."""
    from fixture_sync_service import self_heal_bad_data
    from datetime import timedelta
    today = datetime.now(timezone.utc).date()
    dates = [(today + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(-1, 4)]
    return await self_heal_bad_data(db, dates)


async def _build_slip_for_date(date_str: str, cfg: dict):
    """Build the slip + quality gate result for a given date.

    Returns a tuple: (slip_or_none, awaiting_data_payload_or_none, has_picks_bool,
    all_settled_bool, latest_kickoff_iso_or_none).
    """
    docs = await picks_col.find({"date": date_str}, {"_id": 0}).to_list(50)
    has_picks = len(docs) > 0
    sb_url = cfg.get("sportybet_handle", "https://www.sportybet.com/ng/")
    code_doc = await slip_codes_col.find_one({"_id": date_str}, {"_id": 0}) or {}
    manual_code = code_doc.get("code", "")
    picks = [Pick(**d) for d in docs]
    slip = build_slip(date_str, picks, sportybet_url=sb_url, manual_code=manual_code)

    # Are all legs of today's picks settled? Helps decide whether to roll over.
    if picks:
        all_settled = all(p.status in ("won", "lost", "void") for p in picks)
    else:
        all_settled = False

    # Latest kickoff for "has the slate started/ended" detection.
    latest_kickoff = None
    for p in picks:
        if p.kickoff:
            if latest_kickoff is None or p.kickoff > latest_kickoff:
                latest_kickoff = p.kickoff

    if not slip:
        return None, None, has_picks, all_settled, latest_kickoff

    # SLIP-QUALITY GATE: average leg data_richness must clear admin threshold.
    avg_richness = sum((l.data_richness or 0) for l in slip.legs) / max(len(slip.legs), 1)
    min_richness = float(cfg.get("min_slip_data_richness", 0.4))
    if avg_richness < min_richness:
        return None, {
            "data_richness": round(avg_richness, 2),
            "min_required": min_richness,
            "message": (
                "Today's analysis is running on price-only data — no injury or "
                "form intel was available. We refuse to ship slips that aren't "
                "backed by real evidence. Come back later or check Admin → "
                "Configuration → API-Football pre-flight."
            ),
        }, has_picks, all_settled, latest_kickoff

    return slip, None, has_picks, all_settled, latest_kickoff


def _should_rollover(has_picks: bool, all_settled: bool, latest_kickoff: Optional[str]) -> bool:
    """Decide whether to surface tomorrow's slip instead of today's.

    Triggers (best of best — both):
    (a) All of today's picks are settled (won/lost/void) → slate is finished.
    (b) Current UTC time is past 22:00 UTC → late-night cutoff, look ahead.
    (c) Latest kickoff is in the past (every match has already started) and
        the slate is finished or no picks exist for today.
    """
    if has_picks and all_settled:
        return True
    now = datetime.now(timezone.utc)
    if now.hour >= 22:
        return True
    if has_picks and latest_kickoff:
        try:
            ko = datetime.fromisoformat(latest_kickoff.replace("Z", "+00:00"))
            if (now - ko).total_seconds() > 3 * 3600 and all_settled:
                return True
        except Exception:
            pass
    return False


@api.get("/slip/today")
async def slip_today(request: Request):
    """Public endpoint with locked teaser; full slip if user has access.

    Auto-rollover: when today's slate is finished (all settled) or it's past
    the late-night cutoff, surfaces tomorrow's slip if generated.
    """
    cfg = await admin_cfg_col.find_one({"_id": "main"}, {"_id": 0}) or {}
    today = today_str()
    tomorrow = tomorrow_str()

    today_slip, today_awaiting, today_has, today_settled, today_latest = \
        await _build_slip_for_date(today, cfg)

    rollover = _should_rollover(today_has, today_settled, today_latest)

    date_str = today
    slip = today_slip
    awaiting = today_awaiting
    is_tomorrow = False

    if rollover:
        tom_slip, _tom_awaiting, tom_has, _tom_settled, _tom_latest = \
            await _build_slip_for_date(tomorrow, cfg)
        if tom_slip:
            slip = tom_slip
            awaiting = None
            date_str = tomorrow
            is_tomorrow = True
        else:
            # Tomorrow not yet generated OR generated but insufficient picks to
            # build a 2.0-5.0 combined slip. Either way, show the rollover
            # awaiting state so the dashboard never appears empty at end of day.
            return {
                "date": tomorrow, "slip": None, "locked": True,
                "fixtures_analyzed": 0,
                "is_tomorrow": True,
                "awaiting_tomorrow": True,
                "message": (
                    "Today's slate is done. Tomorrow's slip will be generated "
                    "by the AI ensemble shortly — check back soon."
                ),
            }

    # Check user
    locked = True
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

    if awaiting:
        return {
            "date": date_str, "slip": None, "locked": locked,
            "fixtures_analyzed": 0,
            "is_tomorrow": is_tomorrow,
            "awaiting_data": True,
            "data_richness": awaiting["data_richness"],
            "min_required": awaiting["min_required"],
            "message": awaiting["message"],
        }

    if not slip:
        return {"date": date_str, "slip": None, "locked": locked,
                "fixtures_analyzed": 0, "is_tomorrow": is_tomorrow}

    # If locked, return a teaser (no leg details)
    if locked:
        teaser = slip.model_dump()
        teaser["legs"] = [{
            "match": "Locked", "league": leg.league, "country": leg.country,
            "country_code": leg.country_code, "sport": leg.sport,
            "market": "LOCKED", "selection_label": "Subscribe to unlock",
            "odds": leg.odds, "confidence": 0, "edge_pct": 0,
            "kickoff": leg.kickoff, "reasoning": "",
        } for leg in slip.legs]
        teaser["sportybet_code"] = ""
        teaser["summary"] = (
            f"{slip.leg_count}-leg slip ready. Subscribe to unlock the picks, the SportyBet booking code, "
            f"and the full AI ensemble reasoning."
        )
        teaser["locked"] = True
        return {"date": date_str, "slip": teaser, "locked": True, "is_tomorrow": is_tomorrow}

    return {"date": date_str, "slip": slip.model_dump(), "locked": False, "is_tomorrow": is_tomorrow}


# ------------------ Admin: SportyBet booking code per date ------------------

@api.get("/admin/slip/code")
async def admin_get_slip_code(date: Optional[str] = None, _: dict = Depends(admin_required)):
    d = date or today_str()
    doc = await slip_codes_col.find_one({"_id": d}, {"_id": 0}) or {}
    return {"date": d, "code": doc.get("code", ""), "updated_at": doc.get("updated_at")}


@api.post("/admin/slip/code")
async def admin_set_slip_code(payload: dict, _: dict = Depends(admin_required)):
    """Body: { code: 'STQLE2', date?: 'YYYY-MM-DD' }."""
    code = (payload.get("code") or "").strip().upper()
    d = (payload.get("date") or today_str()).strip()
    if code and not (3 <= len(code) <= 12 and code.isalnum()):
        raise HTTPException(status_code=400, detail="Booking code must be 3-12 alphanumeric chars")
    existing = await slip_codes_col.find_one({"_id": d}, {"_id": 0}) or {}
    await slip_codes_col.update_one(
        {"_id": d},
        {"$set": {"code": code, "updated_at": datetime.now(timezone.utc).isoformat()}},
        upsert=True,
    )
    # Broadcast push notification when admin publishes a new (non-empty) code for today
    if code and code != (existing.get("code") or "") and d == today_str():
        cfg = await admin_cfg_col.find_one({"_id": "main"}, {"_id": 0}) or {}
        if cfg.get("push_enabled", True):
            try:
                from push_service import broadcast
                # Fire and forget — don't block the admin response
                asyncio.create_task(broadcast(
                    db,
                    title="ClaudeOdds — Today's slip is live",
                    body=f"Booking code: {code}. Tap to view picks and copy to SportyBet.",
                    url="/dashboard",
                ))
            except Exception as e:
                logger.warning("Push broadcast failed: %s", e)
    return {"date": d, "code": code}


# ------------------ Push notifications (VAPID Web Push) ------------------

@api.post("/push/subscribe")
async def push_subscribe(payload: dict, request: Request, user: dict = Depends(get_current_user_dep)):
    """Body: { subscription: <browser PushSubscription.toJSON()> }"""
    sub = payload.get("subscription") or {}
    ua = request.headers.get("user-agent", "")
    from push_service import save_subscription
    try:
        await save_subscription(db, user_id=user["id"], subscription=sub, user_agent=ua)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"ok": True}


@api.post("/push/unsubscribe")
async def push_unsubscribe(payload: dict, _: dict = Depends(get_current_user_dep)):
    endpoint = (payload.get("endpoint") or "").strip()
    if not endpoint:
        raise HTTPException(status_code=400, detail="Missing endpoint")
    from push_service import remove_subscription
    deleted = await remove_subscription(db, endpoint)
    return {"ok": True, "deleted": deleted}


@api.post("/admin/push/test")
async def admin_push_test(payload: dict, _: dict = Depends(admin_required)):
    """Send a test push to verify the system end-to-end."""
    title = (payload.get("title") or "ClaudeOdds — Test Notification")[:120]
    body = (payload.get("body") or "If you see this, push notifications are working.")[:500]
    from push_service import broadcast
    res = await broadcast(db, title=title, body=body, url="/dashboard")
    return res


@api.get("/admin/apifootball/preflight")
async def admin_apifootball_preflight(_: dict = Depends(admin_required)):
    """Verify the API-Football key works for the CURRENT season before relying
    on it for live predictions. Returns a structured status the UI can render."""
    from apifootball_service import preflight_check
    return await preflight_check()


@api.get("/admin/apibasketball/preflight")
async def admin_apibasketball_preflight(_: dict = Depends(admin_required)):
    """Verify the API-Basketball key works for the CURRENT season."""
    from apibasketball_service import preflight_check
    return await preflight_check()


@api.post("/admin/settle/now")
async def admin_settle_now(_: dict = Depends(admin_required)):
    """Run auto-settlement sweep on demand. Returns settlement stats."""
    from settlement_service import settle_pending_picks
    return await settle_pending_picks(db)


@api.post("/slip/generate")
async def slip_generate(force: bool = False, date: Optional[str] = None, _: dict = Depends(admin_required)):
    """Admin-triggered generation. Returns immediately with a job_id; the actual
    AI ensemble runs in a background task to avoid Kubernetes ingress timeouts.

    `date` may be 'today' (default), 'tomorrow', or an explicit YYYY-MM-DD.
    """
    if not date or date == "today":
        date_str = today_str()
    elif date == "tomorrow":
        date_str = tomorrow_str()
    else:
        # Validate explicit ISO date
        try:
            datetime.strptime(date, "%Y-%m-%d")
            date_str = date
        except ValueError:
            raise HTTPException(status_code=400, detail="date must be YYYY-MM-DD, 'today', or 'tomorrow'")

    if not force:
        run = await runs_col.find_one({"_id": date_str}, {"_id": 0})
        if run:
            cached = await picks_col.find({"date": date_str}, {"_id": 0}).to_list(50)
            return {"date": date_str, "cached": True, "picks": len(cached),
                    "fixtures_analyzed": run.get("fixtures_analyzed", 0),
                    "rejected": run.get("rejected_count", 0),
                    "status": "completed", "job_id": None}

    # Reject if a job is already running for today — but treat any job
    # older than 10 minutes as zombie and let a new one start.
    existing_job = await jobs_col.find_one(
        {"date": date_str, "status": "running"}, {"_id": 0}
    )
    if existing_job:
        try:
            started = datetime.fromisoformat(existing_job["started_at"].replace("Z", "+00:00"))
            age_seconds = (datetime.now(timezone.utc) - started).total_seconds()
        except Exception:
            age_seconds = 0
        if age_seconds < 600:  # <10 min — genuinely running
            return {"date": date_str, "cached": False, "status": "running",
                    "job_id": existing_job["id"],
                    "message": f"Generation already in progress (started {int(age_seconds)}s ago)"}
        # Zombie — mark failed and continue
        await jobs_col.update_one({"id": existing_job["id"]}, {"$set": {
            "status": "failed",
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "error": f"timed out after {int(age_seconds)}s — superseded by new force-regen",
        }})
        logger.warning("Zombie job %s reaped (age %ds)", existing_job["id"], int(age_seconds))

    job_id = str(uuid.uuid4())
    await jobs_col.insert_one({
        "id": job_id,
        "date": date_str,
        "status": "running",
        "force": force,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "completed_at": None,
        "picks": 0,
        "rejected": 0,
        "fixtures_analyzed": 0,
        "error": None,
    })

    async def _runner():
        try:
            # On every (force) generate, also run a self-heal pass over the schedule so
            # legacy mistagged picks and orphan schedule entries are auto-fixed before
            # we try to build a new slip.
            try:
                from fixture_sync_service import self_heal_bad_data
                heal = await self_heal_bad_data(db, [date_str])
                if heal["mistagged_dropped"] or heal["orphans_reset"]:
                    logger.info("Self-heal on %s: dropped=%d orphans_reset=%d",
                                date_str, heal["mistagged_dropped"], heal["orphans_reset"])
            except Exception as e:
                logger.warning("Self-heal step failed (non-fatal): %s", e)

            settings_doc = await settings_col.find_one({"_id": "main"}, {"_id": 0})
            settings = Settings(**settings_doc) if settings_doc else Settings()
            picks, rejections, total = await run_pipeline(date_str, settings, db=db)
            # NON-DESTRUCTIVE force re-generate: only replace existing picks if the
            # new run produced at least one valid pick. Prevents the "force regenerate
            # wiped today's slip" UX bug when Odds API is rate-limited or returns 0.
            kept_old = False
            if force:
                if picks:
                    await picks_col.delete_many({"date": date_str})
                    await rej_col.delete_many({"date": date_str})
                else:
                    kept_old = True
                    logger.warning(
                        "Force re-generate for %s produced 0 picks — keeping existing slip intact",
                        date_str,
                    )
            if picks:
                await picks_col.insert_many([p.model_dump() for p in picks])
            if rejections:
                await rej_col.insert_many([r.model_dump() for r in rejections])
            await runs_col.update_one(
                {"_id": date_str},
                {"$set": {"date": date_str, "rejected_count": len(rejections),
                          "fixtures_analyzed": total,
                          "completed_at": datetime.now(timezone.utc).isoformat()}},
                upsert=True,
            )
            await jobs_col.update_one({"id": job_id}, {"$set": {
                "status": "completed",
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "picks": len(picks), "rejected": len(rejections),
                "fixtures_analyzed": total,
                "kept_old": kept_old,
            }})
            logger.info("Pipeline job %s complete: picks=%d rejected=%d fx=%d kept_old=%s", job_id, len(picks), len(rejections), total, kept_old)
        except Exception as e:
            logger.exception("Pipeline job %s failed: %s", job_id, e)
            await jobs_col.update_one({"id": job_id}, {"$set": {
                "status": "failed",
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "error": str(e)[:500],
            }})

    asyncio.create_task(_runner())
    return {"date": date_str, "cached": False, "status": "running", "job_id": job_id}


@api.get("/slip/generate/status/{job_id}")
async def slip_generate_status(job_id: str, _: dict = Depends(admin_required)):
    job = await jobs_col.find_one({"id": job_id}, {"_id": 0})
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


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
    code_docs = await slip_codes_col.find({}, {"_id": 1, "code": 1}).to_list(2000)
    code_by_date = {d["_id"]: d.get("code", "") for d in code_docs}
    out = []
    for date in sorted(by_date.keys(), reverse=True)[:limit]:
        picks = [Pick(**p) for p in by_date[date]]
        slip = build_slip(date, picks, sportybet_url=sb_url, manual_code=code_by_date.get(date, ""))
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
    if cfg.odds_api_key:
        cfg.odds_api_key = "****" + cfg.odds_api_key[-4:]
    if cfg.apifootball_key:
        cfg.apifootball_key = "****" + cfg.apifootball_key[-4:]
    if cfg.apibasketball_key:
        cfg.apibasketball_key = "****" + cfg.apibasketball_key[-4:]
    return cfg


@api.post("/admin/config", response_model=AdminConfig)
async def admin_set_config(cfg: AdminConfig, _: dict = Depends(admin_required)):
    cfg.updated_at = datetime.now(timezone.utc).isoformat()
    # Don't persist masked placeholders — re-load existing values for any field still masked
    existing = await admin_cfg_col.find_one({"_id": "main"}, {"_id": 0}) or {}
    payload = cfg.model_dump()
    for secret_field in ["flw_secret_key", "flw_encryption_key", "flw_webhook_secret", "smtp_password", "telegram_bot_token", "odds_api_key", "apifootball_key", "apibasketball_key"]:
        v = payload.get(secret_field, "")
        if v and (v.startswith("****") or v == "********"):
            payload[secret_field] = existing.get(secret_field, "")
    await admin_cfg_col.update_one({"_id": "main"}, {"$set": payload}, upsert=True)
    # Re-sync runtime config and reschedule cron
    from odds_api_service import set_runtime_config as set_odds_runtime
    from apifootball_service import set_runtime_config as set_af_runtime
    from apibasketball_service import set_runtime_config as set_ab_runtime
    set_odds_runtime(
        odds_api_key=payload.get("odds_api_key", ""),
        odds_api_base_url=payload.get("odds_api_base_url", ""),
    )
    set_af_runtime(
        apifootball_key=payload.get("apifootball_key", ""),
        apifootball_base_url=payload.get("apifootball_base_url", ""),
    )
    set_ab_runtime(
        apibasketball_key=payload.get("apibasketball_key", ""),
        apibasketball_base_url=payload.get("apibasketball_base_url", ""),
    )
    from scheduler import configure_scheduler
    await configure_scheduler(db)
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
