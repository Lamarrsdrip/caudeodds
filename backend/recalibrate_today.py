"""One-off: re-calibrate today's picks already in MongoDB so the displayed
fair_prob, edge, EV, and confidence reflect realistic real-money values.

The new calibration logic in consensus.py is only applied at pipeline-run
time. This script reaches into existing DB rows for today and bounds the
LLM-derived fair_prob to within 7% of the bookmaker median.
"""
import asyncio
import os
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

load_dotenv(Path(__file__).resolve().parent / ".env")

MAX_PROB_SHIFT_BASE = 0.04
MAX_PROB_SHIFT_STRONG = 0.07


def calibrate_pick(pick: dict) -> dict:
    odds = pick.get("odds")
    if not odds or odds < 1.2:
        return pick
    book_implied = round(1.0 / odds, 4)
    qv = pick.get("quant_view") or {}
    raw_fair = float(qv.get("fair_prob", book_implied))
    direction = 1 if raw_fair > book_implied else -1

    # Strong-signal ceiling: we don't have fixture-level dispersion in the
    # stored Pick, so we take a conservative 4% cap on retroactive calibration.
    cap = MAX_PROB_SHIFT_BASE
    diverge = abs(raw_fair - book_implied)
    fair = book_implied + direction * min(diverge, cap)
    fair = round(max(0.02, min(0.98, fair)), 4)

    new_ev = round(fair * odds - 1.0, 4)
    new_edge = round((fair - book_implied) / book_implied * 100.0, 2)

    confidence_cap = 92.0
    if new_edge < 2.0:
        confidence_cap = min(confidence_cap, 80.0)
    if new_edge < 1.0:
        confidence_cap = min(confidence_cap, 75.0)
    new_conf = min(float(pick.get("confidence", 75.0)), confidence_cap)

    qv["fair_prob"] = fair
    qv["book_implied_prob"] = book_implied
    qv["expected_value"] = new_ev
    qv["edge_pct"] = new_edge
    qv["confidence"] = new_conf

    pick["confidence"] = new_conf
    pick["expected_value"] = new_ev
    pick["edge_pct"] = new_edge
    pick["quant_view"] = qv
    return pick


async def main():
    mongo = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = mongo[os.environ["DB_NAME"]]
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    picks = await db.claudeodd_picks.find({"date": today}).to_list(100)
    print(f"Recalibrating {len(picks)} picks for {today}...")
    for p in picks:
        before = (p.get("confidence"), p.get("edge_pct"), p.get("expected_value"))
        calibrate_pick(p)
        after = (p["confidence"], p["edge_pct"], p["expected_value"])
        await db.claudeodd_picks.update_one({"_id": p["_id"]}, {"$set": {
            "confidence": p["confidence"],
            "edge_pct": p["edge_pct"],
            "expected_value": p["expected_value"],
            "quant_view": p["quant_view"],
        }})
        print(f"  {p['match']:<55} {p['market']:<12} conf {before[0]}->{after[0]}  edge {before[1]}->{after[1]}  ev {before[2]}->{after[2]}")
    mongo.close()


if __name__ == "__main__":
    asyncio.run(main())
