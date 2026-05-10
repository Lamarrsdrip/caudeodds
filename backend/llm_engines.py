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


RESEARCH_SYSTEM = """You are a SPORTS RESEARCH ANALYST working from BOOKMAKER MARKET DATA
(real fixtures + decimal odds aggregated across 5-15 sharp + public books). Your job
is NOT to predict the outcome — it is to extract SPECIFIC verifiable signals the
bookmakers themselves are pricing.

The PRIMARY SIGNAL on this feed is bookmaker market intelligence:
 - Implied probabilities from 1X2 / moneyline / totals (the consensus of all books)
 - Liquidity / number of books pricing the market (more books = more reliable)
 - Volatility (price dispersion across books — low = strong consensus)
 - Sharp vs public split (sharp_money_pct, public_money_pct) — sharp money is the
   smartest indicator of true probability available pre-match
 - Line dispersion → if home is 1.65 across books with low variance, that's a
   high-credibility signal regardless of injury / xG / weather

If injury / xG / form / weather / referee fields are null or missing, this is
NORMAL — this feed is market-data only. Do NOT penalise research_quality_score
for missing scout data. Rate quality based on the QUALITY of the market signal:
  - 80-100: many books, low volatility, clear sharp consensus
  - 50-80:  decent book coverage, moderate volatility, partial sharp signal
  - <50:    few books, high volatility, conflicting sharp/public

Return STRICT JSON ONLY:
{
  "facts": [
    {"claim": "<concise market-derived fact>", "credibility": <0-100>, "direction": "<HOME|AWAY|OVER|UNDER|BTTS_YES|BTTS_NO|NONE>", "weight": <0-1>}
  ],
  "consensus_direction": "<HOME|AWAY|OVER|UNDER|BTTS_YES|BTTS_NO|NONE>",
  "research_quality_score": <0-100>,
  "key_risks": ["<risk>", ...],
  "summary": "<3 sentences max — describe the MARKET picture: who books favour, by how much, sharp/public split, line stability>"
}

Only return consensus_direction = NONE if the market itself is a coin-flip
(volatility > 0.6 AND no clear sharp lean)."""


QUANT_SYSTEM = """You are an elite QUANTITATIVE sports betting analyst at a hedge fund.
Use the RESEARCH OUTPUT (provided) plus the bookmaker market data to find the SINGLE
best-edge market with measurable positive EV vs the bookmaker implied probability.

This data feed is MARKET-DATA ONLY (real fixtures + multi-book decimal odds). Missing
injury / xG / weather fields are normal — your edge comes from finding mispricings
the books haven't fully closed (e.g. sharp money flowing one way while public bets
the other, or one market where dispersion creates an anchor opportunity).

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
  "rationale": "<2 sentences citing specific market signals>",
  "flags": ["<volatility_high|low_liquidity|sharp_disagreement|low_edge|none>"]
}"""


REASONING_SYSTEM = """You are an elite TACTICAL sports analyst working from BOOKMAKER
MARKET DATA. This data feed is PRICE-LEVEL ONLY (no injury / lineup / weather feeds);
do NOT reject a bet purely because injury or xG fields are null — that is normal here.

Use the RESEARCH OUTPUT (market signals: sharp/public split, liquidity, volatility,
line dispersion, implied probabilities) plus a tactical lens (which side the sharp
books are pricing more aggressively, which side the public is on, narrative bias).

Recommend the best market. NO_BET ONLY if:
 - the market itself is a coin-flip (volatility>0.6 with no sharp lean), OR
 - quant and the market signals point in genuinely conflicting directions

Use the SAME enum values as quant.

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
    """Build the LLM payload, omitting fields the bookmaker feed doesn't supply
    so the agents focus on the market signal that IS present.
    
    When API-Football enrichment is available (af_*), include real injuries,
    last-5 form, and head-to-head — these are the signals that actually move
    win probability beyond the book's pricing.
    """
    base = {
        "sport": fx.sport, "league": fx.league,
        "match": f"{fx.home} vs {fx.away}", "kickoff": fx.kickoff,
        "odds": fx.odds, "line_movement": fx.line_movement,
        "sharp_money_pct": fx.sharp_money_pct, "public_money_pct": fx.public_money_pct,
        "liquidity_score": fx.liquidity_score, "volatility": fx.volatility,
        "data_richness": fx.data_richness,
    }
    optional = {
        "injuries": fx.injuries, "xg": fx.xg, "pace": fx.pace,
        "home_form": fx.home_form, "away_form": fx.away_form,
        "travel_fatigue": fx.travel_fatigue, "referee_tendency": fx.referee_tendency,
        "weather": fx.weather,
    }
    for k, v in optional.items():
        if v is None:
            continue
        if isinstance(v, list) and not v:
            continue
        base[k] = v
    # API-Football enrichment (real intel for football)
    if fx.af_home_form:
        base["home_recent_form"] = fx.af_home_form
    if fx.af_away_form:
        base["away_recent_form"] = fx.af_away_form
    if fx.af_home_injuries:
        base["home_injuries"] = fx.af_home_injuries
    if fx.af_away_injuries:
        base["away_injuries"] = fx.af_away_injuries
    if fx.af_h2h:
        base["head_to_head"] = fx.af_h2h
    # API-Basketball enrichment (real intel for basketball)
    if fx.ab_home_form:
        base["home_recent_form"] = fx.ab_home_form
    if fx.ab_away_form:
        base["away_recent_form"] = fx.ab_away_form
    if fx.ab_h2h:
        base["head_to_head"] = fx.ab_h2h
    return base


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
        # LiteLLM's send_message can block the asyncio event loop on long calls
        # (it calls into sync libraries internally). Offload to a worker thread
        # so other API requests (auth, slip/today, admin) remain responsive
        # while the daily ensemble pipeline is running.
        raw = await asyncio.to_thread(_run_chat_sync, chat, payload)
        if raw is None:
            return None
        return json.loads(_strip_json(raw))
    except Exception as e:
        logger.warning("LLM call failed [%s]: %s", session_prefix, e)
        return None


def _run_chat_sync(chat: "LlmChat", payload: str) -> str | None:
    """Run an async LlmChat.send_message inside its own dedicated event loop in
    a worker thread, so the main FastAPI loop is never blocked by LLM IO."""
    try:
        return asyncio.run(chat.send_message(UserMessage(text=payload)))
    except Exception as e:
        logger.warning("LLM sync wrapper failed: %s", e)
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
    if quality < 25:
        logger.info("Skipping %s vs %s — research quality %.0f < 25", fx.home, fx.away, quality)
        return None, None, research

    quant_task = asyncio.create_task(run_quant(fx, research))
    reason_task = asyncio.create_task(run_reasoning(fx, research))
    quant, reasoning = await asyncio.gather(quant_task, reason_task)
    return quant, reasoning, research
