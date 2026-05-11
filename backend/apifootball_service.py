"""API-Football enrichment service — fetches REAL injuries, team form, head-to-head.

This is the data that actually moves win probability. Without it, our AI was
finding "edge" in noise (price-only sharp/public synthetic features).

Free tier: 100 req/day — careful budget. Pro tier ($19/mo): 7,500/day.

Storage:
  db.apifootball_team_map  — {odds_team_name, league_key, team_id, fuzzy_score}
  db.apifootball_cache     — {key, payload, created_at}  (12h TTL on form/H2H, 2h on injuries)

Admin can override the API key + base URL via /admin/config (apifootball_key,
apifootball_base_url). Falls back to APIFOOTBALL_KEY env var.
"""
from __future__ import annotations

import logging
import os
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

import httpx
from rapidfuzz import fuzz

logger = logging.getLogger("claudeodd.apifootball")

DEFAULT_BASE_URL = "https://v3.football.api-sports.io"
# 2025/26 European football season. Free tier only supports 2022-2024 — for
# live predictions you NEED the Pro plan ($19/mo) on the current season.
SEASON = int(os.environ.get("APIFOOTBALL_SEASON", "2025"))

# Maps Odds-API league display name → API-Football league_id (api-sports.io)
LEAGUE_MAP = {
    "Premier League": 39,        # England
    "La Liga": 140,              # Spain
    "Serie A": 135,              # Italy
    "Bundesliga": 78,            # Germany
    "Ligue 1": 61,               # France
    "Champions League": 2,       # UEFA
    "Europa League": 3,          # UEFA
}

_runtime: Dict[str, str] = {"key": "", "base_url": ""}


def set_runtime_config(apifootball_key: str = "", apifootball_base_url: str = "") -> None:
    if apifootball_key is not None:
        _runtime["key"] = (apifootball_key or "").strip()
    if apifootball_base_url is not None:
        _runtime["base_url"] = (apifootball_base_url or "").strip()


def _key() -> Optional[str]:
    k = (_runtime.get("key") or os.environ.get("APIFOOTBALL_KEY", "")).strip()
    return k or None


def _base() -> str:
    return (_runtime.get("base_url") or DEFAULT_BASE_URL).rstrip("/")


def is_configured() -> bool:
    return bool(_key())


# ---------- low-level HTTP ----------

class APIFootballError(Exception):
    pass


async def _get(path: str, params: Optional[Dict] = None) -> Dict:
    k = _key()
    if not k:
        raise APIFootballError("APIFOOTBALL_KEY not configured")
    headers = {"x-apisports-key": k}
    async with httpx.AsyncClient(timeout=15.0) as client:
        r = await client.get(f"{_base()}{path}", params=params or {}, headers=headers)
    if r.status_code == 429:
        raise APIFootballError("API-Football daily quota exhausted (429)")
    if r.status_code >= 400:
        raise APIFootballError(f"API-Football {r.status_code}: {r.text[:200]}")
    body = r.json() or {}
    if body.get("errors"):
        errs = body["errors"]
        if isinstance(errs, dict) and errs:
            # 'plan' / 'access' errors typically mean free-tier season restriction —
            # raise so the caller can decide to skip enrichment for this fixture
            # rather than crashing the whole pipeline.
            raise APIFootballError(f"API-Football plan/access error: {errs}")
        if isinstance(errs, list) and errs:
            raise APIFootballError(f"API-Football errors: {errs}")
    return body


# ---------- caching helpers ----------

async def _cache_get(db, key: str, max_age_seconds: int) -> Optional[dict]:
    doc = await db.apifootball_cache.find_one({"_id": key}, {"_id": 0})
    if not doc:
        return None
    age = time.time() - doc.get("ts", 0)
    if age > max_age_seconds:
        return None
    return doc.get("payload")


async def _cache_put(db, key: str, payload: dict) -> None:
    await db.apifootball_cache.update_one(
        {"_id": key}, {"$set": {"ts": time.time(), "payload": payload}}, upsert=True
    )


# ---------- team resolution ----------

async def _all_teams_for_league(db, league_id: int) -> List[Dict]:
    cache_key = f"teams_{league_id}_{SEASON}"
    cached = await _cache_get(db, cache_key, max_age_seconds=7 * 24 * 3600)
    if cached:
        return cached
    try:
        body = await _get("/teams", params={"league": league_id, "season": SEASON})
    except APIFootballError as e:
        logger.warning("Cannot fetch teams for league %d season %d: %s", league_id, SEASON, e)
        # Cache the empty result for 1h so we don't hammer the API on every fixture
        await _cache_put(db, cache_key, [])
        return []
    teams = [item.get("team") or {} for item in body.get("response", []) if item.get("team")]
    await _cache_put(db, cache_key, teams)
    return teams


async def resolve_team_id(db, odds_team_name: str, league_name: str, threshold: int = 78) -> Optional[int]:
    """Map an Odds API team name to an API-Football team_id, with fuzzy matching."""
    league_id = LEAGUE_MAP.get(league_name)
    if not league_id:
        return None

    map_key = f"{odds_team_name}|{league_name}"
    cached = await db.apifootball_team_map.find_one({"_id": map_key}, {"_id": 0})
    if cached:
        return cached.get("team_id")

    teams = await _all_teams_for_league(db, league_id)
    if not teams:
        return None

    target = odds_team_name.lower().strip()
    best_team = None
    best_score = 0
    for t in teams:
        nm = (t.get("name") or "").lower()
        score = max(fuzz.token_set_ratio(target, nm), fuzz.partial_ratio(target, nm))
        if score > best_score:
            best_score = score
            best_team = t

    if best_team and best_score >= threshold:
        await db.apifootball_team_map.update_one(
            {"_id": map_key},
            {"$set": {
                "odds_team_name": odds_team_name,
                "league_name": league_name,
                "league_id": league_id,
                "team_id": best_team["id"],
                "team_name": best_team["name"],
                "fuzzy_score": best_score,
                "resolved_at": datetime.now(timezone.utc).isoformat(),
            }}, upsert=True,
        )
        return best_team["id"]
    logger.warning("Could not resolve team %r in %s (best=%s @ %d)",
                   odds_team_name, league_name, (best_team or {}).get("name"), best_score)
    return None


# ---------- enrichment endpoints ----------

async def get_team_form(db, team_id: int, league_id: int, last_n: int = 5) -> Optional[Dict]:
    cache_key = f"form_{team_id}_{league_id}_{last_n}"
    cached = await _cache_get(db, cache_key, max_age_seconds=12 * 3600)
    if cached is not None:
        return cached
    try:
        body = await _get("/fixtures", params={"team": team_id, "league": league_id,
                                               "season": SEASON, "last": last_n})
    except APIFootballError as e:
        logger.warning("get_team_form failed: %s", e)
        return None
    fixtures = body.get("response", []) or []
    wins = draws = losses = gf = ga = 0
    last_results: List[str] = []  # 'W' / 'D' / 'L'
    for fx in fixtures:
        teams = fx.get("teams") or {}
        goals = fx.get("goals") or {}
        is_home = (teams.get("home") or {}).get("id") == team_id
        my_g = goals.get("home") if is_home else goals.get("away")
        their_g = goals.get("away") if is_home else goals.get("home")
        if my_g is None or their_g is None:
            continue
        gf += int(my_g); ga += int(their_g)
        if my_g > their_g: wins += 1; last_results.append("W")
        elif my_g == their_g: draws += 1; last_results.append("D")
        else: losses += 1; last_results.append("L")
    n = max(wins + draws + losses, 1)
    out = {
        "matches": wins + draws + losses,
        "wins": wins, "draws": draws, "losses": losses,
        "goals_for": gf, "goals_against": ga,
        "goal_diff": gf - ga,
        "ppg": round((wins * 3 + draws) / n, 2),
        "form_string": "".join(last_results) or "—",
    }
    await _cache_put(db, cache_key, out)
    return out


async def get_team_injuries(db, team_id: int, league_id: int) -> List[Dict]:
    cache_key = f"injuries_{team_id}_{league_id}"
    cached = await _cache_get(db, cache_key, max_age_seconds=2 * 3600)
    if cached is not None:
        return cached
    try:
        body = await _get("/injuries", params={"team": team_id, "league": league_id, "season": SEASON})
    except APIFootballError as e:
        logger.warning("get_team_injuries failed: %s", e)
        return []
    out: List[Dict] = []
    for item in body.get("response", []) or []:
        player = item.get("player") or {}
        out.append({
            "player": player.get("name") or "Unknown",
            "type": (player.get("type") or "").strip(),  # 'Missing Fixture' / 'Questionable'
            "reason": (player.get("reason") or "").strip(),
        })
    await _cache_put(db, cache_key, out)
    return out


async def get_head_to_head(db, home_team_id: int, away_team_id: int, last_n: int = 5) -> Optional[Dict]:
    a, b = sorted([home_team_id, away_team_id])  # cache symmetrically
    cache_key = f"h2h_{a}_{b}_{last_n}"
    cached = await _cache_get(db, cache_key, max_age_seconds=24 * 3600)
    if cached is not None:
        return cached
    try:
        body = await _get("/fixtures/headtohead",
                          params={"h2h": f"{home_team_id}-{away_team_id}", "last": last_n})
    except APIFootballError as e:
        logger.warning("get_head_to_head failed: %s", e)
        return None
    fixtures = body.get("response", []) or []
    home_wins = away_wins = draws = 0
    for fx in fixtures:
        goals = fx.get("goals") or {}
        teams = fx.get("teams") or {}
        h_id = (teams.get("home") or {}).get("id")
        gh = goals.get("home"); ga = goals.get("away")
        if gh is None or ga is None:
            continue
        if gh == ga:
            draws += 1
        elif (gh > ga) and h_id == home_team_id:
            home_wins += 1
        elif (gh > ga) and h_id == away_team_id:
            away_wins += 1
        elif (ga > gh) and h_id == home_team_id:
            away_wins += 1
        elif (ga > gh) and h_id == away_team_id:
            home_wins += 1
    out = {
        "matches": home_wins + away_wins + draws,
        "home_wins": home_wins, "away_wins": away_wins, "draws": draws,
    }
    await _cache_put(db, cache_key, out)
    return out


# ---------- top-level: enrich a fixture ----------

async def fetch_fixtures_for_league_date(db, league_name: str, date_str: str) -> List[Dict]:
    """Fetch ALL fixtures for a league on a given date — schedule only, no odds.

    Cached for 30 min so background syncs are cheap. Returns API-Football's raw
    fixture objects so the caller can extract teams/kickoff/league details.
    """
    league_id = LEAGUE_MAP.get(league_name)
    if not league_id:
        return []
    cache_key = f"schedule_{league_id}_{date_str}"
    cached = await _cache_get(db, cache_key, max_age_seconds=30 * 60)
    if cached is not None:
        return cached.get("fixtures", [])
    try:
        body = await _get("/fixtures", params={
            "league": league_id, "season": SEASON, "date": date_str,
        })
    except APIFootballError as e:
        logger.warning("fetch_fixtures_for_league_date(%s, %s) failed: %s",
                       league_name, date_str, e)
        return []
    fixtures = body.get("response", []) or []
    await _cache_put(db, cache_key, {"fixtures": fixtures})
    return fixtures


async def find_fixture_by_teams(db, league_name: str, home: str, away: str, date_str: str) -> Optional[Dict]:
    """Find a specific fixture (by team names + date) in API-Football.
    Returns the full /fixtures response item, or None.

    Cache key includes date so we re-fetch when matches roll over.
    """
    league_id = LEAGUE_MAP.get(league_name)
    if not league_id:
        return None
    home_id = await resolve_team_id(db, home, league_name)
    if not home_id:
        return None
    cache_key = f"fixture_{home_id}_{league_id}_{date_str}"
    cached = await _cache_get(db, cache_key, max_age_seconds=6 * 3600)
    if cached is not None:
        return cached
    try:
        body = await _get("/fixtures", params={
            "team": home_id, "league": league_id,
            "season": SEASON, "date": date_str,
        })
    except APIFootballError as e:
        logger.warning("find_fixture_by_teams failed: %s", e)
        return None
    fixtures = body.get("response", []) or []
    # Find the one matching the away team (fuzzy)
    target_away = away.lower().strip()
    best, best_score = None, 0
    for fx in fixtures:
        teams = fx.get("teams") or {}
        away_name = ((teams.get("away") or {}).get("name") or "").lower()
        score = max(fuzz.token_set_ratio(target_away, away_name), fuzz.partial_ratio(target_away, away_name))
        if score > best_score:
            best_score = score
            best = fx
    if best and best_score >= 70:
        await _cache_put(db, cache_key, best)
        return best
    return None


def settle_pick_result(market: str, fixture_result: Dict, home: str, away: str) -> Optional[str]:
    """Given a finished fixture and the market we bet on, return 'won' / 'lost' / 'void'.

    Returns None if the fixture isn't finished yet.
    """
    status = ((fixture_result.get("fixture") or {}).get("status") or {}).get("short", "")
    # API-Football status: FT (finished), AET (after extra time), PEN (penalties),
    # PST (postponed), CANC (cancelled), ABD (abandoned), NS (not started), LIVE
    if status in ("PST", "CANC", "ABD", "AWD", "WO"):
        return "void"
    if status not in ("FT", "AET", "PEN"):
        return None  # not finished
    goals = fixture_result.get("goals") or {}
    score = fixture_result.get("score") or {}
    # Use full-time score (regular time only) so DC/DNB/1X2 settle at FT
    ft = (score.get("fulltime") or {})
    home_g = ft.get("home") if ft.get("home") is not None else goals.get("home")
    away_g = ft.get("away") if ft.get("away") is not None else goals.get("away")
    if home_g is None or away_g is None:
        return None
    home_g = int(home_g); away_g = int(away_g)
    total = home_g + away_g
    m = market.upper()
    # 1X2
    if m == "1X2_HOME": return "won" if home_g > away_g else "lost"
    if m == "1X2_DRAW": return "won" if home_g == away_g else "lost"
    if m == "1X2_AWAY": return "won" if away_g > home_g else "lost"
    # Double Chance
    if m == "DC_1X": return "won" if home_g >= away_g else "lost"
    if m == "DC_X2": return "won" if away_g >= home_g else "lost"
    if m == "DC_12": return "won" if home_g != away_g else "lost"
    # Draw No Bet
    if m == "DNB_HOME":
        if home_g == away_g: return "void"
        return "won" if home_g > away_g else "lost"
    if m == "DNB_AWAY":
        if home_g == away_g: return "void"
        return "won" if away_g > home_g else "lost"
    # Over/Under 2.5
    if m == "OU_2_5_OVER": return "won" if total > 2.5 else "lost"
    if m == "OU_2_5_UNDER": return "won" if total < 2.5 else "lost"
    # BTTS
    if m == "BTTS_YES": return "won" if (home_g > 0 and away_g > 0) else "lost"
    if m == "BTTS_NO": return "won" if (home_g == 0 or away_g == 0) else "lost"
    # Asian Handicap (-0.5/+0.5 = same as DNB / 1X2 split)
    if m == "AH_HOME_-0.5": return "won" if home_g > away_g else "lost"
    if m == "AH_AWAY_+0.5": return "won" if away_g >= home_g else "lost"
    return None  # unknown market — leave pending


async def preflight_check() -> Dict:
    """Test API-Football connectivity + verify current-season access.

    Returns: {ok, plan_seasons_ok, current_season_supported, requests_remaining,
              key_configured, sample_team, error}
    """
    out = {
        "ok": False,
        "key_configured": is_configured(),
        "current_season": SEASON,
        "current_season_supported": False,
        "requests": None,
        "limit_day": None,
        "sample_team": None,
        "error": None,
    }
    if not is_configured():
        out["error"] = "No API key set. Paste the key in Admin → Configuration → API-Football."
        return out
    # Step 1: status — verifies key is valid & shows quota
    try:
        body = await _get("/status", params=None)
    except APIFootballError as e:
        msg = str(e)
        if "suspended" in msg.lower():
            out["error"] = (
                "Your API-Football account is SUSPENDED. Log into "
                "https://dashboard.api-football.com to see the reason "
                "(usually quota abuse on free tier). Often resolved by "
                "upgrading to Pro $19/mo or contacting their support."
            )
        elif "quota" in msg.lower() or "429" in msg:
            out["error"] = "Daily quota exhausted. Free tier = 100/day; resets midnight UTC."
        else:
            out["error"] = f"Key rejected by API-Football: {msg}"
        return out
    resp = body.get("response") or {}
    requests = resp.get("requests") or {}
    out["requests"] = requests.get("current")
    out["limit_day"] = requests.get("limit_day")
    # Step 2: try the current-season teams endpoint to confirm plan supports it
    try:
        body = await _get("/teams", params={"league": 39, "season": SEASON})
        teams = body.get("response", []) or []
        if teams:
            out["current_season_supported"] = True
            sample = (teams[0].get("team") or {}).get("name")
            out["sample_team"] = sample
            out["ok"] = True
        else:
            out["error"] = f"API returned 0 teams for Premier League season {SEASON} — unusual; double-check your plan."
    except APIFootballError as e:
        msg = str(e)
        if "plan" in msg.lower() or "season" in msg.lower():
            out["error"] = (
                f"Your plan does NOT include season {SEASON}. "
                f"This is the Free-tier restriction (it only allows 2022-2024). "
                f"Upgrade to Pro $19/mo at api-football.com/pricing to access live data."
            )
        else:
            out["error"] = f"Could not verify current season: {e}"
    return out


async def enrich_fixture(db, sport: str, league_name: str, home: str, away: str) -> Dict:
    """Returns {home_form, away_form, home_injuries, away_injuries, h2h, data_richness}.

    `data_richness` is a 0-1 score of how much real intel we have for this fixture.
    Used downstream to widen/tighten the AI's allowed probability shift.
    """
    out = {
        "home_form": None, "away_form": None,
        "home_injuries": [], "away_injuries": [],
        "h2h": None,
        "data_richness": 0.0,
        "configured": is_configured(),
    }
    if sport != "football" or not is_configured():
        return out
    league_id = LEAGUE_MAP.get(league_name)
    if not league_id:
        return out

    home_id = await resolve_team_id(db, home, league_name)
    away_id = await resolve_team_id(db, away, league_name)
    if not home_id or not away_id:
        return out

    home_form = await get_team_form(db, home_id, league_id)
    away_form = await get_team_form(db, away_id, league_id)
    home_inj = await get_team_injuries(db, home_id, league_id)
    away_inj = await get_team_injuries(db, away_id, league_id)
    h2h = await get_head_to_head(db, home_id, away_id)

    richness = 0.0
    if home_form and home_form.get("matches", 0) >= 3:
        richness += 0.30
    if away_form and away_form.get("matches", 0) >= 3:
        richness += 0.30
    if home_inj is not None and away_inj is not None:
        richness += 0.20
    if h2h and h2h.get("matches", 0) >= 2:
        richness += 0.20

    out.update({
        "home_form": home_form, "away_form": away_form,
        "home_injuries": home_inj, "away_injuries": away_inj,
        "h2h": h2h,
        "data_richness": round(min(1.0, richness), 2),
    })
    return out
