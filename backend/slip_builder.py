"""Combined daily slip builder — turns approved picks into a single 2-5 leg
parlay with SportyBet-style booking code and deep link.
"""
from __future__ import annotations

import hashlib
from typing import List

from saas_models import CombinedSlip, SlipLeg


def make_sportybet_code(date_str: str, legs: List) -> str:
    """Generate a deterministic SportyBet-style booking code from the slip."""
    seed = date_str + "|" + "|".join(f"{p.match}-{p.market}" for p in legs)
    h = hashlib.sha256(seed.encode()).hexdigest().upper()
    # SportyBet codes are typically 6-character alphanumeric (e.g. "RAFD7K")
    alnum = "".join(c for c in h if c.isalnum())
    return f"SB-{alnum[:6]}-{alnum[6:10]}"


def build_slip(date_str: str, picks: List, sportybet_url: str = "https://www.sportybet.com/ng/") -> CombinedSlip | None:
    if not picks:
        return None

    legs: List[SlipLeg] = []
    combined_odds = 1.0
    fair_prob = 1.0
    confidence_avg = 0.0

    for p in picks:
        legs.append(SlipLeg(
            match=p.match,
            league=p.league,
            sport=p.sport,
            market=p.market,
            selection_label=p.selection_label,
            odds=p.odds,
            confidence=p.confidence,
            edge_pct=p.edge_pct,
            reasoning=(p.reasoning or "")[:240],
        ))
        combined_odds *= float(p.odds)
        # Use quant_view fair_prob if present
        try:
            fp = float(p.quant_view.fair_prob)
        except Exception:
            fp = 1.0 / float(p.odds)
        fair_prob *= fp
        confidence_avg += p.confidence

    confidence_avg = confidence_avg / len(picks)
    expected_value = (fair_prob * combined_odds) - 1.0

    # Risk derivation for the parlay
    if confidence_avg >= 75 and len(picks) <= 3 and expected_value > 0.10:
        risk = "LOW"
    elif confidence_avg >= 65 and expected_value > 0:
        risk = "MEDIUM"
    else:
        risk = "HIGH"

    summary = (
        f"{len(picks)}-leg combined slip across "
        f"{', '.join(sorted({l.sport.title() for l in legs}))}: "
        f"AI ensemble confidence avg {confidence_avg:.0f}% with combined fair probability "
        f"{fair_prob*100:.1f}% vs implied {1/combined_odds*100:.1f}% — edge {expected_value*100:+.1f}%."
    )

    return CombinedSlip(
        date=date_str,
        legs=legs,
        leg_count=len(legs),
        combined_odds=round(combined_odds, 2),
        combined_confidence=round(confidence_avg, 1),
        expected_value=round(expected_value, 4),
        risk_level=risk,  # type: ignore[arg-type]
        sportybet_code=make_sportybet_code(date_str, picks),
        sportybet_url=sportybet_url,
        summary=summary,
        locked=False,
    )
