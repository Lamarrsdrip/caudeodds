"""LLM ensemble engines for CLAUDEODD.

Both Claude (tactical/contextual) and GPT (quantitative) analyze each fixture
INDEPENDENTLY in parallel. The consensus engine then checks if both models
lean toward the SAME SIDE (e.g., both pick HOME, both pick OVER, etc.) regardless
of which specific market they prefer. This catches genuine ensemble agreement
without requiring exact market-code matches.
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

# Side tokens used to compare which "direction" the two models lean
SIDE_TOKENS = ["HOME", "AWAY", "DRAW", "OVER", "UNDER", "BTTS_YES", "BTTS_NO", "NONE"]


QUANT_SYSTEM = """You are an elite QUANTITATIVE sports betting analyst at a hedge fund.
Your job: from match data, find the SINGLE best-edge market with measurable
positive expected value vs. bookmaker implied probability. NEVER invent stats
or contradict the input data. If no edge exists, return confidence < 50 and
expected_value near zero — that is correct (the system will skip the bet).

Available market enum values for "market" field (use EXACT strings):
1X2_HOME, 1X2_DRAW, 1X2_AWAY, DC_1X, DC_X2, DC_12,
DNB_HOME, DNB_AWAY, OU_2_5_OVER, OU_2_5_UNDER,
BTTS_YES, BTTS_NO, AH_HOME_-0.5, AH_AWAY_+0.5,
ML_HOME, ML_AWAY, SPREAD_HOME, SPREAD_AWAY,
TOTAL_OVER, TOTAL_UNDER, TEAM_TOTAL_HOME_OVER, TEAM_TOTAL_HOME_UNDER

Return STRICT JSON ONLY (no markdown):
{
  "market": "<enum>",
  "selection_label": "<human readable>",
  "fair_prob": <float 0-1>,
  "book_implied_prob": <float 0-1>,
  "expected_value": <float, can be negative>,
  "confidence": <float 0-100>,
  "edge_pct": <float, may be negative>,
  "rationale": "<2 sentences max, factual>",
  "flags": ["<volatility_high|low_liquidity|sharp_disagreement|low_edge|none>"]
}"""


REASONING_SYSTEM = """You are an elite TACTICAL sports analyst.
Independently analyze the fixture using tactical reasoning: coach matchups,
momentum, injuries, narrative risk (revenge, dead rubbers), referee, weather,
fatigue, public bias. Identify the market most aligned with tactical reality.

You are SKEPTICAL but constructive. Recommend a market only when tactics
clearly favor one side. If unclear, set tactical_confidence < 50 and
narrative_risk > 60.

Use the SAME enum values for "recommended_market" as the quant analyst:
1X2_HOME, 1X2_DRAW, 1X2_AWAY, DC_1X, DC_X2, DC_12, DNB_HOME, DNB_AWAY,
OU_2_5_OVER, OU_2_5_UNDER, BTTS_YES, BTTS_NO, AH_HOME_-0.5, AH_AWAY_+0.5,
ML_HOME, ML_AWAY, SPREAD_HOME, SPREAD_AWAY, TOTAL_OVER, TOTAL_UNDER,
TEAM_TOTAL_HOME_OVER, TEAM_TOTAL_HOME_UNDER, NO_BET

Return STRICT JSON ONLY:
{
  "agrees_with_quant": <true|false — set true if your recommended_market shares the same SIDE (HOME/AWAY/OVER/UNDER/BTTS_YES/BTTS_NO) as the quant pick provided>,
  "recommended_market": "<enum>",
  "tactical_confidence": <float 0-100>,
  "narrative_risk": <float 0-100>,
  "key_factors": ["<bullet>", "<bullet>"],
  "red_flags": ["<flag>"],
  "reasoning": "<2-3 sentences>"
}"""


def _strip_json(s: str) -> str:
    s = s.strip()
    s = re.sub(r"^```(?:json)?\s*", "", s)
    s = re.sub(r"\s*```$", "", s)
    start = s.find("{")
    end = s.rfind("}")
    if start != -1 and end != -1:
        return s[start:end + 1]
    return s


def market_to_side(market: str) -> str:
    """Canonicalize a market to a SIDE token for ensemble comparison."""
    m = (market or "").upper().replace("-", "_").replace(".", "_")
    if "OVER" in m: return "OVER"
    if "UNDER" in m: return "UNDER"
    if "BTTS_YES" in m: return "BTTS_YES"
    if "BTTS_NO" in m: return "BTTS_NO"
    if "DRAW" in m or m.endswith("_X") or m == "1X2_DRAW": return "DRAW"
    if "AWAY" in m or m.endswith("_2") or m == "DC_X2": return "AWAY"
    if "HOME" in m or m.endswith("_1") or m == "DC_1X": return "HOME"
    if m == "DC_12": return "HOME"  # closer to home leaning, treat as ambiguous-home
    return "NONE"


def _fixture_payload(fx: Fixture) -> dict:
    return {
        "sport": fx.sport,
        "league": fx.league,
        "match": f"{fx.home} vs {fx.away}",
        "kickoff": fx.kickoff,
        "odds": fx.odds,
        "line_movement": fx.line_movement,
        "sharp_money_pct": fx.sharp_money_pct,
        "public_money_pct": fx.public_money_pct,
        "liquidity_score": fx.liquidity_score,
        "volatility": fx.volatility,
        "injuries": fx.injuries,
        "xg": fx.xg,
        "pace": fx.pace,
        "home_form": fx.home_form,
        "away_form": fx.away_form,
        "travel_fatigue": fx.travel_fatigue,
        "referee_tendency": fx.referee_tendency,
        "weather": fx.weather,
    }


async def run_quant(fx: Fixture) -> QuantOutput | None:
    if not EMERGENT_KEY:
        logger.error("EMERGENT_LLM_KEY missing")
        return None
    chat = LlmChat(
        api_key=EMERGENT_KEY,
        session_id=f"quant-{fx.id}-{uuid.uuid4().hex[:6]}",
        system_message=QUANT_SYSTEM,
    ).with_model(*GPT_MODEL)
    payload = json.dumps(_fixture_payload(fx), indent=2)
    msg = UserMessage(text=f"Analyze this fixture quantitatively. JSON only.\n\n{payload}")
    try:
        raw = await chat.send_message(msg)
        return QuantOutput(**json.loads(_strip_json(raw)))
    except Exception as e:
        logger.warning("Quant LLM failed for %s vs %s: %s", fx.home, fx.away, e)
        return None


async def run_reasoning(fx: Fixture) -> ReasoningOutput | None:
    if not EMERGENT_KEY:
        return None
    chat = LlmChat(
        api_key=EMERGENT_KEY,
        session_id=f"reason-{fx.id}-{uuid.uuid4().hex[:6]}",
        system_message=REASONING_SYSTEM,
    ).with_model(*CLAUDE_MODEL)
    payload = json.dumps(_fixture_payload(fx), indent=2)
    msg = UserMessage(text=(
        "Analyze this fixture tactically and recommend the best market. "
        "Set agrees_with_quant=true (the quant pick will be cross-checked by side direction). "
        "JSON only.\n\n" + payload
    ))
    try:
        raw = await chat.send_message(msg)
        data = json.loads(_strip_json(raw))
        # Normalize: ensure "agrees_with_quant" exists (default true; consensus checks side)
        if "agrees_with_quant" not in data:
            data["agrees_with_quant"] = True
        return ReasoningOutput(**data)
    except Exception as e:
        logger.warning("Reasoning LLM failed for %s vs %s: %s", fx.home, fx.away, e)
        return None


async def run_ensemble(fx: Fixture) -> tuple[QuantOutput | None, ReasoningOutput | None]:
    """Run both models in parallel for true independent analysis."""
    return await asyncio.gather(run_quant(fx), run_reasoning(fx))
