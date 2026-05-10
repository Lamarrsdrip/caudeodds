"""CLAUDEODD FastAPI server."""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from dotenv import load_dotenv
from fastapi import APIRouter, FastAPI, HTTPException
from motor.motor_asyncio import AsyncIOMotorClient
from starlette.middleware.cors import CORSMiddleware

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

from models import (  # noqa: E402
    GenerateResponse,
    Pick,
    RejectionLog,
    SettlePayload,
    Settings,
)
from pipeline import run_pipeline, today_str  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("claudeodd.server")

mongo_url = os.environ["MONGO_URL"]
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ["DB_NAME"]]

picks_col = db.claudeodd_picks
rej_col = db.claudeodd_rejections
settings_col = db.claudeodd_settings
runs_col = db.claudeodd_runs

app = FastAPI(title="CLAUDEODD")
api = APIRouter(prefix="/api")


# ---------------- Helpers ----------------

DEFAULT_SETTINGS = Settings()


async def get_settings() -> Settings:
    doc = await settings_col.find_one({"_id": "main"}, {"_id": 0})
    if not doc:
        return DEFAULT_SETTINGS
    return Settings(**doc)


async def save_settings(s: Settings) -> None:
    s.updated_at = datetime.now(timezone.utc).isoformat()
    await settings_col.update_one({"_id": "main"}, {"$set": s.model_dump()}, upsert=True)


# ---------------- Routes ----------------

@api.get("/")
async def root():
    return {"app": "CLAUDEODD", "status": "ok", "version": "1.0"}


@api.get("/config", response_model=Settings)
async def cfg_get():
    return await get_settings()


@api.post("/config", response_model=Settings)
async def cfg_set(payload: Settings):
    await save_settings(payload)
    return payload


@api.post("/picks/generate", response_model=GenerateResponse)
async def picks_generate(force: bool = False, date: Optional[str] = None):
    date_str = date or today_str()
    settings = await get_settings()

    # Idempotency: check cached run
    if not force:
        run = await runs_col.find_one({"_id": date_str}, {"_id": 0})
        if run:
            cached_picks_docs = await picks_col.find({"date": date_str}, {"_id": 0}).to_list(50)
            cached_picks = [Pick(**d) for d in cached_picks_docs]
            return GenerateResponse(
                date=date_str,
                picks=cached_picks,
                rejected_count=run.get("rejected_count", 0),
                fixtures_analyzed=run.get("fixtures_analyzed", 0),
                cached=True,
            )

    logger.info("Running pipeline for %s (force=%s)", date_str, force)
    picks, rejections, total = await run_pipeline(date_str, settings)

    # Wipe and re-insert today's picks if force
    if force:
        await picks_col.delete_many({"date": date_str})
        await rej_col.delete_many({"date": date_str})

    if picks:
        await picks_col.insert_many([p.model_dump() for p in picks])
    if rejections:
        await rej_col.insert_many([r.model_dump() for r in rejections])

    await runs_col.update_one(
        {"_id": date_str},
        {"$set": {
            "date": date_str,
            "rejected_count": len(rejections),
            "fixtures_analyzed": total,
            "completed_at": datetime.now(timezone.utc).isoformat(),
        }},
        upsert=True,
    )

    return GenerateResponse(
        date=date_str,
        picks=picks,
        rejected_count=len(rejections),
        fixtures_analyzed=total,
        cached=False,
    )


@api.get("/picks/today", response_model=List[Pick])
async def picks_today():
    date_str = today_str()
    docs = await picks_col.find({"date": date_str}, {"_id": 0}).to_list(50)
    return [Pick(**d) for d in docs]


@api.get("/picks/history", response_model=List[Pick])
async def picks_history(limit: int = 200, sport: Optional[str] = None,
                        status: Optional[str] = None):
    q: dict = {}
    if sport and sport != "all":
        q["sport"] = sport
    if status and status != "all":
        q["status"] = status
    docs = await picks_col.find(q, {"_id": 0}).sort("created_at", -1).to_list(limit)
    return [Pick(**d) for d in docs]


@api.post("/picks/{pick_id}/settle", response_model=Pick)
async def picks_settle(pick_id: str, payload: SettlePayload):
    doc = await picks_col.find_one({"id": pick_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="pick not found")
    p = Pick(**doc)
    p.status = payload.result
    p.settled_at = datetime.now(timezone.utc).isoformat()
    await picks_col.update_one({"id": pick_id}, {"$set": p.model_dump()})
    return p


@api.get("/picks/parlay")
async def picks_parlay():
    """Combined daily slip: multiplied odds + combined Kelly stake."""
    date_str = today_str()
    docs = await picks_col.find({"date": date_str}, {"_id": 0}).to_list(50)
    if not docs:
        return {"date": date_str, "legs": 0, "combined_odds": 1.0, "stake_pct": 0.0,
                "stake_units": 0.0, "expected_value": 0.0}
    settings = await get_settings()
    combined = 1.0
    prob = 1.0
    for d in docs:
        combined *= float(d["odds"])
        # back out fair_prob from quant view
        qv = d.get("quant_view") or {}
        prob *= float(qv.get("fair_prob", 1.0 / float(d["odds"])))
    ev = (prob * combined) - 1.0
    # use safest stake (smallest leg %) for parlay risk
    safest = min(float(d.get("kelly_stake_pct", 1.0)) for d in docs) * 0.5
    return {
        "date": date_str,
        "legs": len(docs),
        "combined_odds": round(combined, 2),
        "fair_prob": round(prob, 4),
        "expected_value": round(ev, 4),
        "stake_pct": round(safest, 2),
        "stake_units": round(safest / 100 * settings.bankroll, 2),
    }


@api.get("/analytics/roi")
async def analytics_roi():
    settings = await get_settings()
    docs = await picks_col.find({}, {"_id": 0}).sort("created_at", 1).to_list(2000)
    bankroll = settings.bankroll
    curve = []
    won = lost = pending = voided = 0
    total_staked = 0.0
    profit = 0.0
    for d in docs:
        stake = float(d.get("stake_units", 0))
        status = d.get("status", "pending")
        if status == "won":
            won += 1
            total_staked += stake
            pnl = stake * (float(d["odds"]) - 1)
            profit += pnl
            bankroll += pnl
        elif status == "lost":
            lost += 1
            total_staked += stake
            profit -= stake
            bankroll -= stake
        elif status == "void":
            voided += 1
        else:
            pending += 1
        curve.append({
            "t": d.get("settled_at") or d.get("created_at"),
            "bankroll": round(bankroll, 2),
            "match": d.get("match"),
            "status": status,
        })
    settled = won + lost
    win_rate = (won / settled * 100) if settled else 0.0
    roi_pct = (profit / total_staked * 100) if total_staked else 0.0
    return {
        "starting_bankroll": settings.bankroll,
        "current_bankroll": round(bankroll, 2),
        "profit": round(profit, 2),
        "total_staked": round(total_staked, 2),
        "won": won, "lost": lost, "pending": pending, "void": voided, "settled": settled,
        "win_rate": round(win_rate, 1),
        "roi_pct": round(roi_pct, 2),
        "curve": curve[-200:],
    }


@api.get("/analytics/rejected", response_model=List[RejectionLog])
async def analytics_rejected(limit: int = 100, date: Optional[str] = None):
    q = {}
    if date:
        q["date"] = date
    docs = await rej_col.find(q, {"_id": 0}).sort("created_at", -1).to_list(limit)
    return [RejectionLog(**d) for d in docs]


@api.get("/analytics/sharp")
async def analytics_sharp():
    """Live sharp money + line movement signals (synthesized from today's fixtures)."""
    from data_engine import generate_fixtures_for_date
    fixtures = generate_fixtures_for_date(today_str())
    signals = []
    for fx in fixtures[:14]:
        delta = fx.line_movement.get("delta_pct", 0)
        sharp_home = fx.sharp_money_pct.get("home", 50)
        public_home = fx.public_money_pct.get("home", 50)
        signals.append({
            "match": f"{fx.home} vs {fx.away}",
            "league": fx.league,
            "sport": fx.sport,
            "line_delta_pct": delta,
            "sharp_home_pct": sharp_home,
            "public_home_pct": public_home,
            "alert": (
                "SHARP_FADE_PUBLIC" if abs(sharp_home - public_home) > 25
                else "STEAM_MOVE" if abs(delta) > 6
                else "NEUTRAL"
            ),
        })
    signals.sort(key=lambda s: abs(s["line_delta_pct"]), reverse=True)
    return signals


# ---------------- App wiring ----------------

app.include_router(api)
app.add_middleware(
    CORSMiddleware,
    allow_credentials=False,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("shutdown")
async def shutdown():
    client.close()
