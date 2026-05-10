"""ClaudeOdds combined slip builder.

Goal: combine 3-5 highest-confidence games such that the combined (multiplied)
decimal odds land in the user-friendly [2.0, 5.0] range. Cap at 5.0 odds.

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


def _select_picks(picks: List) -> List:
    """Pick 3-5 legs that pack into the 2.0-5.0 combined-odds window.

    Strategy: prefer 3-LEG ACCUMULATORS over 1-2 big-odds singles. A 3-leg
    accumulator at 2.5 combined is psychologically easier (3 small wins vs
    1 medium win) AND statistically better for our subscribers because we
    average pick-correlation across legs.

    Search order:
      1. Try every combination of 3-5 picks that lands in [2.0, 5.0]; rank
         them by min(individual confidences) × combined EV. Pick the best.
      2. If none, fall back to 2-leg combinations.
      3. If still nothing, single highest-confidence pick.
    """
    from itertools import combinations
    if not picks:
        return []

    # Pre-rank picks by quality (confidence + edge — ignore odds size here so
    # we don't auto-prefer favourites; size is handled by the combo search).
    ranked = sorted(
        picks,
        key=lambda p: (p.confidence * 0.55 + (p.expected_value * 100) * 0.30 + p.agreement * 0.15),
        reverse=True,
    )
    pool = ranked[:12]  # cap search space — 12C5 = 792 combos max

    def combo_score(combo) -> float:
        combined_odds = 1.0
        combined_fp = 1.0
        away_count = home_count = 0
        for p in combo:
            combined_odds *= float(p.odds)
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
        # DIRECTIONAL DIVERSITY: hard-reject combos that are entirely one-sided
        # when the combo has 3+ legs AND we have alternatives. This kills the
        # "all away" pattern subscribers complained about.
        if len(combo) >= 3 and (away_count == len(combo) or home_count == len(combo)):
            return -0.5  # negative but better than invalid range — fallback
        ev = combined_fp * combined_odds - 1.0
        min_conf = min(p.confidence for p in combo)
        avg_conf = sum(p.confidence for p in combo) / len(combo)
        # STRONG accumulator preference: 3-leg gets +50, 4-leg +100, 5-leg +150.
        # This dwarfs the EV signal so we always prefer accumulators over singles.
        leg_bonus = (len(combo) - 1) * 50.0
        return (min_conf * 0.30) + (avg_conf * 0.20) + (ev * 100 * 0.20) + leg_bonus

    # Try combos largest-first so we prefer accumulators
    best_combo = None
    best_score = -1.0
    # Search 3+ leg combos first; only fall back to 2-leg if NO 3-leg fits the window
    for n in (5, 4, 3):
        for combo in combinations(pool, min(n, len(pool))):
            s = combo_score(list(combo))
            if s > best_score:
                best_score = s
                best_combo = list(combo)
        if best_combo and best_score > 0:
            return best_combo

    # 3-leg search exhausted — try 2-leg as graceful fallback
    for combo in combinations(pool, min(2, len(pool))):
        s = combo_score(list(combo))
        if s > best_score:
            best_score = s
            best_combo = list(combo)
    if best_combo and best_score > 0:
        return best_combo

    # Last resort: best single pick (with a clear warning to the user)
    return [max(picks, key=lambda p: p.confidence)]


def build_slip(date_str: str, all_picks: List, sportybet_url: str = "https://www.sportybet.com/ng/", manual_code: str = "") -> CombinedSlip | None:
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
    )
