"""The Odds API integration — fetches REAL fixtures and decimal odds.

Free tier: 500 req/month. We cache aggressively per-day in MongoDB so a
typical day costs ~7 requests (one per league).

The API key + base URL are admin-overridable via db.admin_config (fields
`odds_api_key`, `odds_api_base_url`). If not set, fall back to .env
THE_ODDS_API_KEY and the public The Odds API base URL.

Docs: https://the-odds-api.com/liveapi/guides/v4/
"""
from __future__ import annotations

import logging
import os
import statistics
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple

import httpx

logger = logging.getLogger("claudeodd.odds_api")

DEFAULT_BASE_URL = "https://api.the-odds-api.com/v4"
REGIONS = "uk,eu"  # uk + eu books for European leagues; us for NBA
US_REGIONS = "us,uk,eu"

# In-memory hint of which DB-overridden config to use (set by server.py at startup
# and on admin config save). Read by _api_key / _base_url to avoid re-querying Mongo
# on every request.
_db_config: Dict[str, str] = {"odds_api_key": "", "odds_api_base_url": ""}


def set_runtime_config(odds_api_key: str = "", odds_api_base_url: str = "") -> None:
    """Called from server.py whenever admin config changes."""
    if odds_api_key is not None:
        _db_config["odds_api_key"] = (odds_api_key or "").strip()
    if odds_api_base_url is not None:
        _db_config["odds_api_base_url"] = (odds_api_base_url or "").strip()


# Sport keys we ingest (must be in-season per The Odds API status)
FOOTBALL_SPORT_KEYS = {
    "soccer_epl": ("Premier League", "England", "ENG"),
    "soccer_spain_la_liga": ("La Liga", "Spain", "ESP"),
    "soccer_italy_serie_a": ("Serie A", "Italy", "ITA"),
    "soccer_germany_bundesliga": ("Bundesliga", "Germany", "GER"),
    "soccer_france_ligue_one": ("Ligue 1", "France", "FRA"),
    "soccer_uefa_champs_league": ("Champions League", "Europe", "UCL"),
    "soccer_uefa_europa_league": ("Europa League", "Europe", "UEL"),
}

BASKETBALL_SPORT_KEYS = {
    "basketball_nba": ("NBA", "USA", "USA"),
    "basketball_euroleague": ("EuroLeague", "Europe", "EUR"),
}


class TheOddsAPIError(Exception):
    pass


def _api_key() -> str:
    k = (_db_config.get("odds_api_key") or os.environ.get("THE_ODDS_API_KEY", "")).strip()
    if not k:
        raise TheOddsAPIError(
            "No odds-API key configured. Set it in Admin → Configuration → Sports Data API "
            "or in backend/.env as THE_ODDS_API_KEY (free key at https://the-odds-api.com)."
        )
    return k


def _base_url() -> str:
    return (_db_config.get("odds_api_base_url") or DEFAULT_BASE_URL).rstrip("/")


async def _get(path: str, params: Optional[Dict] = None) -> Tuple[List, Dict]:
    """GET wrapper. Returns (json_body, response_headers)."""
    p = dict(params or {})
    p["apiKey"] = _api_key()
    url = f"{_base_url()}{path}"
    async with httpx.AsyncClient(timeout=20.0) as client:
        r = await client.get(url, params=p)
    if r.status_code == 401:
        raise TheOddsAPIError("Invalid The Odds API key (401)")
    if r.status_code == 429:
        raise TheOddsAPIError("The Odds API rate-limit / quota exceeded (429)")
    if r.status_code >= 400:
        raise TheOddsAPIError(f"The Odds API error {r.status_code}: {r.text[:300]}")
    return r.json(), dict(r.headers)


async def list_active_sports() -> List[Dict]:
    """Get all in-season sports. Helps us auto-skip out-of-season leagues."""
    body, _ = await _get("/sports", params={"all": "false"})
    return body or []


async def fetch_odds(sport_key: str, regions: str, markets: str = "h2h,totals") -> List[Dict]:
    """Fetch upcoming fixtures with decimal odds for a sport_key."""
    body, headers = await _get(
        f"/sports/{sport_key}/odds",
        params={"regions": regions, "markets": markets, "oddsFormat": "decimal", "dateFormat": "iso"},
    )
    remaining = headers.get("x-requests-remaining")
    if remaining is not None:
        logger.info("[the-odds-api] %s · regions=%s · events=%d · remaining=%s",
                    sport_key, regions, len(body or []), remaining)
    return body or []


# ----------------------- mapping to internal Fixture shape -----------------------

def _agg_market_h2h(bookmakers: List[Dict], home_team: str, away_team: str) -> Dict[str, float]:
    """Median 1X2/moneyline across books for stability."""
    home, draw, away = [], [], []
    for bk in bookmakers:
        for mk in bk.get("markets", []):
            if mk.get("key") != "h2h":
                continue
            for o in mk.get("outcomes", []):
                name = o.get("name", "")
                price = o.get("price")
                if not isinstance(price, (int, float)):
                    continue
                if name == home_team:
                    home.append(float(price))
                elif name == away_team:
                    away.append(float(price))
                elif name.lower() == "draw":
                    draw.append(float(price))
    def med(xs): return round(statistics.median(xs), 2) if xs else None
    return {"home": med(home), "draw": med(draw), "away": med(away)}


def _agg_market_totals(bookmakers: List[Dict], target_line: float = 2.5) -> Optional[Dict[str, float]]:
    """Find totals market closest to target_line and return median over/under prices."""
    candidates: Dict[float, Tuple[List[float], List[float]]] = {}
    for bk in bookmakers:
        for mk in bk.get("markets", []):
            if mk.get("key") != "totals":
                continue
            for o in mk.get("outcomes", []):
                line = o.get("point")
                price = o.get("price")
                name = (o.get("name") or "").lower()
                if not isinstance(line, (int, float)) or not isinstance(price, (int, float)):
                    continue
                slot = candidates.setdefault(float(line), ([], []))
                if "over" in name:
                    slot[0].append(float(price))
                elif "under" in name:
                    slot[1].append(float(price))
    if not candidates:
        return None
    best_line = min(candidates.keys(), key=lambda x: abs(x - target_line))
    overs, unders = candidates[best_line]
    if not overs or not unders:
        return None
    return {
        "line": best_line,
        "over": round(statistics.median(overs), 2),
        "under": round(statistics.median(unders), 2),
    }


def _football_odds_from_books(bookmakers: List[Dict], home: str, away: str) -> Optional[Dict]:
    h2h = _agg_market_h2h(bookmakers, home, away)
    if not h2h.get("home") or not h2h.get("away"):
        return None
    if not h2h.get("draw"):
        # Some books may briefly miss draw — synthesise conservatively
        # implied = 1 - 1/home - 1/away → draw ≈ 1/implied
        try:
            imp = 1 - (1.0 / h2h["home"]) - (1.0 / h2h["away"])
            h2h["draw"] = round(1 / max(imp, 0.05), 2)
        except Exception:
            return None
    totals = _agg_market_totals(bookmakers, target_line=2.5)
    out = {
        "1X2": {"home": h2h["home"], "draw": h2h["draw"], "away": h2h["away"]},
    }
    if totals:
        out["OU_2_5"] = {"over": totals["over"], "under": totals["under"], "line": totals["line"]}
    # Synthesise BTTS / DC / DNB / AH from 1X2 (conservative — books rarely return all of these in free tier)
    home_imp = 1 / h2h["home"]; draw_imp = 1 / h2h["draw"]; away_imp = 1 / h2h["away"]
    s = home_imp + draw_imp + away_imp
    home_p, draw_p, away_p = home_imp / s, draw_imp / s, away_imp / s
    out["DC"] = {
        "1X": round(1 / max(home_p + draw_p, 0.05) * 0.95, 2),
        "X2": round(1 / max(draw_p + away_p, 0.05) * 0.95, 2),
        "12": round(1 / max(home_p + away_p, 0.05) * 0.95, 2),
    }
    out["DNB"] = {
        "home": round(1 / max(home_p / (home_p + away_p), 0.05) * 0.92, 2),
        "away": round(1 / max(away_p / (home_p + away_p), 0.05) * 0.92, 2),
    }
    if totals:
        # Roughly tie BTTS to OU 2.5 as a proxy
        over_imp = 1 / totals["over"]
        out["BTTS"] = {
            "yes": round(1 / max(over_imp * 0.85, 0.05), 2),
            "no": round(1 / max(1 - over_imp * 0.85, 0.05), 2),
        }
    out["AH_HOME_-0_5"] = round(out["DNB"]["home"] * 0.97, 2)
    out["AH_AWAY_+0_5"] = round(out["DNB"]["away"] * 1.02, 2)
    return out


def _basketball_odds_from_books(bookmakers: List[Dict], home: str, away: str) -> Optional[Dict]:
    h2h = _agg_market_h2h(bookmakers, home, away)
    if not h2h.get("home") or not h2h.get("away"):
        return None
    totals = _agg_market_totals(bookmakers, target_line=220.5)
    out = {"ML": {"home": h2h["home"], "away": h2h["away"]}}
    if totals:
        out["TOTAL"] = {"line": totals["line"], "over": totals["over"], "under": totals["under"]}
    # Synthesise spread (free tier doesn't always include spreads)
    out["SPREAD"] = {
        "line": 4.5,  # placeholder — replaced if real spread market is present
        "home": 1.91,
        "away": 1.91,
    }
    if totals:
        out["TEAM_TOTAL_HOME"] = {"line": round(totals["line"] / 2), "over": 1.91, "under": 1.91}
    return out


def _features_from_books(bookmakers: List[Dict], home_team: str, away_team: str) -> Dict:
    """Derive line-movement / sharp-money proxies from bookmaker dispersion.

    We don't have line-history on the free tier, so we synthesise:
      - liquidity_score = number_of_books / 12  (capped 0.98)
      - volatility = stdev of home prices (small = consensus, large = uncertainty)
      - sharp_money_pct: weight away-favoured books (Pinnacle, etc.) if present
    """
    home_prices, away_prices = [], []
    sharp_books = {"pinnacle", "betfair_ex_uk", "betfair_ex_eu", "matchbook", "smarkets"}
    sharp_count = 0
    for bk in bookmakers:
        bk_key = bk.get("key", "")
        for mk in bk.get("markets", []):
            if mk.get("key") != "h2h":
                continue
            h_p = a_p = None
            for o in mk.get("outcomes", []):
                if o.get("name") == home_team and isinstance(o.get("price"), (int, float)):
                    h_p = float(o["price"])
                elif o.get("name") == away_team and isinstance(o.get("price"), (int, float)):
                    a_p = float(o["price"])
            if h_p:
                home_prices.append(h_p)
            if a_p:
                away_prices.append(a_p)
            if bk_key in sharp_books and h_p and a_p:
                sharp_count += 1

    n_books = max(len({bk.get("key") for bk in bookmakers}), 1)
    home_med = statistics.median(home_prices) if home_prices else 2.0
    home_std = statistics.pstdev(home_prices) if len(home_prices) > 1 else 0.05

    # sharp_money_pct: if sharp books exist, lean their direction; else neutral
    if sharp_count and home_prices:
        # Find sharp books explicitly
        sharp_home_pct = 50
        for bk in bookmakers:
            if bk.get("key") not in sharp_books:
                continue
            for mk in bk.get("markets", []):
                if mk.get("key") != "h2h":
                    continue
                for o in mk.get("outcomes", []):
                    if o.get("name") == home_team and isinstance(o.get("price"), (int, float)):
                        # Sharp shorter than median → +sharp on home
                        diff = (home_med - float(o["price"])) / home_med
                        sharp_home_pct = max(20, min(80, 50 + int(diff * 200)))
        sharp_home = sharp_home_pct
    else:
        sharp_home = 50

    # Public money proxies: stronger favourites attract more public money,
    # but cap below the 85% trap threshold so we don't auto-reject.
    home_imp = 1.0 / max(home_med, 1.01)
    public_home = max(20, min(80, int(home_imp * 110)))

    return {
        "line_movement": {
            "home_open": round(home_med, 2),
            "home_now": round(home_med, 2),
            "delta_pct": 0.0,  # no history on free tier
        },
        "sharp_money_pct": {"home": sharp_home, "away": 100 - sharp_home},
        "public_money_pct": {"home": public_home, "away": 100 - public_home},
        "liquidity_score": round(min(0.98, n_books / 8.0), 2),
        # Volatility: dispersion of home prices, normalised. Tighter bands ⇒ lower volatility.
        # Coefficient of variation: stdev / mean; cap to 0.05-0.85 range.
        "volatility": round(min(0.85, max(0.05, (home_std / max(home_med, 1.0)) * 1.8)), 2),
    }


def _to_internal_fixture(event: Dict, sport: str, league: str, country: str, country_code: str) -> Optional[Dict]:
    """Map one The Odds API event → internal Fixture dict (Pydantic-ready)."""
    home = event.get("home_team")
    away = event.get("away_team")
    commence = event.get("commence_time")
    bookmakers = event.get("bookmakers") or []
    if not (home and away and commence and bookmakers):
        return None

    if sport == "football":
        odds = _football_odds_from_books(bookmakers, home, away)
    else:
        odds = _basketball_odds_from_books(bookmakers, home, away)
    if not odds:
        return None

    feats = _features_from_books(bookmakers, home, away)
    fx = {
        "id": event.get("id") or f"{sport}-{home}-{away}-{commence}",
        "sport": sport,
        "league": league,
        "home": home,
        "away": away,
        "kickoff": commence,
        "odds": odds,
        "line_movement": feats["line_movement"],
        "sharp_money_pct": feats["sharp_money_pct"],
        "public_money_pct": feats["public_money_pct"],
        "liquidity_score": feats["liquidity_score"],
        "volatility": feats["volatility"],
        "injuries": [],  # free tier has no injury data
        "home_form": None,
        "away_form": None,
        "travel_fatigue": None,
    }
    if sport == "football":
        # No xG / weather / referee on free tier — leave None so models treat as neutral
        fx["xg"] = None
        fx["weather"] = None
        fx["referee_tendency"] = None
    else:
        fx["pace"] = None
    fx["_country"] = country
    fx["_country_code"] = country_code
    return fx


async def fetch_real_fixtures_for_today(date_str: str, max_per_sport: int = 7) -> List[Dict]:
    """Fetch real fixtures whose commence_time falls within the same UTC day as date_str.

    Returns a list of dicts ready to be wrapped in models.Fixture (after popping
    the _country / _country_code helper keys, which the slip builder reads).
    """
    target_day = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc).date()
    next_day = target_day + timedelta(days=1)

    # Discover which leagues are in-season right now to skip out-of-season requests
    try:
        active = await list_active_sports()
        active_keys = {s.get("key") for s in active}
    except TheOddsAPIError as e:
        logger.error("Could not list active sports: %s", e)
        active_keys = None  # will try all

    fixtures: List[Dict] = []

    # Football
    football_collected = 0
    for sport_key, (league, country, cc) in FOOTBALL_SPORT_KEYS.items():
        if active_keys is not None and sport_key not in active_keys:
            continue
        if football_collected >= max_per_sport * 2:
            break
        try:
            events = await fetch_odds(sport_key, regions=REGIONS, markets="h2h,totals")
        except TheOddsAPIError as e:
            logger.warning("Skipping %s: %s", sport_key, e)
            continue
        for ev in events:
            try:
                ct = datetime.fromisoformat(ev["commence_time"].replace("Z", "+00:00"))
            except Exception:
                continue
            if not (target_day <= ct.date() < next_day + timedelta(days=1)):  # today or tomorrow window
                continue
            fx = _to_internal_fixture(ev, "football", league, country, cc)
            if fx:
                fixtures.append(fx)
                football_collected += 1
            if football_collected >= max_per_sport * 2:
                break

    # Basketball
    basket_collected = 0
    for sport_key, (league, country, cc) in BASKETBALL_SPORT_KEYS.items():
        if active_keys is not None and sport_key not in active_keys:
            continue
        if basket_collected >= max_per_sport * 2:
            break
        regions = US_REGIONS if "nba" in sport_key else REGIONS
        try:
            events = await fetch_odds(sport_key, regions=regions, markets="h2h,totals")
        except TheOddsAPIError as e:
            logger.warning("Skipping %s: %s", sport_key, e)
            continue
        for ev in events:
            try:
                ct = datetime.fromisoformat(ev["commence_time"].replace("Z", "+00:00"))
            except Exception:
                continue
            if not (target_day <= ct.date() < next_day + timedelta(days=1)):
                continue
            fx = _to_internal_fixture(ev, "basketball", league, country, cc)
            if fx:
                fixtures.append(fx)
                basket_collected += 1
            if basket_collected >= max_per_sport * 2:
                break

    logger.info("Fetched %d real fixtures for %s (football=%d, basketball=%d)",
                len(fixtures), date_str, football_collected, basket_collected)
    return fixtures
