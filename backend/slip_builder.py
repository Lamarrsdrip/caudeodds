"""ClaudeOdd combined slip builder.

Goal: combine 3-5 highest-confidence games such that the combined (multiplied)
decimal odds land in the user-friendly [2.0, 5.0] range. Caps at 5 odds.
"""
from __future__ import annotations

import hashlib
from typing import List

from saas_models import CombinedSlip, SlipLeg


TARGET_MIN_ODDS = 2.0
TARGET_MAX_ODDS = 5.0
MIN_LEGS = 3
MAX_LEGS = 5
HARD_MIN_LEGS = 2  # if we truly cannot reach 3, fall back


def make_sportybet_code(date_str: str, picks: List) -> str:
    seed = date_str + "|" + "|".join(f"{p.match}-{p.market}" for p in picks)
    h = hashlib.sha256(seed.encode()).hexdigest().upper()
    alnum = "".join(c for c in h if c.isalnum())
    return f"SB-{alnum[:6]}-{alnum[6:10]}"


def _select_picks(picks: List) -> List:
    """Greedy pack: take highest-confidence picks first. Combined odds must stay
    within [2.0, 5.0]. Legs preferred 3-5, minimum 2."""
    if not picks:
        return []
    sorted_picks = sorted(
        picks,
        key=lambda p: (p.confidence * 0.6 + (p.expected_value * 100) * 0.3 + p.agreement * 0.1),
        reverse=True,
    )

    selected: List = []
    combined = 1.0
    for p in sorted_picks:
        if len(selected) >= MAX_LEGS:
            break
        new_combined = combined * float(p.odds)
        # If adding this leg breaks the cap AND we already have enough legs → stop
        if new_combined > TARGET_MAX_ODDS and len(selected) >= HARD_MIN_LEGS:
            break
        # If adding would break cap and we don't yet have hard-min legs, skip and try next
        if new_combined > TARGET_MAX_ODDS:
            continue
        selected.append(p)
        combined = new_combined
        # Sweet spot: at least min legs and combined inside [2.0, 5.0] → stop
        if len(selected) >= MIN_LEGS and combined >= TARGET_MIN_ODDS:
            break

    # If still under TARGET_MIN_ODDS, try to add more (highest odds first that still fits)
    if combined < TARGET_MIN_ODDS:
        remaining = [p for p in sorted_picks if p not in selected]
        # Sort remaining by odds DESC to push combined up faster
        remaining.sort(key=lambda p: p.odds, reverse=True)
        for p in remaining:
            if len(selected) >= MAX_LEGS:
                break
            new_combined = combined * float(p.odds)
            if new_combined > TARGET_MAX_ODDS:
                continue
            selected.append(p)
            combined = new_combined
            if combined >= TARGET_MIN_ODDS:
                break

    return selected


def build_slip(date_str: str, all_picks: List, sportybet_url: str = "https://www.sportybet.com/ng/") -> CombinedSlip | None:
    if not all_picks:
        return None
    picks = _select_picks(all_picks)
    if len(picks) < HARD_MIN_LEGS:
        # Not enough quality picks today
        return None

    legs: List[SlipLeg] = []
    combined_odds = 1.0
    fair_prob = 1.0
    confidence_avg = 0.0

    for p in picks:
        legs.append(SlipLeg(
            match=p.match, league=p.league, sport=p.sport, market=p.market,
            selection_label=p.selection_label, odds=p.odds, confidence=p.confidence,
            edge_pct=p.edge_pct, reasoning=(p.reasoning or "")[:240],
        ))
        combined_odds *= float(p.odds)
        try:
            fp = float(p.quant_view.fair_prob)
        except Exception:
            fp = 1.0 / float(p.odds)
        fair_prob *= fp
        confidence_avg += p.confidence

    confidence_avg = confidence_avg / len(picks)
    expected_value = (fair_prob * combined_odds) - 1.0

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
        risk_level=risk,  # type: ignore[arg-type]
        sportybet_code=make_sportybet_code(date_str, picks),
        sportybet_url=sportybet_url,
        summary=summary,
        locked=False,
    )
