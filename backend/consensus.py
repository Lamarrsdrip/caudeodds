"""Consensus engine: combine quant + reasoning into approved Picks."""
from __future__ import annotations

import logging
from typing import List, Tuple

from llm_engines import market_to_side
from models import Fixture, Pick, QuantOutput, ReasoningOutput, RejectionLog, Settings
from staking import risk_level, stake_recommendation

logger = logging.getLogger("claudeodd.consensus")

MARKET_LABELS = {
    "1X2_HOME": "Home Win",
    "1X2_DRAW": "Draw",
    "1X2_AWAY": "Away Win",
    "DC_1X": "Double Chance 1X",
    "DC_X2": "Double Chance X2",
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
        if research is not None and float(research.get("research_quality_score", 0)) < 25:
            return None, RejectionLog(
                date=date_str, match=match, sport=fx.sport,
                reason_code="LOW_RESEARCH",
                reason=f"Research quality {research.get('research_quality_score', 0):.0f}/100 — insufficient verifiable facts",
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
    if ensemble_conf < settings.min_confidence:
        return None, RejectionLog(
            date=date_str, match=match, sport=fx.sport,
            reason_code="LOW_CONFIDENCE",
            reason=f"Ensemble confidence {ensemble_conf:.0f}% < {settings.min_confidence:.0f}%",
        )

    if quant.expected_value < settings.min_ev:
        return None, RejectionLog(
            date=date_str, match=match, sport=fx.sport,
            reason_code="LOW_EV",
            reason=f"EV {quant.expected_value:.3f} < {settings.min_ev:.3f}",
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

    conf_gap = abs(quant.confidence - reasoning.tactical_confidence)
    agreement = max(0.0, 100.0 - conf_gap)
    if agreement < settings.min_agreement:
        return None, RejectionLog(
            date=date_str, match=match, sport=fx.sport,
            reason_code="LOW_AGREEMENT",
            reason=f"Agreement {agreement:.0f}% < {settings.min_agreement:.0f}%",
        )

    pct, units = stake_recommendation(
        fair_prob=quant.fair_prob,
        odds=odds,
        confidence=ensemble_conf,
        bankroll=settings.bankroll,
        kelly_frac=settings.kelly_fraction,
    )

    risk = risk_level(ensemble_conf, quant.edge_pct, fx.volatility)
    label = quant.selection_label or MARKET_LABELS.get(quant.market.upper(), quant.market)

    pick = Pick(
        date=date_str,
        sport=fx.sport,
        league=fx.league,
        match=match,
        kickoff=fx.kickoff,
        market=quant.market,
        selection_label=label,
        odds=odds,
        confidence=round(ensemble_conf, 1),
        agreement=round(agreement, 1),
        expected_value=round(quant.expected_value, 4),
        edge_pct=round(quant.edge_pct, 2),
        risk_level=risk,
        kelly_stake_pct=pct,
        stake_units=units,
        reasoning=f"{reasoning.reasoning} | Quant: {quant.rationale}",
        quant_view=quant,
        reasoning_view=reasoning,
    )
    return pick, None


def select_top(picks: List[Pick], max_picks: int) -> List[Pick]:
    def score(p: Pick) -> float:
        return p.confidence * 0.5 + p.expected_value * 100 + p.agreement * 0.3
    return sorted(picks, key=score, reverse=True)[:max_picks]
