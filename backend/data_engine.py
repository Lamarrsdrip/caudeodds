"""Real fixture & odds data sourcing for ClaudeOdds.

Pulls REAL upcoming fixtures with bookmaker odds from The Odds API, then
ENRICHES football fixtures with real injuries/form/H2H from API-Football
(if configured). The richer the data, the wider the AI is allowed to deviate
from book consensus — a key real-money safeguard.
"""
from __future__ import annotations

import asyncio
import logging
from typing import List, Optional

from apifootball_service import enrich_fixture, is_configured as af_configured
from models import Fixture
from odds_api_service import (
    TheOddsAPIError,
    fetch_real_fixtures_for_today,
)

logger = logging.getLogger("claudeodd.data_engine")

LEAGUE_COUNTRY = {
    "Premier League": ("England", "ENG"),
    "La Liga": ("Spain", "ESP"),
    "Serie A": ("Italy", "ITA"),
    "Bundesliga": ("Germany", "GER"),
    "Ligue 1": ("France", "FRA"),
    "Champions League": ("Europe", "UCL"),
    "Europa League": ("Europe", "UEL"),
    "NBA": ("USA", "USA"),
    "EuroLeague": ("Europe", "EUR"),
}


async def _enrich_one(db, fx: Fixture) -> Fixture:
    if fx.sport != "football" or db is None or not af_configured():
        return fx
    try:
        enrich = await enrich_fixture(db, fx.sport, fx.league, fx.home, fx.away)
    except Exception as e:
        logger.warning("Enrichment failed for %s vs %s: %s", fx.home, fx.away, e)
        return fx
    fx.af_home_form = enrich.get("home_form")
    fx.af_away_form = enrich.get("away_form")
    fx.af_home_injuries = enrich.get("home_injuries") or []
    fx.af_away_injuries = enrich.get("away_injuries") or []
    fx.af_h2h = enrich.get("h2h")
    fx.data_richness = enrich.get("data_richness", 0.0)
    return fx


async def _fetch_real_async(date_str: str, db=None) -> List[Fixture]:
    raw = await fetch_real_fixtures_for_today(date_str)
    out: List[Fixture] = []
    for d in raw:
        d.pop("_country", None)
        d.pop("_country_code", None)
        try:
            out.append(Fixture(**d))
        except Exception as e:
            logger.warning("Skipping malformed fixture: %s", e)
    # Enrich football fixtures with API-Football (best-effort, parallel)
    if db is not None and af_configured() and out:
        sem = asyncio.Semaphore(4)  # protect free-tier quota
        async def _run(fx):
            async with sem:
                return await _enrich_one(db, fx)
        out = await asyncio.gather(*[_run(fx) for fx in out])
    return list(out)


def generate_fixtures_for_date(date_str: str, max_per_sport: int = 7) -> List[Fixture]:
    """Sync wrapper kept for backwards compat — does NOT enrich (no db handle)."""
    try:
        return asyncio.run(_fetch_real_async(date_str, db=None))
    except RuntimeError:
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(_fetch_real_async(date_str, db=None))
        finally:
            loop.close()


async def generate_fixtures_for_date_async(date_str: str, db=None, max_per_sport: int = 7) -> List[Fixture]:
    """Preferred async API. Pass `db` to enable API-Football enrichment."""
    try:
        return await _fetch_real_async(date_str, db=db)
    except TheOddsAPIError as e:
        logger.error("Real odds fetch failed: %s", e)
        return []
