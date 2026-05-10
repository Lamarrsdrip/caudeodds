"""Real fixture & odds data sourcing for ClaudeOdds.

Pulls REAL upcoming fixtures with bookmaker odds from The Odds API. If the API
is unavailable / quota exhausted / no fixtures match today, returns an empty
list so the pipeline can produce no slip rather than a fake one.
"""
from __future__ import annotations

import asyncio
import logging
import os
from typing import List

from models import Fixture
from odds_api_service import (
    TheOddsAPIError,
    fetch_real_fixtures_for_today,
)

logger = logging.getLogger("claudeodd.data_engine")

# Country / code lookup mirrors odds_api_service mapping; kept here so slip_builder
# stays decoupled from the odds vendor.
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


async def _fetch_real_async(date_str: str) -> List[Fixture]:
    raw = await fetch_real_fixtures_for_today(date_str)
    out: List[Fixture] = []
    for d in raw:
        d.pop("_country", None)
        d.pop("_country_code", None)
        try:
            out.append(Fixture(**d))
        except Exception as e:  # malformed event — skip
            logger.warning("Skipping malformed fixture: %s", e)
    return out


def generate_fixtures_for_date(date_str: str, max_per_sport: int = 7) -> List[Fixture]:
    """Sync wrapper used by sync callers (kept for backwards compat)."""
    try:
        return asyncio.run(_fetch_real_async(date_str))
    except RuntimeError:
        # Already inside an event loop — caller should use the async variant
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(_fetch_real_async(date_str))
        finally:
            loop.close()


async def generate_fixtures_for_date_async(date_str: str, max_per_sport: int = 7) -> List[Fixture]:
    """Preferred async API for use inside FastAPI request handlers."""
    try:
        return await _fetch_real_async(date_str)
    except TheOddsAPIError as e:
        logger.error("Real odds fetch failed: %s", e)
        return []
