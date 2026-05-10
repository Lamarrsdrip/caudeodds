"""Realistic fixture & market data simulator for CLAUDEODD.

Designed so it can be swapped with The Odds API / API-Football later — same
shape returned. Uses deterministic seed per UTC date so the same day always
gives the same fixtures (idempotent demo).
"""
from __future__ import annotations

import hashlib
import random
from datetime import datetime, timedelta, timezone
from typing import List

from models import Fixture


FOOTBALL_LEAGUES = {
    "Premier League": [
        "Arsenal", "Manchester City", "Liverpool", "Chelsea", "Tottenham",
        "Manchester United", "Newcastle", "Aston Villa", "Brighton", "West Ham",
    ],
    "La Liga": [
        "Real Madrid", "Barcelona", "Atletico Madrid", "Sevilla", "Real Sociedad",
        "Athletic Bilbao", "Villarreal", "Real Betis",
    ],
    "Serie A": [
        "Inter", "Juventus", "AC Milan", "Napoli", "Roma", "Lazio", "Atalanta", "Fiorentina",
    ],
    "Bundesliga": [
        "Bayern Munich", "Bayer Leverkusen", "Borussia Dortmund", "RB Leipzig",
        "Eintracht Frankfurt", "Stuttgart",
    ],
    "Ligue 1": [
        "PSG", "Marseille", "Monaco", "Lille", "Lyon", "Rennes",
    ],
}

BASKETBALL_LEAGUES = {
    "NBA": [
        "Boston Celtics", "Denver Nuggets", "Milwaukee Bucks", "LA Lakers",
        "Golden State Warriors", "Miami Heat", "Phoenix Suns", "Philadelphia 76ers",
        "Dallas Mavericks", "Oklahoma City Thunder", "New York Knicks", "Memphis Grizzlies",
    ],
    "EuroLeague": [
        "Real Madrid", "Olympiacos", "Panathinaikos", "Fenerbahce",
        "Barcelona", "Maccabi Tel Aviv", "Anadolu Efes",
    ],
}

REFEREE_TENDENCIES = ["high_cards", "lenient", "neutral", "penalty_friendly"]
WEATHERS = ["clear", "rain", "wind", "cold", "neutral"]


def seed_for_date(date_str: str) -> int:
    h = hashlib.sha256(date_str.encode()).hexdigest()
    return int(h[:8], 16)


def _football_odds(rng: random.Random, value_bias: bool = False) -> dict:
    home = round(rng.uniform(1.35, 3.80), 2)
    draw = round(rng.uniform(2.90, 4.20), 2)
    away = round(rng.uniform(1.55, 4.80), 2)
    over25 = round(rng.uniform(1.55, 2.30), 2)
    under25 = round(rng.uniform(1.55, 2.30), 2)
    btts_yes = round(rng.uniform(1.55, 2.10), 2)
    btts_no = round(rng.uniform(1.65, 2.20), 2)
    # Mispricing — gentle (8-22%) so favourite odds remain realistic
    if value_bias:
        target = rng.choice(["over", "under", "btts_yes", "btts_no", "home", "away"])
        boost = rng.uniform(1.08, 1.22)
        if target == "over": over25 = round(over25 * boost, 2)
        elif target == "under": under25 = round(under25 * boost, 2)
        elif target == "btts_yes": btts_yes = round(btts_yes * boost, 2)
        elif target == "btts_no": btts_no = round(btts_no * boost, 2)
        elif target == "home": home = round(home * boost, 2)
        elif target == "away": away = round(away * boost, 2)
    dc_1x = round(1 / (1 / home + 1 / draw) * rng.uniform(0.92, 0.97), 2)
    dc_x2 = round(1 / (1 / draw + 1 / away) * rng.uniform(0.92, 0.97), 2)
    dnb_home = round(home * rng.uniform(0.85, 0.93), 2)
    dnb_away = round(away * rng.uniform(0.85, 0.93), 2)
    return {
        "1X2": {"home": home, "draw": draw, "away": away},
        "DC": {"1X": dc_1x, "X2": dc_x2, "12": round(rng.uniform(1.18, 1.40), 2)},
        "DNB": {"home": dnb_home, "away": dnb_away},
        "OU_2_5": {"over": over25, "under": under25},
        "BTTS": {"yes": btts_yes, "no": btts_no},
        "AH_HOME_-0_5": round(rng.uniform(1.65, 2.20), 2),
        "AH_AWAY_+0_5": round(rng.uniform(1.55, 2.05), 2),
    }


def _basketball_odds(rng: random.Random, value_bias: bool = False) -> dict:
    ml_home = round(rng.uniform(1.30, 2.80), 2)
    ml_away = round(rng.uniform(1.30, 2.80), 2)
    spread = round(rng.uniform(2.5, 11.5) * 2) / 2
    spread_home = round(rng.uniform(1.85, 1.95), 2)
    spread_away = round(rng.uniform(1.85, 1.95), 2)
    total_pts = round(rng.uniform(205, 235) * 2) / 2
    over_total = round(rng.uniform(1.85, 1.95), 2)
    under_total = round(rng.uniform(1.85, 1.95), 2)
    if value_bias:
        target = rng.choice(["ml_home", "ml_away", "over", "under"])
        boost = rng.uniform(1.08, 1.20)
        if target == "ml_home": ml_home = round(ml_home * boost, 2)
        elif target == "ml_away": ml_away = round(ml_away * boost, 2)
        elif target == "over": over_total = round(over_total * boost, 2)
        elif target == "under": under_total = round(under_total * boost, 2)
    return {
        "ML": {"home": ml_home, "away": ml_away},
        "SPREAD": {"line": spread, "home": spread_home, "away": spread_away},
        "TOTAL": {"line": total_pts, "over": over_total, "under": under_total},
        "TEAM_TOTAL_HOME": {"line": round(total_pts / 2 + rng.uniform(-2, 2)),
                            "over": 1.91, "under": 1.91},
    }


def _form(rng: random.Random) -> List[str]:
    return [rng.choice(["W", "W", "D", "L"]) for _ in range(5)]


def _injuries(rng: random.Random, team: str) -> List[str]:
    if rng.random() < 0.55:
        return []
    pool = [
        f"{team} starting CB doubtful",
        f"{team} top scorer fitness test",
        f"{team} starting GK ruled out",
        f"{team} key midfielder suspended",
        f"{team} star wing late fitness call",
    ]
    return rng.sample(pool, k=rng.randint(1, 2))


def _make_match_features(rng: random.Random, sport: str) -> dict:
    home_open = round(rng.uniform(1.50, 3.20), 2)
    home_now = round(home_open * rng.uniform(0.88, 1.12), 2)
    delta = round((home_now - home_open) / home_open * 100, 1)
    sharp = rng.randint(35, 78)
    public = rng.randint(20, 80)
    return {
        "line_movement": {"home_open": home_open, "home_now": home_now, "delta_pct": delta},
        "sharp_money_pct": {"home": sharp, "away": 100 - sharp},
        "public_money_pct": {"home": public, "away": 100 - public},
        "liquidity_score": round(rng.uniform(0.35, 0.98), 2),
        "volatility": round(rng.uniform(0.10, 0.95), 2),
    }


def generate_fixtures_for_date(date_str: str, max_per_sport: int = 7) -> List[Fixture]:
    """Generate deterministic realistic fixtures for the given UTC date."""
    rng = random.Random(seed_for_date(date_str))
    fixtures: List[Fixture] = []

    base_dt = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc) + timedelta(hours=15)

    # Football
    leagues = list(FOOTBALL_LEAGUES.keys())
    for i in range(max_per_sport):
        league = rng.choice(leagues)
        teams_pool = FOOTBALL_LEAGUES[league]
        home, away = rng.sample(teams_pool, 2)
        feats = _make_match_features(rng, "football")
        kickoff = (base_dt + timedelta(hours=rng.randint(0, 8), minutes=rng.choice([0, 15, 30, 45]))).isoformat()
        value_bias = rng.random() < 0.35  # 35% mispriced (gentler boosts so favourites stay short)
        fixtures.append(Fixture(
            sport="football",
            league=league,
            home=home,
            away=away,
            kickoff=kickoff,
            odds=_football_odds(rng, value_bias),
            line_movement=feats["line_movement"],
            sharp_money_pct=feats["sharp_money_pct"],
            public_money_pct=feats["public_money_pct"],
            liquidity_score=feats["liquidity_score"],
            volatility=feats["volatility"],
            injuries=_injuries(rng, home) + _injuries(rng, away),
            xg={"home": round(rng.uniform(0.7, 2.4), 2), "away": round(rng.uniform(0.6, 2.2), 2)},
            home_form=_form(rng),
            away_form=_form(rng),
            referee_tendency=rng.choice(REFEREE_TENDENCIES),
            weather=rng.choice(WEATHERS),
            travel_fatigue={"home": rng.randint(0, 4), "away": rng.randint(0, 5)},
        ))

    # Basketball
    leagues = list(BASKETBALL_LEAGUES.keys())
    for i in range(max_per_sport):
        league = rng.choice(leagues)
        teams_pool = BASKETBALL_LEAGUES[league]
        home, away = rng.sample(teams_pool, 2)
        feats = _make_match_features(rng, "basketball")
        kickoff = (base_dt + timedelta(hours=rng.randint(0, 8), minutes=rng.choice([0, 30]))).isoformat()
        value_bias = rng.random() < 0.35
        fixtures.append(Fixture(
            sport="basketball",
            league=league,
            home=home,
            away=away,
            kickoff=kickoff,
            odds=_basketball_odds(rng, value_bias),
            line_movement=feats["line_movement"],
            sharp_money_pct=feats["sharp_money_pct"],
            public_money_pct=feats["public_money_pct"],
            liquidity_score=feats["liquidity_score"],
            volatility=feats["volatility"],
            injuries=_injuries(rng, home) + _injuries(rng, away),
            pace={"home": round(rng.uniform(95, 108), 1), "away": round(rng.uniform(95, 108), 1)},
            home_form=_form(rng),
            away_form=_form(rng),
            travel_fatigue={"home": rng.randint(0, 3), "away": rng.randint(0, 5)},
        ))

    return fixtures
