"""Fixture-First sync pipeline for ClaudeOdds.

Solves the "tomorrow's slip empty until bookmakers post odds" problem by
separating MATCH SCHEDULE from BETTING ODDS:

  1. SCHEDULE   — pulled early from API-Football / API-Basketball (1-2 weeks
                  in advance). Users see the slate immediately.
  2. ODDS       — pulled progressively from The Odds API as bookmakers post.
                  Schedule entries flip from `waiting` → `available` when
                  prices land.
  3. AI ANALYSIS — runs only on schedule entries that have odds. New picks
                  are inserted into the existing `claudeodd_picks` collection
                  so the slip_builder / slip_today logic is unchanged.

Background job (every 15 min) drives the loop:
    sync_schedule(today, tomorrow, +2)  →
        enrich_with_odds(date)         →
            run_ai_for_new_odds(date)  →
                upsert claudeodd_picks


Schedule document shape (db.claudeodd_schedule):
    {
      _id, id,                                   # uuid
      date: 'YYYY-MM-DD',
      sport: 'football'|'basketball',
      league, country, country_code,
      home, away, kickoff (ISO UTC),
      external_ids: {af_fixture_id, ab_game_id, odds_event_id},
      odds_status: 'waiting' | 'available',
      ai_status:   'pending' | 'analyzing' | 'ready' | 'rejected' | 'failed',
      pick_id:     <claudeodd_picks.id> | null,
      odds:        {...} | null,                 # only when odds_status=available
      first_seen_at, updated_at,
    }
"""
from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple

from rapidfuzz import fuzz

import apifootball_service as af
import apibasketball_service as ab
from consensus import evaluate
from data_engine import _enrich_one
from filters import filter_fixtures
from llm_engines import run_ensemble
from models import Fixture, Pick, Settings
from odds_api_service import (
    FOOTBALL_SPORT_KEYS,
    BASKETBALL_SPORT_KEYS,
    REGIONS,
    US_REGIONS,
    fetch_odds,
    _to_internal_fixture,
    TheOddsAPIError,
)

logger = logging.getLogger("claudeodd.fixture_sync")


SCHEDULE_COLLECTION = "claudeodd_schedule"


# ─────────────────────────────────────────────────────────────────────────────
# Schedule sourcing — pull early from API-Football / API-Basketball
# ─────────────────────────────────────────────────────────────────────────────


async def _af_fixtures_to_schedule(db, date_str: str) -> List[Dict]:
    """Pull football schedule from API-Football for ALL tracked leagues."""
    if not af.is_configured():
        return []
    out: List[Dict] = []
    for league_name in af.LEAGUE_MAP.keys():
        country, cc = _football_country_for_league(league_name)
        try:
            raw = await af.fetch_fixtures_for_league_date(db, league_name, date_str)
        except Exception as e:
            logger.warning("AF schedule fetch failed (%s, %s): %s", league_name, date_str, e)
            continue
        for fx in raw:
            try:
                fixture_meta = fx.get("fixture") or {}
                teams = fx.get("teams") or {}
                home = (teams.get("home") or {}).get("name") or ""
                away = (teams.get("away") or {}).get("name") or ""
                kickoff = fixture_meta.get("date") or ""
                if not (home and away and kickoff):
                    continue
                out.append({
                    "date": date_str,
                    "sport": "football",
                    "league": league_name,
                    "country": country,
                    "country_code": cc,
                    "home": home,
                    "away": away,
                    "kickoff": kickoff,
                    "external_ids": {
                        "af_fixture_id": fixture_meta.get("id"),
                    },
                })
            except Exception as e:
                logger.debug("AF schedule parse error: %s", e)
    return out


async def _ab_fixtures_to_schedule(db, date_str: str) -> List[Dict]:
    """Pull basketball schedule from API-Basketball for tracked leagues."""
    if not ab.is_configured():
        return []
    out: List[Dict] = []
    for league_name in ab.LEAGUE_MAP.keys():
        country, cc = _basketball_country_for_league(league_name)
        try:
            raw = await ab.fetch_fixtures_for_league_date(db, league_name, date_str)
        except Exception as e:
            logger.warning("AB schedule fetch failed (%s, %s): %s", league_name, date_str, e)
            continue
        for g in raw:
            try:
                teams = g.get("teams") or {}
                home = (teams.get("home") or {}).get("name") or ""
                away = (teams.get("away") or {}).get("name") or ""
                kickoff = g.get("date") or g.get("time") or ""
                if not (home and away and kickoff):
                    continue
                out.append({
                    "date": date_str,
                    "sport": "basketball",
                    "league": league_name,
                    "country": country,
                    "country_code": cc,
                    "home": home,
                    "away": away,
                    "kickoff": kickoff,
                    "external_ids": {
                        "ab_game_id": g.get("id"),
                    },
                })
            except Exception as e:
                logger.debug("AB schedule parse error: %s", e)
    return out


def _football_country_for_league(league: str) -> Tuple[str, str]:
    for (_skey, (lname, c, cc)) in FOOTBALL_SPORT_KEYS.items():
        if lname == league:
            return c, cc
    return "", ""


def _basketball_country_for_league(league: str) -> Tuple[str, str]:
    for (_skey, (lname, c, cc)) in BASKETBALL_SPORT_KEYS.items():
        if lname == league:
            return c, cc
    return "", ""


async def sync_schedule_for_date(db, date_str: str) -> Dict:
    """Pull tomorrow / today / day-after schedule from API-Football +
    API-Basketball and upsert into the schedule collection. Idempotent.

    Returns counts: {fetched, new, updated}.
    """
    af_rows = await _af_fixtures_to_schedule(db, date_str)
    ab_rows = await _ab_fixtures_to_schedule(db, date_str)
    rows = af_rows + ab_rows

    new = updated = 0
    now = datetime.now(timezone.utc).isoformat()
    for row in rows:
        # Stable matching key: (date, sport, league, home, away). Avoids creating
        # duplicate schedule entries on every sync.
        match_key = {
            "date": row["date"], "sport": row["sport"],
            "league": row["league"],
            "home": row["home"], "away": row["away"],
        }
        existing = await db[SCHEDULE_COLLECTION].find_one(match_key, {"_id": 0})
        if existing:
            await db[SCHEDULE_COLLECTION].update_one(match_key, {"$set": {
                "kickoff": row["kickoff"],
                "country": row["country"],
                "country_code": row["country_code"],
                "external_ids": {**(existing.get("external_ids") or {}), **(row["external_ids"] or {})},
                "updated_at": now,
            }})
            updated += 1
        else:
            doc = {
                **row,
                "id": str(uuid.uuid4()),
                "odds_status": "waiting",
                "ai_status": "pending",
                "pick_id": None,
                "odds": None,
                "first_seen_at": now,
                "updated_at": now,
            }
            await db[SCHEDULE_COLLECTION].insert_one(doc)
            new += 1

    return {"date": date_str, "fetched": len(rows), "new": new, "updated": updated}


# ─────────────────────────────────────────────────────────────────────────────
# Odds enrichment — match The Odds API events to schedule entries
# ─────────────────────────────────────────────────────────────────────────────


async def _fetch_odds_events_for_date(date_str: str) -> List[Dict]:
    """Pull odds events (football + basketball) whose commence date matches.

    Returns a list of internal-format fixture dicts ready for AI consumption.
    """
    target_day = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc).date()
    out: List[Dict] = []
    # Football
    for sport_key, (league, country, cc) in FOOTBALL_SPORT_KEYS.items():
        try:
            events = await fetch_odds(sport_key, regions=REGIONS, markets="h2h,totals")
        except TheOddsAPIError as e:
            logger.debug("Odds fetch skip %s: %s", sport_key, e)
            continue
        for ev in events:
            try:
                ct = datetime.fromisoformat(ev["commence_time"].replace("Z", "+00:00"))
            except Exception:
                continue
            if ct.date() != target_day:
                continue
            fx = _to_internal_fixture(ev, "football", league, country, cc)
            if fx:
                out.append(fx)
    # Basketball
    for sport_key, (league, country, cc) in BASKETBALL_SPORT_KEYS.items():
        regions = US_REGIONS if "nba" in sport_key else REGIONS
        try:
            events = await fetch_odds(sport_key, regions=regions, markets="h2h,totals")
        except TheOddsAPIError as e:
            logger.debug("Odds fetch skip %s: %s", sport_key, e)
            continue
        for ev in events:
            try:
                ct = datetime.fromisoformat(ev["commence_time"].replace("Z", "+00:00"))
            except Exception:
                continue
            if ct.date() != target_day:
                continue
            fx = _to_internal_fixture(ev, "basketball", league, country, cc)
            if fx:
                out.append(fx)
    return out


def _team_match(a: str, b: str, threshold: int = 75) -> bool:
    if not (a and b):
        return False
    score = max(
        fuzz.token_set_ratio(a.lower(), b.lower()),
        fuzz.partial_ratio(a.lower(), b.lower()),
    )
    return score >= threshold


async def enrich_with_odds(db, date_str: str) -> Dict:
    """Pull odds for the date and attach to matching schedule entries.

    Returns: {priced, still_waiting, no_match}.
    """
    odds_fixtures = await _fetch_odds_events_for_date(date_str)
    if not odds_fixtures:
        return {"date": date_str, "priced": 0, "still_waiting": 0, "no_match": 0,
                "message": "No odds available yet from The Odds API for this date."}

    schedule = await db[SCHEDULE_COLLECTION].find(
        {"date": date_str}, {"_id": 0}
    ).to_list(2000)

    priced = no_match = 0
    now = datetime.now(timezone.utc).isoformat()
    for ofx in odds_fixtures:
        sport = ofx.get("sport")
        league = ofx.get("league")
        home = ofx.get("home")
        away = ofx.get("away")
        # Look for a matching schedule entry (same sport, same league, fuzzy team match)
        target = None
        for s in schedule:
            if s.get("sport") != sport or s.get("league") != league:
                continue
            if s.get("odds_status") == "available":
                continue  # already priced
            if _team_match(s.get("home", ""), home) and _team_match(s.get("away", ""), away):
                target = s
                break
        if not target:
            no_match += 1
            continue

        await db[SCHEDULE_COLLECTION].update_one(
            {"id": target["id"]},
            {"$set": {
                "odds_status": "available",
                "odds": ofx,
                "external_ids": {**(target.get("external_ids") or {}),
                                 "odds_event_id": ofx.get("id")},
                "updated_at": now,
            }},
        )
        priced += 1

    still_waiting = sum(1 for s in schedule if s.get("odds_status") != "available") - priced
    still_waiting = max(0, still_waiting)
    return {"date": date_str, "priced": priced, "still_waiting": still_waiting,
            "no_match": no_match}


# ─────────────────────────────────────────────────────────────────────────────
# AI analysis — run ensemble on schedule entries that just got odds
# ─────────────────────────────────────────────────────────────────────────────


async def run_ai_for_new_odds(db, date_str: str, settings: Optional[Settings] = None) -> Dict:
    """For all schedule entries with odds_status='available' and
    ai_status='pending', run the AI ensemble and persist as a Pick.

    Reuses the same evaluate/consensus stack as the original pipeline so the
    EV calibration & hallucination guards are unchanged.
    """
    settings = settings or Settings()
    cursor = db[SCHEDULE_COLLECTION].find({
        "date": date_str,
        "odds_status": "available",
        "ai_status": "pending",
    }, {"_id": 0})
    targets = await cursor.to_list(200)
    if not targets:
        return {"date": date_str, "analyzed": 0, "rejected": 0, "ready": 0, "failed": 0}

    # Mark as analyzing up-front so a concurrent run won't double-process them.
    ids = [t["id"] for t in targets]
    await db[SCHEDULE_COLLECTION].update_many(
        {"id": {"$in": ids}}, {"$set": {"ai_status": "analyzing",
                                        "updated_at": datetime.now(timezone.utc).isoformat()}},
    )

    # Apply filter_fixtures + enrichment (same as run_pipeline) on the odds payloads
    fixtures = []
    sched_by_fx_id: Dict[str, Dict] = {}
    for t in targets:
        try:
            fx = Fixture(**t["odds"])
        except Exception as e:
            logger.warning("Schedule %s has malformed odds payload: %s", t["id"], e)
            await db[SCHEDULE_COLLECTION].update_one({"id": t["id"]}, {"$set": {
                "ai_status": "failed", "updated_at": datetime.now(timezone.utc).isoformat(),
            }})
            continue
        sched_by_fx_id[fx.id] = t
        fixtures.append(fx)

    kept, rejections = filter_fixtures(fixtures, date_str)
    rejected_fx_ids = {f.id for f in fixtures} - {f.id for f in kept}

    # Reject filtered-out fixtures at the schedule layer
    for fx_id in rejected_fx_ids:
        t = sched_by_fx_id.get(fx_id)
        if t:
            await db[SCHEDULE_COLLECTION].update_one({"id": t["id"]}, {"$set": {
                "ai_status": "rejected",
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }})

    # CRITICAL — enrich kept fixtures with API-Football intel (form, injuries,
    # h2h) so picks ship with realistic data_richness. Without this every
    # fixture_sync-produced pick fails the dashboard's data_richness gate.
    enrich_sem = asyncio.Semaphore(6)
    async def _enrich(fx):
        async with enrich_sem:
            try:
                return await _enrich_one(db, fx)
            except Exception as e:
                logger.warning("Enrichment failed for %s vs %s: %s", fx.home, fx.away, e)
                return fx
    kept = await asyncio.gather(*[_enrich(fx) for fx in kept])

    # Run ensemble concurrently (capped)
    sem = asyncio.Semaphore(8)
    async def _analyze(fx):
        async with sem:
            return fx, await run_ensemble(fx)
    results = await asyncio.gather(*[_analyze(f) for f in kept], return_exceptions=True)

    ready_count = rejected_count = failed_count = 0
    for res in results:
        if isinstance(res, Exception):
            failed_count += 1
            logger.warning("AI analyze threw: %s", res)
            continue
        fx, (q, r, research) = res
        sched = sched_by_fx_id.get(fx.id)
        if not sched:
            continue
        try:
            pick, rej = evaluate(fx, q, r, settings, date_str, research=research)
        except Exception as e:
            logger.exception("evaluate() failed for %s: %s", fx.id, e)
            await db[SCHEDULE_COLLECTION].update_one({"id": sched["id"]}, {"$set": {
                "ai_status": "failed",
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }})
            failed_count += 1
            continue

        if pick is not None:
            await db.claudeodd_picks.insert_one(pick.model_dump())
            await db[SCHEDULE_COLLECTION].update_one({"id": sched["id"]}, {"$set": {
                "ai_status": "ready",
                "pick_id": pick.id,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }})
            ready_count += 1
        else:
            if rej is not None:
                await db.claudeodd_rejections.insert_one(rej.model_dump())
            await db[SCHEDULE_COLLECTION].update_one({"id": sched["id"]}, {"$set": {
                "ai_status": "rejected",
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }})
            rejected_count += 1

    # Persist a 'runs' row so the existing /slip endpoints recognise this date.
    if ready_count or rejected_count or failed_count:
        await db.claudeodd_runs.update_one(
            {"_id": date_str},
            {"$set": {
                "date": date_str,
                "rejected_count": rejected_count,
                "fixtures_analyzed": len(kept),
                "completed_at": datetime.now(timezone.utc).isoformat(),
            }},
            upsert=True,
        )

    return {"date": date_str, "analyzed": len(kept),
            "ready": ready_count, "rejected": rejected_count,
            "failed": failed_count, "fixtures_analyzed": len(fixtures)}


# ─────────────────────────────────────────────────────────────────────────────
# Top-level driver
# ─────────────────────────────────────────────────────────────────────────────


async def run_full_cycle(db, dates: Optional[List[str]] = None) -> Dict:
    """One full sync → odds-enrich → AI cycle across the given dates.

    Default dates: today, tomorrow, day-after-tomorrow.
    """
    if not dates:
        today = datetime.now(timezone.utc).date()
        dates = [(today + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(0, 3)]

    out: Dict[str, Dict] = {}
    for d in dates:
        sched_stats = await sync_schedule_for_date(db, d)
        odds_stats = await enrich_with_odds(db, d)
        ai_stats = await run_ai_for_new_odds(db, d)
        out[d] = {"schedule": sched_stats, "odds": odds_stats, "ai": ai_stats}
    return out


# ─────────────────────────────────────────────────────────────────────────────
# Public read API
# ─────────────────────────────────────────────────────────────────────────────


async def get_upcoming_schedule(db, date_str: str) -> Dict:
    """Returns the schedule + status counts for a date, ready for the UI."""
    docs = await db[SCHEDULE_COLLECTION].find(
        {"date": date_str}, {"_id": 0}
    ).sort("kickoff", 1).to_list(500)

    summary = {"total": len(docs), "waiting_odds": 0, "ready": 0,
               "analyzing": 0, "rejected": 0, "failed": 0}
    fixtures = []
    for d in docs:
        odds_status = d.get("odds_status", "waiting")
        ai_status = d.get("ai_status", "pending")
        # Public status badge: simpler 3-state view
        if ai_status == "ready":
            badge = "ready"
            summary["ready"] += 1
        elif odds_status == "waiting":
            badge = "waiting"
            summary["waiting_odds"] += 1
        elif ai_status == "analyzing":
            badge = "analyzing"
            summary["analyzing"] += 1
        elif ai_status == "rejected":
            badge = "rejected"
            summary["rejected"] += 1
        elif ai_status == "failed":
            badge = "failed"
            summary["failed"] += 1
        else:
            badge = "analyzing"
            summary["analyzing"] += 1

        fixtures.append({
            "id": d.get("id"),
            "date": d.get("date"),
            "sport": d.get("sport"),
            "league": d.get("league"),
            "country": d.get("country"),
            "country_code": d.get("country_code"),
            "home": d.get("home"),
            "away": d.get("away"),
            "kickoff": d.get("kickoff"),
            "badge": badge,
            "odds_status": odds_status,
            "ai_status": ai_status,
            "has_pick": bool(d.get("pick_id")),
        })

    return {"date": date_str, "summary": summary, "fixtures": fixtures}
