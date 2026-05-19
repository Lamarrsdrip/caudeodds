import os

import pytest

pytest.importorskip("emergentintegrations")

from consensus import evaluate
from llm_engines import _api_key, set_runtime_config
from models import Fixture, QuantOutput, ReasoningOutput, Settings


def _fixture(**overrides):
    base = {
        "sport": "football",
        "league": "Premier League",
        "home": "Home FC",
        "away": "Away FC",
        "kickoff": "2026-05-19T18:00:00Z",
        "odds": {
            "1X2": {"home": 1.70, "draw": 3.50, "away": 4.60},
            "DC": {"1X": 1.24, "X2": 2.10, "12": 1.30},
            "DNB": {"home": 1.32, "away": 2.80},
        },
        "line_movement": {"delta_pct": 0},
        "sharp_money_pct": {"home": 72, "away": 28},
        "public_money_pct": {"home": 54, "away": 46},
        "liquidity_score": 0.90,
        "volatility": 0.12,
        "injuries": [],
        "data_richness": 0.0,
    }
    base.update(overrides)
    return Fixture(**base)


def test_llm_runtime_config_uses_admin_key_when_env_missing(monkeypatch):
    monkeypatch.delenv("EMERGENT_LLM_KEY", raising=False)
    set_runtime_config("admin-runtime-key")
    assert _api_key() == "admin-runtime-key"
    set_runtime_config("")


def test_llm_runtime_config_falls_back_to_environment(monkeypatch):
    set_runtime_config("")
    monkeypatch.setenv("EMERGENT_LLM_KEY", "env-key")
    assert _api_key() == "env-key"


def test_strong_market_only_fixture_can_publish_without_fake_intel():
    fx = _fixture()
    quant = QuantOutput(
        market="DNB_HOME",
        selection_label="Draw No Bet - Home",
        fair_prob=0.80,
        book_implied_prob=1 / 1.32,
        expected_value=0.05,
        confidence=76,
        edge_pct=4.0,
        rationale="Stable market, strong sharp lean, low volatility.",
        flags=["none"],
    )
    reasoning = ReasoningOutput(
        agrees_with_quant=True,
        recommended_market="DNB_HOME",
        tactical_confidence=73,
        narrative_risk=30,
        reasoning="Market is clean enough for a protected home-side leg.",
    )
    pick, rej = evaluate(fx, quant, reasoning, Settings(), "2026-05-19", research={
        "research_quality_score": 78,
        "consensus_direction": "HOME",
    })
    assert rej is None
    assert pick is not None
    assert "Market-intel mode" in pick.reasoning


def test_weak_market_only_fixture_is_rejected():
    fx = _fixture(liquidity_score=0.52, volatility=0.58, sharp_money_pct={"home": 54, "away": 46})
    quant = QuantOutput(
        market="DNB_HOME",
        selection_label="Draw No Bet - Home",
        fair_prob=0.80,
        book_implied_prob=1 / 1.32,
        expected_value=0.05,
        confidence=78,
        edge_pct=4.0,
        rationale="Weak market.",
        flags=["none"],
    )
    reasoning = ReasoningOutput(
        agrees_with_quant=True,
        recommended_market="DNB_HOME",
        tactical_confidence=74,
        narrative_risk=30,
        reasoning="Weak market-only signal.",
    )
    pick, rej = evaluate(fx, quant, reasoning, Settings(), "2026-05-19", research={
        "research_quality_score": 55,
        "consensus_direction": "HOME",
    })
    assert pick is None
    assert rej.reason_code == "DATA_TOO_WEAK"
