"""Kelly Criterion + confidence-weighted stake sizing."""
from __future__ import annotations


def kelly_fraction(prob: float, decimal_odds: float) -> float:
    """Full Kelly fraction. Returns 0 if no edge."""
    b = decimal_odds - 1.0
    if b <= 0:
        return 0.0
    q = 1 - prob
    f = (b * prob - q) / b
    return max(0.0, f)


def stake_recommendation(
    fair_prob: float,
    odds: float,
    confidence: float,
    bankroll: float,
    kelly_frac: float = 0.25,
) -> tuple[float, float]:
    """Return (kelly_stake_pct_of_bankroll, units_dollars)."""
    full_k = kelly_fraction(fair_prob, odds)
    # Fractional Kelly + confidence weighting (cap)
    weighted = full_k * kelly_frac * (confidence / 100.0)
    # Hard cap at 5% of bankroll (anti-ruin)
    capped = min(weighted, 0.05)
    return round(capped * 100, 2), round(capped * bankroll, 2)


def risk_level(confidence: float, edge_pct: float, volatility: float) -> str:
    score = confidence * 0.5 + edge_pct * 2 - volatility * 30
    if score >= 50 and volatility <= 0.45:
        return "LOW"
    if score >= 30:
        return "MEDIUM"
    return "HIGH"
