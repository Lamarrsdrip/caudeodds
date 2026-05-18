"""ClaudeOdds combined slip builder.

Goal: combine only the strongest games such that the combined (multiplied)
decimal odds land in the user-friendly [2.0, 5.0] range. Cap at 5.0 odds.
Extra approved games are still exposed as optional categories so users can
extend their slip knowingly instead of the app forcing weak legs into the main
slip.

SportyBet booking codes can ONLY be issued by SportyBet itself when the slip is
manually built on their platform — no third-party can generate a working code.
We therefore leave the field empty by default; the admin pastes the real code
into the admin panel after building the slip on SportyBet.
"""
from __future__ import annotations

from typing import List

from saas_models import CombinedSlip, SlipLeg


TARGET_MIN_ODDS = 2.0
TARGET_MAX_ODDS = 5.0
MIN_LEGS = 3
MAX_LEGS = 5
HARD_MIN_LEGS = 2
OFFICIAL_POOL_LIMIT = 16
OPTIONAL_POOL_LIMIT = 40

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


def league_country(league: str) -> tuple[str, str]:
    return LEAGUE_COUNTRY.get(league, ("Intl", "INT"))


def _pick_quality(p) -> float:
    return (
        float(p.confidence) * 0.45
        + float(p.agreement) * 0.20
        + max(float(p.expected_value), 0.0) * 100.0 * 0.25
        + float(getattr(p, "data_richness", 0.0) or 0.0) * 10.0
    )


def _select_picks(picks: List) -> List:
    """Pick the official slip without forcing five legs.

    We rank candidate combinations by weakest-leg quality, average confidence,
    calibrated EV, data richness, and directional diversity. Leg count gets only
    a small preference, because a forced 5-leg accumulator can lose often even
    when every single pick is decent.
    """
    from itertools import combinations
    if not picks:
        return []

    ranked = sorted(picks, key=_pick_quality, reverse=True)
    pool = ranked[:OFFICIAL_POOL_LIMIT]

    def combo_score(combo) -> float:
        combined_odds = 1.0
        combined_fp = 1.0
        away_count = home_count = 0
        richness_sum = 0.0
        for p in combo:
            combined_odds *= float(p.odds)
            richness_sum += float(getattr(p, "data_richness", 0.0) or 0.0)
            try:
                combined_fp *= float(p.quant_view.fair_prob)
            except Exception:
                combined_fp *= 1.0 / float(p.odds)
            mk = p.market.upper()
            if "AWAY" in mk or mk in ("DC_X2", "ML_AWAY", "SPREAD_AWAY"):
                away_count += 1
            elif "HOME" in mk or mk in ("DC_1X", "ML_HOME", "SPREAD_HOME"):
                home_count += 1
        if combined_odds < TARGET_MIN_ODDS or combined_odds > TARGET_MAX_ODDS:
            return -1
        if len(combo) >= 3 and (away_count == len(combo) or home_count == len(combo)):
            return -0.5
        ev = combined_fp * combined_odds - 1.0
        min_conf = min(p.confidence for p in combo)
        avg_conf = sum(p.confidence for p in combo) / len(combo)
        min_ev = min(p.expected_value for p in combo)
        avg_richness = richness_sum / len(combo)
        leg_bonus = max(0, len(combo) - 1) * 4.0
        return (
            min_conf * 0.38
            + avg_conf * 0.22
            + min_ev * 100.0 * 0.16
            + ev * 100.0 * 0.12
            + avg_richness * 12.0
            + leg_bonus
        )

    best_combo = None
    best_score = -1.0
    for n in (2, 3, 4, 5):
        if len(pool) < n:
            continue
        for combo in combinations(pool, min(n, len(pool))):
            s = combo_score(list(combo))
            if s > best_score:
                best_score = s
                best_combo = list(combo)
    if best_combo and best_score > 0:
        return best_combo

    return [max(picks, key=lambda p: p.confidence)]


def _category_for_pick(p) -> str:
    richness = float(getattr(p, "data_richness", 0.0) or 0.0)
    if p.confidence >= 80 and p.expected_value >= 0.05 and richness >= 0.65:
        return "Elite"
    if p.confidence >= 74 and p.expected_value >= 0.04 and richness >= 0.50:
        return "Strong"
    if p.expected_value >= 0.055 and p.confidence >= 68:
        return "Value"
    if p.odds <= 1.55 and p.confidence >= 72:
        return "Safer Singles"
    return "Leans"


def _optional_pick_dict(p, official_ids: set[str]) -> dict:
    try:
        fp = float(p.quant_view.fair_prob)
    except Exception:
        fp = 1.0 / float(p.odds)
    return {
        "id": p.id,
        "date": p.date,
        "match": p.match,
        "league": p.league,
        "sport": p.sport,
        "kickoff": p.kickoff,
        "market": p.market,
        "selection_label": p.selection_label,
        "odds": p.odds,
        "confidence": p.confidence,
        "edge_pct": p.edge_pct,
        "expected_value": p.expected_value,
        "book_implied_prob": round(1.0 / float(p.odds), 4),
        "model_probability": round(fp, 4),
        "risk_level": p.risk_level,
        "data_richness": getattr(p, "data_richness", 0.0) or 0.0,
        "category": _category_for_pick(p),
        "in_main_slip": p.id in official_ids,
        "reasoning": (p.reasoning or "")[:220],
        "status": getattr(p, "status", "pending"),
    }


def _build_optional_categories(all_picks: List, selected: List) -> List[dict]:
    official_ids = {p.id for p in selected}
    ordered = sorted(all_picks, key=_pick_quality, reverse=True)[:OPTIONAL_POOL_LIMIT]
    buckets = {
        "Elite": [],
        "Strong": [],
        "Value": [],
        "Safer Singles": [],
        "Leans": [],
    }
    for p in ordered:
        item = _optional_pick_dict(p, official_ids)
        buckets[item["category"]].append(item)
    descriptions = {
        "Elite": "Best data quality, strongest calibrated edge, and highest model agreement.",
        "Strong": "Good confirmed picks that narrowly missed or support the main slip.",
        "Value": "Higher expected value, but more variance than the official slip.",
        "Safer Singles": "Lower odds with cleaner probability profile for users who prefer singles.",
        "Leans": "Approved but weaker than the official slip; use carefully.",
    }
    return [
        {"name": name, "description": descriptions[name], "picks": picks}
        for name, picks in buckets.items()
        if picks
    ]


def _filter_picks_to_date(picks: List, date_str: str) -> List:
    """Hard date-scope guard: only keep picks whose kickoff UTC-date matches
    the slip's date. Defensive against legacy DB rows where a pick may have
    been written with the wrong date (e.g. before the strict date-window fix).
    """
    from datetime import datetime
    out = []
    for p in picks:
        try:
            ko = p.kickoff or ""
            if not ko:
                # No kickoff metadata — fall through (don't drop).
                out.append(p)
                continue
            kd = datetime.fromisoformat(ko.replace("Z", "+00:00")).date().isoformat()
            if kd == date_str:
                out.append(p)
        except Exception:
            out.append(p)  # parse failure → keep, don't lose a valid pick
    return out


def build_slip(date_str: str, all_picks: List, sportybet_url: str = "https://www.sportybet.com/ng/", manual_code: str = "") -> CombinedSlip | None:
    if not all_picks:
        return None
    all_picks = _filter_picks_to_date(all_picks, date_str)
    if not all_picks:
        return None
    picks = _select_picks(all_picks)
    if not picks:
        return None

    legs: List[SlipLeg] = []
    combined_odds = 1.0
    fair_prob = 1.0
    confidence_avg = 0.0

    for p in picks:
        country, country_code = league_country(p.league)
        try:
            fp = float(p.quant_view.fair_prob)
        except Exception:
            fp = 1.0 / float(p.odds)
        leg_ev = round(fp * float(p.odds) - 1.0, 4)
        book_imp = round(1.0 / float(p.odds), 4)
        legs.append(SlipLeg(
            match=p.match, league=p.league, country=country, country_code=country_code,
            sport=p.sport, market=p.market, selection_label=p.selection_label,
            odds=p.odds, confidence=p.confidence, edge_pct=p.edge_pct,
            expected_value=leg_ev, book_implied_prob=book_imp,
            data_richness=getattr(p, "data_richness", 0.0) or 0.0,
            kickoff=p.kickoff, reasoning=(p.reasoning or "")[:240],
        ))
        combined_odds *= float(p.odds)
        fair_prob *= fp
        confidence_avg += p.confidence

    confidence_avg = confidence_avg / len(picks)
    expected_value = (fair_prob * combined_odds) - 1.0

    # HARD SAFEGUARD: enforce the 2.0-5.0 / max-5-legs strategy cap at runtime.
    # Real money is at stake — never ship a slip that violates the rules.
    if combined_odds > TARGET_MAX_ODDS or len(legs) > MAX_LEGS:
        return None

    if confidence_avg >= 78 and combined_odds <= 3.5 and expected_value > 0.08:
        risk = "LOW"
    elif confidence_avg >= 68 and expected_value > 0:
        risk = "MEDIUM"
    else:
        risk = "HIGH"

    sport_mix = sorted({l.sport.title() for l in legs})
    summary = (
        f"Combined slip of {len(picks)} highest-confidence games "
        f"({' + '.join(sport_mix)}) — total odds {combined_odds:.2f} · "
        f"avg confidence {confidence_avg:.0f}% · model edge {expected_value*100:+.1f}%."
    )

    return CombinedSlip(
        date=date_str, legs=legs, leg_count=len(legs),
        combined_odds=round(combined_odds, 2),
        combined_confidence=round(confidence_avg, 1),
        expected_value=round(expected_value, 4),
        risk_level=risk,
        sportybet_code=(manual_code or "").strip().upper(),
        sportybet_url=sportybet_url,
        summary=summary, locked=False,
        optional_picks=_build_optional_categories(all_picks, picks),
        candidate_count=len(all_picks),
        quality_note=(
            "Main slip is capped at 5 odds and only uses the strongest approved legs. "
            "Optional categories are listed separately so users can add extra games knowingly."
        ),
    )
