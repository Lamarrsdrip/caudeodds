"""API-Basketball enrichment service — sister product to API-Football, same vendor.

Endpoints used (https://api-sports.io/documentation/basketball/v1):
  /status                       — verify key + plan
  /teams?league=&season=        — discover team IDs (cached 7d)
  /games?team=&league=&season=&last=N — recent form (cached 12h)
  /games/h2h?h2h=A-B&last=N     — head-to-head (cached 24h)
  /standings?league=&season=    — season position (cached 24h)

NBA league_id = 12. EuroLeague = 120. Season format is "YYYY-YYYY" (e.g. "2025-2026").

Storage:
  db.apibasketball_team_map  {odds_team_name|league_name → team_id}
  db.apibasketball_cache     {key → {ts, payload}}
"""
from __future__ import annotations

import logging
import os
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional

import httpx
from rapidfuzz import fuzz

logger = logging.getLogger("claudeodd.apibasketball")

DEFAULT_BASE_URL = "https://v1.basketball.api-sports.io"
# Basketball seasons span Oct → June. 2025/26 = "2025-2026".
SEASON = os.environ.get("APIBASKETBALL_SEASON", "2025-2026")

LEAGUE_MAP = {
    "NBA": 12,
    "EuroLeague": 120,
}

_runtime: Dict[str, str] = {"key": "", "base_url": ""}


def set_runtime_config(apibasketball_key: str = "", apibasketball_base_url: str = "") -> None:
    if apibasketball_key is not None:
        _runtime["key"] = (apibasketball_key or "").strip()
    if apibasketball_base_url is not None:
        _runtime["base_url"] = (apibasketball_base_url or "").strip()


def _key() -> Optional[str]:
    k = (_runtime.get("key") or os.environ.get("APIBASKETBALL_KEY", "")).strip()
    return k or None


def _base() -> str:
    return (_runtime.get("base_url") or DEFAULT_BASE_URL).rstrip("/")


def is_configured() -> bool:
    return bool(_key())


class APIBasketballError(Exception):
    pass


async def _get(path: str, params: Optional[Dict] = None) -> Dict:
    k = _key()
    if not k:
        raise APIBasketballError("APIBASKETBALL_KEY not configured")
    headers = {"x-apisports-key": k}
    async with httpx.AsyncClient(timeout=15.0) as client:
        r = await client.get(f"{_base()}{path}", params=params or {}, headers=headers)
    if r.status_code == 429:
        raise APIBasketballError("API-Basketball daily quota exhausted (429)")
    if r.status_code >= 400:
        raise APIBasketballError(f"API-Basketball {r.status_code}: {r.text[:200]}")
    body = r.json() or {}
    if body.get("errors"):
        errs = body["errors"]
        if isinstance(errs, dict) and errs:
            raise APIBasketballError(f"API-Basketball plan/access error: {errs}")
        if isinstance(errs, list) and errs:
            raise APIBasketballError(f"API-Basketball errors: {errs}")
    return body


async def _cache_get(db, key: str, max_age_seconds: int) -> Optional[dict]:
    doc = await db.apibasketball_cache.find_one({"_id": key}, {"_id": 0})
    if not doc:
        return None
    age = time.time() - doc.get("ts", 0)
    if age > max_age_seconds:
        return None
    return doc.get("payload")


async def _cache_put(db, key: str, payload) -> None:
    await db.apibasketball_cache.update_one(
        {"_id": key}, {"$set": {"ts": time.time(), "payload": payload}}, upsert=True
    )


async def fetch_fixtures_for_league_date(db, league_name: str, date_str: str) -> List[Dict]:
    """Fetch ALL basketball games for a league on a date — schedule only.

    Cached 30 min so background syncs are cheap. Returns raw API-Basketball
    response items.
    """
    league_id = LEAGUE_MAP.get(league_name)
    if not league_id:
        return []
    cache_key = f"schedule_{league_id}_{date_str}"
    cached = await _cache_get(db, cache_key, max_age_seconds=30 * 60)
    if cached is not None:
        # Cache may have been put as raw list — handle both shapes for backwards compat.
        if isinstance(cached, list):
            return cached
        return cached.get("games", [])
    try:
        body = await _get("/games", params={
            "league": league_id, "season": SEASON, "date": date_str,
        })
    except APIBasketballError as e:
        logger.warning("fetch_fixtures_for_league_date(%s, %s) failed: %s",
                       league_name, date_str, e)
        return []
    games = body.get("response", []) or []
    await _cache_put(db, cache_key, {"games": games})
    return games


async def _all_teams_for_league(db, league_id: int) -> List[Dict]:
    cache_key = f"teams_{league_id}_{SEASON}"
    cached = await _cache_get(db, cache_key, max_age_seconds=7 * 24 * 3600)
    if cached:
        return cached
    try:
        body = await _get("/teams", params={"league": league_id, "season": SEASON})
    except APIBasketballError as e:
        logger.warning("Cannot fetch basketball teams for league %d %s: %s", league_id, SEASON, e)
        await _cache_put(db, cache_key, [])
        return []
    teams = body.get("response", []) or []
    await _cache_put(db, cache_key, teams)
    return teams


async def resolve_team_id(db, odds_team_name: str, league_name: str, threshold: int = 78) -> Optional[int]:
    league_id = LEAGUE_MAP.get(league_name)
    if not league_id:
        return None
    map_key = f"{odds_team_name}|{league_name}"
    cached = await db.apibasketball_team_map.find_one({"_id": map_key}, {"_id": 0})
    if cached:
        return cached.get("team_id")
    teams = await _all_teams_for_league(db, league_id)
    if not teams:
        return None
    target = odds_team_name.lower().strip()
    best_team, best_score = None, 0
    for t in teams:
        nm = (t.get("name") or "").lower()
        score = max(fuzz.token_set_ratio(target, nm), fuzz.partial_ratio(target, nm))
        if score > best_score:
            best_score, best_team = score, t
    if best_team and best_score >= threshold:
        await db.apibasketball_team_map.update_one(
            {"_id": map_key},
            {"$set": {"odds_team_name": odds_team_name, "league_name": league_name,
                      "league_id": league_id, "team_id": best_team["id"],
                      "team_name": best_team["name"], "fuzzy_score": best_score,
                      "resolved_at": datetime.now(timezone.utc).isoformat()}},
            upsert=True,
        )
        return best_team["id"]
    logger.warning("Could not resolve basketball team %r in %s (best=%s @ %d)",
                   odds_team_name, league_name, (best_team or {}).get("name"), best_score)
    return None


async def get_team_form(db, team_id: int, league_id: int, last_n: int = 5) -> Optional[Dict]:
    cache_key = f"form_{team_id}_{league_id}_{last_n}"
    cached = await _cache_get(db, cache_key, max_age_seconds=12 * 3600)
    if cached is not None:
        return cached
    try:
        body = await _get("/games", params={"team": team_id, "league": league_id,
                                            "season": SEASON, "last": last_n})
    except APIBasketballError as e:
        logger.warning("get_team_form (basketball) failed: %s", e)
        return None
    games = body.get("response", []) or []
    wins = losses = pts_for = pts_against = 0
    last_results: List[str] = []
    for g in games:
        teams = g.get("teams") or {}
        scores = g.get("scores") or {}
        is_home = (teams.get("home") or {}).get("id") == team_id
        my_pts = (scores.get("home") or {}).get("total") if is_home else (scores.get("away") or {}).get("total")
        their_pts = (scores.get("away") or {}).get("total") if is_home else (scores.get("home") or {}).get("total")
        if my_pts is None or their_pts is None:
            continue
        pts_for += int(my_pts); pts_against += int(their_pts)
        if my_pts > their_pts: wins += 1; last_results.append("W")
        else: losses += 1; last_results.append("L")
    n = max(wins + losses, 1)
    out = {
        "matches": wins + losses, "wins": wins, "losses": losses,
        "pts_for": pts_for, "pts_against": pts_against,
        "pts_diff": pts_for - pts_against,
        "win_pct": round(wins / n * 100, 1),
        "form_string": "".join(last_results) or "—",
    }
    await _cache_put(db, cache_key, out)
    return out


async def get_head_to_head(db, home_team_id: int, away_team_id: int, last_n: int = 5) -> Optional[Dict]:
    a, b = sorted([home_team_id, away_team_id])
    cache_key = f"h2h_{a}_{b}_{last_n}"
    cached = await _cache_get(db, cache_key, max_age_seconds=24 * 3600)
    if cached is not None:
        return cached
    try:
        body = await _get("/games/h2h", params={"h2h": f"{home_team_id}-{away_team_id}", "last": last_n})
    except APIBasketballError as e:
        logger.warning("get_head_to_head (basketball) failed: %s", e)
        return None
    games = body.get("response", []) or []
    home_wins = away_wins = 0
    for g in games:
        teams = g.get("teams") or {}
        scores = g.get("scores") or {}
        h_id = (teams.get("home") or {}).get("id")
        gh = (scores.get("home") or {}).get("total")
        ga = (scores.get("away") or {}).get("total")
        if gh is None or ga is None:
            continue
        if (gh > ga) and h_id == home_team_id: home_wins += 1
        elif (gh > ga) and h_id == away_team_id: away_wins += 1
        elif (ga > gh) and h_id == home_team_id: away_wins += 1
        elif (ga > gh) and h_id == away_team_id: home_wins += 1
    out = {"matches": home_wins + away_wins, "home_wins": home_wins, "away_wins": away_wins}
    await _cache_put(db, cache_key, out)
    return out


async def preflight_check() -> Dict:
    """Mirror of API-Football preflight: validates key + current-season access."""
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
        out["error"] = "No API key set. Paste the key in Admin → Configuration → API-Basketball."
        return out
    try:
        body = await _get("/status", params=None)
    except APIBasketballError as e:
        msg = str(e)
        if "suspended" in msg.lower():
            out["error"] = (
                "Your API-Basketball account is SUSPENDED. Log into "
                "https://dashboard.api-sports.io to see the reason "
                "(usually quota abuse on free tier). Often resolved by "
                "upgrading to Pro $19/mo or contacting their support."
            )
        elif "quota" in msg.lower() or "429" in msg:
            out["error"] = "Daily quota exhausted. Free tier = 100/day; resets midnight UTC."
        else:
            out["error"] = f"Key rejected by API-Basketball: {msg}"
        return out
    resp = body.get("response") or {}
    requests = resp.get("requests") or {}
    out["requests"] = requests.get("current")
    out["limit_day"] = requests.get("limit_day")
    # NBA teams check — confirms current-season access
    try:
        body = await _get("/teams", params={"league": 12, "season": SEASON})
        teams = body.get("response", []) or []
        if teams:
            out["current_season_supported"] = True
            out["sample_team"] = teams[0].get("name")
            out["ok"] = True
        else:
            out["error"] = f"API returned 0 NBA teams for season {SEASON} — double-check your plan."
    except APIBasketballError as e:
        msg = str(e)
        if "plan" in msg.lower() or "season" in msg.lower():
            out["error"] = (
                f"Your plan does NOT include season {SEASON}. "
                f"Free tier is restricted to past seasons only. "
                f"Upgrade to Pro $19/mo at api-basketball.com/pricing for live data."
            )
        else:
            out["error"] = f"Could not verify current season: {e}"
    return out


async def enrich_fixture(db, sport: str, league_name: str, home: str, away: str) -> Dict:
    """Returns {home_form, away_form, h2h, data_richness, configured}.

    Basketball doesn't expose injuries on api-basketball v1 (key gap vs football),
    so data_richness tops out at ~0.7 — still much better than price-only (0.0).
    """
    out = {
        "home_form": None, "away_form": None,
        "h2h": None,
        "data_richness": 0.0,
        "configured": is_configured(),
    }
    if sport != "basketball" or not is_configured():
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
    h2h = await get_head_to_head(db, home_id, away_id)
    richness = 0.0
    if home_form and home_form.get("matches", 0) >= 3:
        richness += 0.30
    if away_form and away_form.get("matches", 0) >= 3:
        richness += 0.30
    if h2h and h2h.get("matches", 0) >= 1:
        richness += 0.10
    out.update({
        "home_form": home_form, "away_form": away_form,
        "h2h": h2h,
        "data_richness": round(min(0.70, richness), 2),
    })
    return out
