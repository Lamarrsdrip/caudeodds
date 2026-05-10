"""Post-match auto-settlement.

Finds picks past kickoff+3h that are still `pending`, fetches their final score
from API-Football, and marks them `won` / `lost` / `void`. Powers a real ROI
tracker for subscribers and removes manual settle work for admin.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta
from typing import Dict

from apifootball_service import (
    find_fixture_by_teams,
    is_configured,
    settle_pick_result,
)

logger = logging.getLogger("claudeodd.settler")


async def settle_pending_picks(db, max_age_days: int = 7) -> Dict:
    """Sweep for finished, unsettled picks and update them.

    Returns: {checked, settled, still_pending, skipped, errors}
    """
    if not is_configured():
        return {"checked": 0, "settled": 0, "still_pending": 0, "skipped": 0,
                "errors": ["API-Football not configured"]}

    now = datetime.now(timezone.utc)
    min_date = (now - timedelta(days=max_age_days)).strftime("%Y-%m-%d")

    # Find pending picks whose kickoff is at least 105 min ago (football ≈ 90+15)
    cursor = db.claudeodd_picks.find({
        "status": "pending",
        "sport": "football",
        "date": {"$gte": min_date},
    }, {"_id": 1, "id": 1, "match": 1, "league": 1, "market": 1,
         "kickoff": 1, "odds": 1, "date": 1})

    stats = {"checked": 0, "settled": 0, "still_pending": 0,
             "skipped": 0, "errors": [], "details": []}

    async for p in cursor:
        stats["checked"] += 1
        try:
            ko = datetime.fromisoformat(p["kickoff"].replace("Z", "+00:00"))
        except Exception:
            stats["skipped"] += 1
            continue
        if (now - ko).total_seconds() < 105 * 60:
            stats["still_pending"] += 1
            continue

        match = p.get("match", "")
        if " vs " not in match:
            stats["skipped"] += 1
            continue
        home, away = [s.strip() for s in match.split(" vs ", 1)]
        league = p.get("league")
        fixture_date = p.get("date")

        fixture = await find_fixture_by_teams(db, league, home, away, fixture_date)
        if not fixture:
            stats["skipped"] += 1
            stats["details"].append(f"{match}: no API-Football fixture found")
            continue

        result = settle_pick_result(p["market"], fixture, home, away)
        if result is None:
            stats["still_pending"] += 1
            continue

        await db.claudeodd_picks.update_one(
            {"_id": p["_id"]},
            {"$set": {
                "status": result,
                "settled_at": now.isoformat(),
            }},
        )
        stats["settled"] += 1
        stats["details"].append(f"{match} ({p['market']}): {result.upper()}")
        logger.info("Settled pick %s (%s): %s", match, p["market"], result)

    return stats
