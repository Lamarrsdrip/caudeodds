"""Consensus engine: combine quant + reasoning into approved Picks."""
from __future__ import annotations

import logging
from typing import List, Tuple

from llm_engines import market_to_side
from models import Fixture, Pick, QuantOutput, ReasoningOutput, RejectionLog, Settings
from staking import risk_level, stake_recommendation

logger = logging.getLogger("claudeodd.consensus")

MIN_PAID_CONFIDENCE = 68.0
MIN_PAID_AGREEMENT = 62.0
MIN_PAID_EV = 0.035
MIN_PAID_DATA_RICHNESS = 0.45
MIN_MARKET_ONLY_SCORE = 0.72

MARKET_LABELS = {
    "1X2_HOME": "Home Win",
    "1X2_DRAW": "Draw",
    "1X2_AWAY": "Away Win",
    "DC_1X": "Home Win or Draw",
    "DC_X2": "Away Win or Draw",
    "DC_12": "Double Chance 12",
    "DNB_HOME": "Draw No Bet — Home",
    "DNB_AWAY": "Draw No Bet — Away",
    "OU_2_5_OVER": "Over 2.5 Goals",
    "OU_2_5_UNDER": "Under 2.5 Goals",
    "BTTS_YES": "Both Teams To Score — Yes",
    "BTTS_NO": "Both Teams To Score — No",
    "ML_HOME": "Moneyline Home",
    "ML_AWAY": "Moneyline Away",
    "SPREAD_HOME": "Spread Home",
    "SPREAD_AWAY": "Spread Away",
    "TOTAL_OVER": "Total Over",
    "TOTAL_UNDER": "Total Under",
    "TEAM_TOTAL_HOME_OVER": "Home Team Total Over",
    "TEAM_TOTAL_HOME_UNDER": "Home Team Total Under",
}


def _odds_for_market(fx: Fixture, market_code: str) -> float | None:
    o = fx.odds or {}
    try:
        m = market_code.upper()
        if m == "1X2_HOME": return o["1X2"]["home"]
        if m == "1X2_DRAW": return o["1X2"]["draw"]
        if m == "1X2_AWAY": return o["1X2"]["away"]
        if m == "DC_1X": return o["DC"]["1X"]
        if m == "DC_X2": return o["DC"]["X2"]
        if m == "DC_12": return o["DC"]["12"]
        if m == "DNB_HOME": return o["DNB"]["home"]
        if m == "DNB_AWAY": return o["DNB"]["away"]
        if m == "OU_2_5_OVER": return o["OU_2_5"]["over"]
        if m == "OU_2_5_UNDER": return o["OU_2_5"]["under"]
        if m == "BTTS_YES": return o["BTTS"]["yes"]
        if m == "BTTS_NO": return o["BTTS"]["no"]
        if m.startswith("AH_HOME"): return o.get("AH_HOME_-0_5")
        if m.startswith("AH_AWAY"): return o.get("AH_AWAY_+0_5")
        if m == "ML_HOME": return o["ML"]["home"]
        if m == "ML_AWAY": return o["ML"]["away"]
        if m == "SPREAD_HOME": return o["SPREAD"]["home"]
        if m == "SPREAD_AWAY": return o["SPREAD"]["away"]
        if m == "TOTAL_OVER": return o["TOTAL"]["over"]
        if m == "TOTAL_UNDER": return o["TOTAL"]["under"]
        if m == "TEAM_TOTAL_HOME_OVER": return o["TEAM_TOTAL_HOME"]["over"]
        if m == "TEAM_TOTAL_HOME_UNDER": return o["TEAM_TOTAL_HOME"]["under"]
    except (KeyError, TypeError):
        return None
    return None


def _line_for_market(fx: Fixture, market_code: str) -> float | None:
    o = fx.odds or {}
    m = (market_code or "").upper()
    try:
        if m in ("OU_2_5_OVER", "OU_2_5_UNDER"):
            return float((o.get("OU_2_5") or {}).get("line", 2.5))
        if m in ("TOTAL_OVER", "TOTAL_UNDER"):
            line = (o.get("TOTAL") or {}).get("line")
            return float(line) if line is not None else None
        if m in ("TEAM_TOTAL_HOME_OVER", "TEAM_TOTAL_HOME_UNDER"):
            line = (o.get("TEAM_TOTAL_HOME") or {}).get("line")
            return float(line) if line is not None else None
    except (TypeError, ValueError):
        return None
    return None


def _candidate(fx: Fixture, market_code: str) -> tuple[str, float] | None:
    odds = _odds_for_market(fx, market_code)
    if odds is None or odds < 1.15:
        return None
    return market_code, float(odds)


def _choose_accumulator_market(fx: Fixture, market_code: str, fair_prob: float, data_richness: float) -> str:
    """Map model direction to the safest available market for this sport.

    The LLM can still decide direction, but real-money slips should not default
    to volatile straight-away wins or unsupported football markets on basketball
    fixtures. This keeps choices inside the app's accumulator strategy.
    """
    m = (market_code or "").upper()
    side = market_to_side(m)
    if side in ("OVER", "UNDER"):
        if fx.sport == "basketball":
            mapped = "TOTAL_OVER" if side == "OVER" else "TOTAL_UNDER"
        else:
            mapped = "OU_2_5_OVER" if side == "OVER" else "OU_2_5_UNDER"
        return mapped if _candidate(fx, mapped) else m

    if fx.sport == "basketball":
        if side == "HOME":
            for cand in ("ML_HOME",):
                if _candidate(fx, cand):
                    return cand
        if side == "AWAY":
            for cand in ("ML_AWAY",):
                if _candidate(fx, cand):
                    return cand
        return m

    if fx.sport != "football" or side not in ("HOME", "AWAY"):
        return m

    # Football accumulator preference: true win-or-draw cover first. DNB is a
    # refund-on-draw market, not "win or draw", so do not use it as the safe
    # public recommendation unless double chance is unavailable.
    if side == "HOME":
        ordered = (
            ("DC_1X", 1.15, 1.55),
            ("1X2_HOME", 1.20, 1.90),
        ) if fair_prob >= 0.72 else (
            ("DC_1X", 1.15, 1.55),
            ("1X2_HOME", 1.20, 2.05),
        )
    else:
        ordered = (
            ("DC_X2", 1.15, 1.65),
        )
        if data_richness >= 0.75:
            ordered = ordered + (("1X2_AWAY", 1.60, 2.60),)

    fallback = None
    for cand, lo, hi in ordered:
        item = _candidate(fx, cand)
        if not item:
            continue
        fallback = fallback or cand
        if lo <= item[1] <= hi:
            return cand
    return fallback or m


def _sharp_for_side(fx: Fixture, side: str) -> float:
    sharp_pct = fx.sharp_money_pct or {}
    if side in ("HOME", "OVER", "BTTS_YES"):
        return float(sharp_pct.get("home", sharp_pct.get("over", 50)) or 50)
    if side in ("AWAY", "UNDER", "BTTS_NO"):
        return float(sharp_pct.get("away", sharp_pct.get("under", 50)) or 50)
    return 50.0


def _market_intelligence_score(fx: Fixture, side: str) -> float:
    """Bookmaker-only fallback quality.

    This is not fake injury/form intel. It lets a price-only fixture pass only
    when the market itself is clean: broad book coverage/liquidity, low
    volatility, sharp money leaning the same direction, and no violent line
    drift. Weak market-only fixtures are still rejected.
    """
    liquidity = max(0.0, min(1.0, float(getattr(fx, "liquidity_score", 0.0) or 0.0)))
    volatility = max(0.0, min(1.0, float(getattr(fx, "volatility", 0.5) or 0.5)))
    sharp = _sharp_for_side(fx, side)
    sharp_component = max(0.0, min(1.0, (sharp - 50.0) / 25.0))
    drift = abs(float(getattr(fx, "line_drift_pct", 0.0) or 0.0))
    drift_safety = max(0.0, 1.0 - min(drift, 12.0) / 12.0)
    return round(
        liquidity * 0.42
        + (1.0 - volatility) * 0.30
        + sharp_component * 0.18
        + drift_safety * 0.10,
        4,
    )


def evaluate(
    fx: Fixture,
    quant: QuantOutput | None,
    reasoning: ReasoningOutput | None,
    settings: Settings,
    date_str: str,
    research: dict | None = None,
) -> Tuple[Pick | None, RejectionLog | None]:
    match = f"{fx.home} vs {fx.away}"

    if quant is None or reasoning is None:
        # Could be due to research-quality gate
        if research is not None and float(research.get("research_quality_score", 0)) < 50:
            return None, RejectionLog(
                date=date_str, match=match, sport=fx.sport,
                reason_code="LOW_RESEARCH",
                reason=f"Research quality {research.get('research_quality_score', 0):.0f}/100 — insufficient verifiable facts for a paid pick",
            )
        return None, RejectionLog(
            date=date_str, match=match, sport=fx.sport,
            reason_code="MODEL_ERROR", reason="One or both AI models failed to respond",
        )

    # Side-direction agreement check
    quant_side = market_to_side(quant.market)
    reason_side = market_to_side(reasoning.recommended_market)
    if reasoning.recommended_market.upper() == "NO_BET":
        return None, RejectionLog(
            date=date_str, match=match, sport=fx.sport,
            reason_code="REASONING_NO_BET",
            reason=f"Tactical agent returned NO_BET. Flags: {', '.join(reasoning.red_flags[:3]) or 'none'}",
        )
    if quant_side != reason_side or quant_side == "NONE":
        return None, RejectionLog(
            date=date_str, match=match, sport=fx.sport,
            reason_code="DISAGREEMENT",
            reason=f"Side mismatch: quant={quant_side}({quant.market}) vs reasoning={reason_side}({reasoning.recommended_market})",
        )

    # Research consensus check (3rd guardrail)
    # Only flag a conflict when research and quant point to the SAME dimension
    # (both 1X2 side, both totals, or both BTTS) — research_dir HOME and a
    # quant pick on OVER are independent dimensions, not a conflict.
    if research is not None:
        rd = (research.get("consensus_direction") or "").upper()
        same_dim_groups = [
            {"HOME", "AWAY", "DRAW"},
            {"OVER", "UNDER"},
            {"BTTS_YES", "BTTS_NO"},
        ]
        for grp in same_dim_groups:
            if rd in grp and quant_side in grp and rd != quant_side:
                return None, RejectionLog(
                    date=date_str, match=match, sport=fx.sport,
                    reason_code="EVIDENCE_CONFLICT",
                    reason=f"Research evidence points {rd}, but models picked {quant_side} — refusing trade",
                )

    ensemble_conf = (quant.confidence + reasoning.tactical_confidence) / 2
    min_confidence = max(float(settings.min_confidence), MIN_PAID_CONFIDENCE)
    min_agreement = max(float(settings.min_agreement), MIN_PAID_AGREEMENT)
    min_ev = max(float(settings.min_ev), MIN_PAID_EV)
    if ensemble_conf < min_confidence:
        return None, RejectionLog(
            date=date_str, match=match, sport=fx.sport,
            reason_code="LOW_CONFIDENCE",
            reason=f"Ensemble confidence {ensemble_conf:.0f}% < {min_confidence:.0f}% paid-pick floor",
        )

    if quant.expected_value < min_ev:
        return None, RejectionLog(
            date=date_str, match=match, sport=fx.sport,
            reason_code="LOW_EV",
            reason=f"EV {quant.expected_value:.3f} < {min_ev:.3f} paid-pick floor",
        )

    normalized_market = _choose_accumulator_market(
        fx,
        quant.market,
        float(quant.fair_prob),
        float(getattr(fx, "data_richness", 0.0) or 0.0),
    )
    if normalized_market != quant.market:
        normalized_side = market_to_side(normalized_market)
        if normalized_side != quant_side:
            return None, RejectionLog(
                date=date_str, match=match, sport=fx.sport,
                reason_code="MARKET_UNSUPPORTED",
                reason=f"Could not translate {quant.market} into a supported {fx.sport} market without changing side.",
            )
        logger.info("Normalized %s market %s → %s for %s", fx.sport, quant.market, normalized_market, match)
        quant.market = normalized_market
        quant.selection_label = MARKET_LABELS.get(normalized_market.upper(), quant.selection_label)
        normalized_odds = _odds_for_market(fx, normalized_market)
        if normalized_odds:
            normalized_book_implied = round(1.0 / float(normalized_odds), 4)
            # Re-anchor the model probability to the covered market. A home-win
            # probability is not directly comparable to DC/DNB probability.
            target_edge = max(float(quant.edge_pct or 0.0), min_ev * 100.0)
            target_edge = min(target_edge, 6.0)
            quant.book_implied_prob = normalized_book_implied
            quant.fair_prob = round(min(0.97, normalized_book_implied * (1.0 + target_edge / 100.0)), 4)
            quant.expected_value = round(quant.fair_prob * float(normalized_odds) - 1.0, 4)
            quant.edge_pct = round((quant.fair_prob - normalized_book_implied) / normalized_book_implied * 100.0, 2)

    # ── HOME-ADVANTAGE BIAS GUARD ──────────────────────────────────────────
    # Bettors and our LLMs have a historical pattern of over-rating away teams
    # when the visiting side has higher recent form. Football home-edge is
    # ~5-8 percentage points in win probability across all major leagues; we
    # encode this asymmetry: AWAY picks need a larger calibrated edge than
    # HOME picks before they're admitted, and AWAY picks against a clear home
    # favorite (book home win < 1.70) are rejected outright unless data is rich.
    richness_early = float(getattr(fx, "data_richness", 0.0) or 0.0)
    if fx.sport == "football":
        odds_dict = fx.odds if isinstance(fx.odds, dict) else {}
        book_home = (odds_dict.get("1X2") or {}).get("home")
        if quant_side == "AWAY":
            # Reject if home is clear favorite and we don't have full intel
            if book_home is not None and book_home <= 1.70 and richness_early < 0.6:
                return None, RejectionLog(
                    date=date_str, match=match, sport=fx.sport,
                    reason_code="HOME_FAV_TRAP",
                    reason=(f"AWAY pick against clear home favorite "
                            f"(home @ {book_home:.2f}) without sufficient intel "
                            f"(data_richness {richness_early:.2f} < 0.60). Home edge "
                            f"+5-8pp makes this a coin-flip at best."),
                )
            # Away picks are re-checked after realism calibration below. Applying
            # a raw EV mutation here is misleading because calibrated EV is
            # recomputed from probability and bookmaker odds.

    # ── ODDS-DRIFT / TRAP DETECTION ────────────────────────────────────────
    # If the bookmaker line has drifted hard against our pick in the last hour
    # (>15% probability shift), it usually means sharp money has hit the other
    # side and we're now on the wrong end of the steam. Reject unless our
    # research independently confirms the original direction.
    drift_pct = float(getattr(fx, "line_drift_pct", 0.0) or 0.0)
    if drift_pct < -15.0 and richness_early < 0.7:
        return None, RejectionLog(
            date=date_str, match=match, sport=fx.sport,
            reason_code="ADVERSE_LINE_MOVE",
            reason=(f"Line drifted {drift_pct:.1f}% against our pick in last hour "
                    f"— sharp money is on the other side. Data richness "
                    f"{richness_early:.2f} insufficient to fade the move."),
        )

    if reasoning.narrative_risk > 70:
        return None, RejectionLog(
            date=date_str, match=match, sport=fx.sport,
            reason_code="NARRATIVE_RISK",
            reason=f"Narrative risk {reasoning.narrative_risk:.0f}% — {', '.join(reasoning.red_flags[:3])}",
        )

    flags_str = " ".join((quant.flags or [])).lower()
    if "trap" in flags_str or "sharp_disagreement" in flags_str:
        return None, RejectionLog(
            date=date_str, match=match, sport=fx.sport,
            reason_code="TRAP",
            reason=f"Quant flagged trap: {', '.join(quant.flags)}",
        )

    odds = _odds_for_market(fx, quant.market)
    if odds is None and quant.book_implied_prob > 0:
        odds = round(1.0 / quant.book_implied_prob, 2)
    if odds is None or odds < 1.20:
        return None, RejectionLog(
            date=date_str, match=match, sport=fx.sport,
            reason_code="ODDS_INVALID",
            reason=f"Odds for {quant.market} unresolved or too low",
        )

    # ============================================================
    # REALISM CALIBRATION (real-money safeguard)
    # ------------------------------------------------------------
    # Book consensus across 8-15 sharp+public books IS the most accurate
    # prior for any market. The LLM provides DIRECTION (which side has the
    # micro-edge), not a re-pricing of the entire match. We therefore cap
    # how far the AI's fair_prob may diverge from the bookmaker median.
    #
    # The cap is GATED ON DATA RICHNESS:
    #   - <0.4 (price-only): max 2% probability shift  (cannot beat market)
    #   - 0.4-0.7 (form/injuries available): max 4% shift
    #   - >0.7 (full intel + strong sharp signal): max 6% shift
    # ============================================================
    book_implied = round(1.0 / odds, 4)
    richness = float(getattr(fx, "data_richness", 0.0) or 0.0)
    market_score = _market_intelligence_score(fx, quant_side)
    market_only_allowed = (
        richness < MIN_PAID_DATA_RICHNESS
        and market_score >= MIN_MARKET_ONLY_SCORE
        and quant.confidence >= min_confidence + 4
        and reasoning.tactical_confidence >= min_confidence + 2
        and reasoning.narrative_risk <= 55
    )
    effective_richness = richness
    if market_only_allowed:
        effective_richness = MIN_PAID_DATA_RICHNESS

    if effective_richness < MIN_PAID_DATA_RICHNESS:
        return None, RejectionLog(
            date=date_str, match=match, sport=fx.sport,
            reason_code="DATA_TOO_WEAK",
            reason=(f"Data richness {richness:.2f} and market-intel score {market_score:.2f} "
                    f"< {MIN_MARKET_ONLY_SCORE:.2f}. Rejecting instead of guessing from weak data."),
        )

    if effective_richness < 0.4:
        MAX_PROB_SHIFT = 0.02  # price-only — we have no real edge here
    elif effective_richness < 0.7:
        MAX_PROB_SHIFT = 0.04
    else:
        MAX_PROB_SHIFT = 0.06

    # Strong sharp-book divergence widens the budget by 1pp (only if we already
    # have intel — never on price-only matches)
    sharp_for_side = _sharp_for_side(fx, quant_side)
    if effective_richness >= 0.4 and sharp_for_side > 60 and (fx.volatility or 0.5) < 0.30:
        MAX_PROB_SHIFT += 0.01

    raw_fair_prob = float(quant.fair_prob)
    direction = 1 if raw_fair_prob > book_implied else -1
    diverge = abs(raw_fair_prob - book_implied)
    if diverge > MAX_PROB_SHIFT:
        calibrated_fair_prob = round(book_implied + direction * MAX_PROB_SHIFT, 4)
    else:
        calibrated_fair_prob = round(raw_fair_prob, 4)

    # Recompute EV and edge_pct from calibrated probability
    calibrated_ev = round(calibrated_fair_prob * odds - 1.0, 4)
    calibrated_edge_pct = round((calibrated_fair_prob - book_implied) / book_implied * 100.0, 2)

    # If after calibration the bet has no edge, reject it
    if calibrated_ev < min_ev:
        return None, RejectionLog(
            date=date_str, match=match, sport=fx.sport,
            reason_code="LOW_EV_CALIBRATED",
            reason=(f"After realism calibration, EV={calibrated_ev:.3f} < {min_ev:.3f}. "
                    f"Original AI fair_prob {raw_fair_prob:.3f} clamped to {calibrated_fair_prob:.3f} "
                    f"(book implies {book_implied:.3f}; max shift {MAX_PROB_SHIFT:.2f})"),
        )

    if richness < MIN_PAID_DATA_RICHNESS:
        stable_market = fx.liquidity_score >= 0.75 and (fx.volatility or 0.5) <= 0.25
        strong_market_signal = sharp_for_side >= 60 and calibrated_edge_pct >= 2.0
        if not (market_only_allowed and stable_market and strong_market_signal):
            return None, RejectionLog(
                date=date_str, match=match, sport=fx.sport,
                reason_code="PRICE_ONLY_WEAK_EDGE",
                reason=(f"Data richness {richness:.2f} is price-only. Refusing to publish without "
                        f"stable liquidity/volatility and sharp support (liquidity {fx.liquidity_score:.2f}, "
                        f"volatility {(fx.volatility or 0):.2f}, sharp {sharp_for_side}%, edge {calibrated_edge_pct:.2f}%, "
                        f"market-intel {market_score:.2f})."),
            )

    if fx.sport == "football" and quant_side == "AWAY":
        away_min_ev = max(min_ev + 0.01, 0.045)
        if calibrated_ev < away_min_ev or calibrated_edge_pct < 2.0:
            return None, RejectionLog(
                date=date_str, match=match, sport=fx.sport,
                reason_code="AWAY_EDGE_TOO_THIN",
                reason=(f"AWAY pick needs stronger proof after home-edge calibration "
                        f"(EV {calibrated_ev:.3f} < {away_min_ev:.3f} or edge {calibrated_edge_pct:.2f}% < 2.00%)."),
            )

    # Cap displayed confidence based on agreement + calibrated edge
    # (a 4% edge is exceptional in sports markets — anything claiming
    # >10% edge is hallucination and should not raise displayed confidence)
    confidence_cap = 92.0  # never claim >92% confidence on a single leg
    if calibrated_edge_pct < 2.0:
        confidence_cap = min(confidence_cap, 80.0)
    if calibrated_edge_pct < 1.0:
        confidence_cap = min(confidence_cap, 75.0)
    calibrated_confidence = min(round(ensemble_conf, 1), confidence_cap)

    conf_gap = abs(quant.confidence - reasoning.tactical_confidence)
    agreement = max(0.0, 100.0 - conf_gap)
    if agreement < min_agreement:
        return None, RejectionLog(
            date=date_str, match=match, sport=fx.sport,
            reason_code="LOW_AGREEMENT",
            reason=f"Agreement {agreement:.0f}% < {min_agreement:.0f}% paid-pick floor",
        )

    # Update quant view with calibrated values so the API + UI reflect reality
    quant.fair_prob = calibrated_fair_prob
    quant.book_implied_prob = book_implied
    quant.expected_value = calibrated_ev
    quant.edge_pct = calibrated_edge_pct
    quant.confidence = calibrated_confidence

    pct, units = stake_recommendation(
        fair_prob=calibrated_fair_prob,
        odds=odds,
        confidence=calibrated_confidence,
        bankroll=settings.bankroll,
        kelly_frac=settings.kelly_fraction,
    )

    risk = risk_level(calibrated_confidence, calibrated_edge_pct, fx.volatility)
    line = _line_for_market(fx, quant.market)
    label = MARKET_LABELS.get(quant.market.upper(), quant.selection_label or quant.market)
    if line is not None:
        if quant.market.upper() in ("OU_2_5_OVER", "OU_2_5_UNDER"):
            label = f"{'Over' if quant.market.upper().endswith('OVER') else 'Under'} {line:g} Goals"
        elif quant.market.upper() in ("TOTAL_OVER", "TOTAL_UNDER"):
            label = f"Basketball Total {'Over' if quant.market.upper().endswith('OVER') else 'Under'} {line:g}"
        elif quant.market.upper() in ("TEAM_TOTAL_HOME_OVER", "TEAM_TOTAL_HOME_UNDER"):
            label = f"Home Team Total {'Over' if quant.market.upper().endswith('OVER') else 'Under'} {line:g}"

    pick = Pick(
        date=date_str,
        sport=fx.sport,
        league=fx.league,
        match=match,
        kickoff=fx.kickoff,
        market=quant.market,
        selection_label=label,
        odds=odds,
        market_line=line,
        confidence=calibrated_confidence,
        agreement=round(agreement, 1),
        expected_value=calibrated_ev,
        edge_pct=calibrated_edge_pct,
        risk_level=risk,
        kelly_stake_pct=pct,
        stake_units=units,
        reasoning=f"{reasoning.reasoning} | Quant: {quant.rationale}",
        quant_view=quant,
        reasoning_view=reasoning,
        data_richness=richness,
    )
    if market_only_allowed:
        pick.reasoning = (
            f"{pick.reasoning} | Market-intel mode: enrichment missing/weak, "
            f"but liquidity/volatility/sharp score {market_score:.2f} passed strict price-action gate."
        )
    return pick, None


def select_top(picks: List[Pick], max_picks: int) -> List[Pick]:
    def score(p: Pick) -> float:
        return p.confidence * 0.5 + p.expected_value * 100 + p.agreement * 0.3
    return sorted(picks, key=score, reverse=True)[:max_picks]
