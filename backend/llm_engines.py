"""LLM ensemble engines for ClaudeOdd — Anthropic Skills-style 3-agent pipeline.

Pipeline (per fixture):
  1. RESEARCH agent (Claude)  — synthesises specific verifiable facts from the
     fixture data (recent form, head-to-head, injuries impact, line moves) and
     scores their credibility. Forces evidence-first, not vibes.
  2. QUANT agent (GPT-4o-mini) — uses the research output + raw fixture data
     to compute fair_prob, EV, edge for the highest-EV market.
  3. TACTICAL agent (Claude)  — independently picks its best market based on
     research + tactical lens.

Consensus: side-direction match between QUANT and TACTICAL must hold. Research
quality_score also gates final approval (low-research-quality fixtures are
rejected upfront).

Inspired by Anthropic's Prediction Market Skill framework (Scan → Research →
Predict → Risk → Execute → Compound).
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import uuid

from emergentintegrations.llm.chat import LlmChat, UserMessage

from models import Fixture, QuantOutput, ReasoningOutput

logger = logging.getLogger("claudeodd.llm")

EMERGENT_KEY = os.environ.get("EMERGENT_LLM_KEY", "")

GPT_MODEL = ("openai", "gpt-4o-mini")
CLAUDE_MODEL = ("anthropic", "claude-haiku-4-5-20251001")


RESEARCH_SYSTEM = """You are a SPORTS RESEARCH ANALYST. Your job is NOT to predict
the outcome — it is to extract and synthesise SPECIFIC verifiable facts from the
fixture data that a betting analyst can rely on. You are evidence-first.

Process:
1. Parse the fixture data carefully (odds, line movement, sharp_money_pct,
   public_money_pct, injuries, form, xg, pace, fatigue, referee, weather).
2. Identify FACTS that materially shift true probability.
3. For each fact, score its credibility (0-100) and impact direction (HOME, AWAY, OVER, UNDER, BTTS_YES, BTTS_NO, NONE).
4. Compute a research_quality_score (0-100) — high if you found multiple
   high-credibility, non-conflicting facts; low if data is sparse or facts
   conflict.

Return STRICT JSON ONLY:
{
  "facts": [
    {"claim": "<concise fact>", "credibility": <0-100>, "direction": "<HOME|AWAY|OVER|UNDER|BTTS_YES|BTTS_NO|NONE>", "weight": <0-1>}
  ],
  "consensus_direction": "<HOME|AWAY|OVER|UNDER|BTTS_YES|BTTS_NO|NONE>",
  "research_quality_score": <0-100>,
  "key_risks": ["<risk>", ...],
  "summary": "<3 sentences max>"
}

If the data is too thin to find ANY high-credibility facts, set
research_quality_score < 40 and consensus_direction = "NONE"."""


QUANT_SYSTEM = """You are an elite QUANTITATIVE sports betting analyst at a hedge fund.
Use the RESEARCH OUTPUT (provided) plus the raw fixture data to find the SINGLE
best-edge market with measurable positive EV vs bookmaker implied probability.

NEVER invent stats or contradict the research. If research_quality_score < 50,
reduce confidence and flag low_edge.

Available market enum values for "market":
1X2_HOME, 1X2_DRAW, 1X2_AWAY, DC_1X, DC_X2, DC_12,
DNB_HOME, DNB_AWAY, OU_2_5_OVER, OU_2_5_UNDER,
BTTS_YES, BTTS_NO, AH_HOME_-0.5, AH_AWAY_+0.5,
ML_HOME, ML_AWAY, SPREAD_HOME, SPREAD_AWAY,
TOTAL_OVER, TOTAL_UNDER, TEAM_TOTAL_HOME_OVER, TEAM_TOTAL_HOME_UNDER

Return STRICT JSON ONLY:
{
  "market": "<enum>",
  "selection_label": "<human readable>",
  "fair_prob": <float 0-1>,
  "book_implied_prob": <float 0-1>,
  "expected_value": <float>,
  "confidence": <float 0-100>,
  "edge_pct": <float>,
  "rationale": "<2 sentences citing specific research facts>",
  "flags": ["<volatility_high|low_liquidity|sharp_disagreement|low_edge|none>"]
}"""


REASONING_SYSTEM = """You are an elite TACTICAL sports analyst.
Use the RESEARCH OUTPUT (provided) plus tactical lens (coach matchups, momentum,
narrative risk, referee, weather, fatigue, public bias) to recommend the best
market. You are SKEPTICAL but constructive.

Use the SAME enum values as quant. NO_BET if no edge.

Return STRICT JSON ONLY:
{
  "agrees_with_quant": true,
  "recommended_market": "<enum or NO_BET>",
  "tactical_confidence": <float 0-100>,
  "narrative_risk": <float 0-100>,
  "key_factors": ["<bullet>", "<bullet>"],
  "red_flags": ["<flag>"],
  "reasoning": "<2-3 sentences>"
}"""


SIDE_TOKENS = ["HOME", "AWAY", "DRAW", "OVER", "UNDER", "BTTS_YES", "BTTS_NO", "NONE"]


def market_to_side(market: str) -> str:
    m = (market or "").upper().replace("-", "_").replace(".", "_")
    if "OVER" in m: return "OVER"
    if "UNDER" in m: return "UNDER"
    if "BTTS_YES" in m: return "BTTS_YES"
    if "BTTS_NO" in m: return "BTTS_NO"
    if "DRAW" in m or m == "1X2_DRAW": return "DRAW"
    if "AWAY" in m or m == "DC_X2": return "AWAY"
    if "HOME" in m or m == "DC_1X": return "HOME"
    if m == "DC_12": return "HOME"
    return "NONE"


def _strip_json(s: str) -> str:
    s = s.strip()
    s = re.sub(r"^```(?:json)?\s*", "", s)
    s = re.sub(r"\s*```$", "", s)
    start = s.find("{")
    end = s.rfind("}")
    if start != -1 and end != -1:
        return s[start:end + 1]
    return s


def _fixture_payload(fx: Fixture) -> dict:
    return {
        "sport": fx.sport, "league": fx.league,
        "match": f"{fx.home} vs {fx.away}", "kickoff": fx.kickoff,
        "odds": fx.odds, "line_movement": fx.line_movement,
        "sharp_money_pct": fx.sharp_money_pct, "public_money_pct": fx.public_money_pct,
        "liquidity_score": fx.liquidity_score, "volatility": fx.volatility,
        "injuries": fx.injuries, "xg": fx.xg, "pace": fx.pace,
        "home_form": fx.home_form, "away_form": fx.away_form,
        "travel_fatigue": fx.travel_fatigue, "referee_tendency": fx.referee_tendency,
        "weather": fx.weather,
    }


async def _llm(model_provider: tuple, system: str, payload: str, session_prefix: str, fx_id: str) -> dict | None:
    if not EMERGENT_KEY:
        logger.error("EMERGENT_LLM_KEY missing")
        return None
    chat = LlmChat(
        api_key=EMERGENT_KEY,
        session_id=f"{session_prefix}-{fx_id}-{uuid.uuid4().hex[:6]}",
        system_message=system,
    ).with_model(*model_provider)
    try:
        raw = await chat.send_message(UserMessage(text=payload))
        return json.loads(_strip_json(raw))
    except Exception as e:
        logger.warning("LLM call failed [%s]: %s", session_prefix, e)
        return None


async def run_research(fx: Fixture) -> dict | None:
    payload = "Analyze this fixture. Return research JSON only.\n\n" + json.dumps(_fixture_payload(fx), indent=2)
    return await _llm(CLAUDE_MODEL, RESEARCH_SYSTEM, payload, "research", fx.id)


async def run_quant(fx: Fixture, research: dict) -> QuantOutput | None:
    body = {"fixture": _fixture_payload(fx), "research": research}
    payload = "Use the research evidence to find the highest-EV market. JSON only.\n\n" + json.dumps(body, indent=2)
    data = await _llm(GPT_MODEL, QUANT_SYSTEM, payload, "quant", fx.id)
    if data is None:
        return None
    try:
        return QuantOutput(**data)
    except Exception as e:
        logger.warning("Quant parse failed: %s", e)
        return None


async def run_reasoning(fx: Fixture, research: dict) -> ReasoningOutput | None:
    body = {"fixture": _fixture_payload(fx), "research": research}
    payload = "Use the research evidence + tactical lens. Recommend best market. JSON only.\n\n" + json.dumps(body, indent=2)
    data = await _llm(CLAUDE_MODEL, REASONING_SYSTEM, payload, "reason", fx.id)
    if data is None:
        return None
    if "agrees_with_quant" not in data:
        data["agrees_with_quant"] = True
    try:
        return ReasoningOutput(**data)
    except Exception as e:
        logger.warning("Reasoning parse failed: %s", e)
        return None


async def run_ensemble(fx: Fixture) -> tuple[QuantOutput | None, ReasoningOutput | None, dict | None]:
    """Pipeline: Research → (Quant ∥ Reasoning).

    Returns (quant, reasoning, research). The research dict carries
    research_quality_score + consensus_direction used by the consensus engine
    as an additional gate.
    """
    research = await run_research(fx)
    if research is None:
        return None, None, None
    quality = float(research.get("research_quality_score", 0))
    if quality < 35:
        logger.info("Skipping %s vs %s — research quality %.0f < 35", fx.home, fx.away, quality)
        return None, None, research

    quant_task = asyncio.create_task(run_quant(fx, research))
    reason_task = asyncio.create_task(run_reasoning(fx, research))
    quant, reasoning = await asyncio.gather(quant_task, reason_task)
    return quant, reasoning, research
