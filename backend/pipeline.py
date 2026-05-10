"""Daily orchestration pipeline for CLAUDEODD."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import List, Tuple

from consensus import evaluate, select_top
from data_engine import generate_fixtures_for_date_async
from filters import filter_fixtures
from llm_engines import run_ensemble
from models import Pick, RejectionLog, Settings

logger = logging.getLogger("claudeodd.pipeline")


def today_str() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


async def run_pipeline(date_str: str, settings: Settings) -> Tuple[List[Pick], List[RejectionLog], int]:
    fixtures = await generate_fixtures_for_date_async(date_str)
    if settings.sport_filter != "all":
        fixtures = [f for f in fixtures if f.sport == settings.sport_filter]
    total_fixtures = len(fixtures)

    kept, rejections = filter_fixtures(fixtures, date_str)
    logger.info("Filter kept %d / %d fixtures for %s", len(kept), total_fixtures, date_str)

    # Run ensemble concurrently across kept fixtures
    sem = asyncio.Semaphore(12)  # bump from 6 → 12: same total LLM credit, half wall-time

    async def analyze(fx):
        async with sem:
            return fx, await run_ensemble(fx)

    results = await asyncio.gather(*[analyze(fx) for fx in kept])

    candidate_picks: List[Pick] = []
    for fx, (q, r, research) in results:
        pick, rej = evaluate(fx, q, r, settings, date_str, research=research)
        if pick is not None:
            candidate_picks.append(pick)
        elif rej is not None:
            rejections.append(rej)

    top_picks = select_top(candidate_picks, settings.max_picks_per_day)
    # Picks not chosen go to rejection log
    chosen_ids = {p.id for p in top_picks}
    for p in candidate_picks:
        if p.id not in chosen_ids:
            rejections.append(RejectionLog(
                date=date_str, match=p.match, sport=p.sport,
                reason_code="OUTRANKED",
                reason=f"Conf {p.confidence:.0f}% / EV {p.expected_value:.3f} — better picks selected",
            ))

    return top_picks, rejections, total_fixtures
