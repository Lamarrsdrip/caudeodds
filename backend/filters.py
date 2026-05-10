"""NO BAD BETS ultra-filter for CLAUDEODD.

Pre-LLM filter: removes obviously unprofitable / risky fixtures to save tokens
and enforce discipline. Returns (kept_fixtures, rejection_log_entries).
"""
from __future__ import annotations

from typing import List, Tuple

from models import Fixture, RejectionLog


def _check(fx: Fixture, date_str: str) -> Tuple[bool, str | None, str | None]:
    """Returns (keep, reason_code, reason_text)."""
    # 1. Liquidity (low books are risky)
    if fx.liquidity_score < 0.45:
        return False, "LOW_LIQ", f"Liquidity score {fx.liquidity_score:.2f} < 0.45 — thin market"

    # 2. Volatility (suspicious uncertainty)
    if fx.volatility > 0.85:
        return False, "VOLATILITY", f"Volatility {fx.volatility:.2f} above threshold — unstable market"

    # 3. Suspicious line movement (very large move w/ low liquidity)
    delta = abs(fx.line_movement.get("delta_pct", 0))
    if delta > 10.0 and fx.liquidity_score < 0.70:
        return False, "TRAP", f"Line moved {delta:.1f}% on thin book — possible trap"

    # 4. Injury chaos: 4+ injuries combined
    if len(fx.injuries) >= 4:
        return False, "INJURY_CHAOS", f"{len(fx.injuries)} key injuries — too many unknowns"

    # 5. Conflicting public vs sharp signal too extreme
    sharp_home = fx.sharp_money_pct.get("home", 50)
    public_home = fx.public_money_pct.get("home", 50)
    conflict = abs(sharp_home - public_home)
    if conflict > 50 and fx.volatility > 0.70:
        return False, "CONFLICT", (
            f"Sharp {sharp_home}% vs Public {public_home}% conflict at high volatility"
        )

    # 6. Hyped public trap: extreme public side
    if public_home > 85 or public_home < 15:
        return False, "TRAP", f"Public extreme {public_home}% — heavy bias risk"

    return True, None, None


def filter_fixtures(fixtures: List[Fixture], date_str: str) -> Tuple[List[Fixture], List[RejectionLog]]:
    kept: List[Fixture] = []
    rejected: List[RejectionLog] = []
    for fx in fixtures:
        keep, code, reason = _check(fx, date_str)
        if keep:
            kept.append(fx)
        else:
            rejected.append(RejectionLog(
                date=date_str,
                match=f"{fx.home} vs {fx.away}",
                sport=fx.sport,
                reason_code=code or "FILTERED",
                reason=reason or "Filtered by ultra-filter",
            ))
    return kept, rejected
