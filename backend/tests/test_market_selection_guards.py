import pytest

pytest.importorskip("emergentintegrations")

from consensus import evaluate
from models import Fixture, QuantOutput, ReasoningOutput, Settings
from slip_builder import build_slip


def _fixture(**overrides):
    base = {
        "sport": "football",
        "league": "Premier League",
        "home": "Home FC",
        "away": "Away FC",
        "kickoff": "2026-05-24T18:00:00Z",
        "odds": {
            "1X2": {"home": 1.62, "draw": 3.80, "away": 5.20},
            "DC": {"1X": 1.22, "X2": 2.35, "12": 1.28},
            "DNB": {"home": 1.38, "away": 3.10},
            "OU_2_5": {"over": 1.72, "under": 1.96, "line": 2.5},
        },
        "line_movement": {"delta_pct": 0},
        "sharp_money_pct": {"home": 70, "away": 30, "over": 62, "under": 38},
        "public_money_pct": {"home": 55, "away": 45},
        "liquidity_score": 0.92,
        "volatility": 0.10,
        "injuries": [],
        "data_richness": 0.55,
    }
    base.update(overrides)
    return Fixture(**base)


def _quant(market, **overrides):
    base = {
        "market": market,
        "selection_label": market,
        "fair_prob": 0.83,
        "book_implied_prob": 0.61,
        "expected_value": 0.08,
        "confidence": 80,
        "edge_pct": 4.0,
        "rationale": "Stable market, strong sharp support.",
        "flags": ["none"],
    }
    base.update(overrides)
    return QuantOutput(**base)


def _reasoning(market, **overrides):
    base = {
        "recommended_market": market,
        "tactical_confidence": 78,
        "narrative_risk": 25,
        "reasoning": "The tactical read agrees with the market direction.",
    }
    base.update(overrides)
    return ReasoningOutput(**base)


def test_football_straight_home_is_normalized_to_draw_cover_market():
    fx = _fixture()
    pick, rej = evaluate(
        fx,
        _quant("1X2_HOME"),
        _reasoning("1X2_HOME"),
        Settings(),
        "2026-05-24",
        research={"research_quality_score": 80, "consensus_direction": "HOME"},
    )
    assert rej is None
    assert pick is not None
    assert pick.market == "DC_1X"
    assert pick.odds == 1.22


def test_dnb_request_is_normalized_to_true_win_or_draw_market():
    fx = _fixture()
    pick, rej = evaluate(
        fx,
        _quant("DNB_HOME", fair_prob=0.70),
        _reasoning("DNB_HOME"),
        Settings(),
        "2026-05-24",
        research={"research_quality_score": 80, "consensus_direction": "HOME"},
    )
    assert rej is None
    assert pick is not None
    assert pick.market == "DC_1X"
    assert pick.selection_label == "Home Win or Draw"


def test_basketball_football_market_is_translated_to_moneyline():
    fx = _fixture(
        sport="basketball",
        league="NBA",
        odds={
            "ML": {"home": 1.44, "away": 2.75},
            "SPREAD": {"line": 4.5, "home": 1.91, "away": 1.91},
            "TOTAL": {"line": 220.5, "over": 1.88, "under": 1.92},
        },
        sharp_money_pct={"home": 68, "away": 32, "over": 60, "under": 40},
    )
    pick, rej = evaluate(
        fx,
        _quant("1X2_HOME", book_implied_prob=1 / 1.44),
        _reasoning("1X2_HOME"),
        Settings(),
        "2026-05-24",
        research={"research_quality_score": 82, "consensus_direction": "HOME"},
    )
    assert rej is None
    assert pick is not None
    assert pick.market == "ML_HOME"
    assert pick.odds == 1.44


def test_basketball_over_under_uses_total_market():
    fx = _fixture(
        sport="basketball",
        league="NBA",
        odds={
            "ML": {"home": 1.70, "away": 2.12},
            "SPREAD": {"line": 4.5, "home": 1.91, "away": 1.91},
            "TOTAL": {"line": 220.5, "over": 1.88, "under": 1.92},
        },
        sharp_money_pct={"home": 52, "away": 48, "over": 66, "under": 34},
    )
    pick, rej = evaluate(
        fx,
        _quant("OU_2_5_OVER", fair_prob=0.58, book_implied_prob=1 / 1.88),
        _reasoning("OU_2_5_OVER"),
        Settings(),
        "2026-05-24",
        research={"research_quality_score": 82, "consensus_direction": "OVER"},
    )
    assert rej is None
    assert pick is not None
    assert pick.market == "TOTAL_OVER"
    assert pick.market_line == 220.5
    assert pick.selection_label == "Basketball Total Over 220.5"


def test_slip_builder_prefers_close_quality_market_and_sport_mix():
    football = evaluate(
        _fixture(home="A", away="B"),
        _quant("1X2_HOME", confidence=79),
        _reasoning("1X2_HOME", tactical_confidence=77),
        Settings(),
        "2026-05-24",
        research={"research_quality_score": 80, "consensus_direction": "HOME"},
    )[0]
    basketball = evaluate(
        _fixture(
            sport="basketball",
            league="NBA",
            home="C",
            away="D",
            odds={
                "ML": {"home": 1.48, "away": 2.55},
                "SPREAD": {"line": 4.5, "home": 1.91, "away": 1.91},
                "TOTAL": {"line": 220.5, "over": 1.86, "under": 1.94},
            },
            sharp_money_pct={"home": 66, "away": 34},
        ),
        _quant("1X2_HOME", confidence=78, book_implied_prob=1 / 1.48),
        _reasoning("1X2_HOME", tactical_confidence=76),
        Settings(),
        "2026-05-24",
        research={"research_quality_score": 82, "consensus_direction": "HOME"},
    )[0]
    total = evaluate(
        _fixture(home="E", away="F"),
        _quant("OU_2_5_OVER", fair_prob=0.62, book_implied_prob=1 / 1.72, confidence=77),
        _reasoning("OU_2_5_OVER", tactical_confidence=76),
        Settings(),
        "2026-05-24",
        research={"research_quality_score": 78, "consensus_direction": "OVER"},
    )[0]
    slip = build_slip("2026-05-24", [football, basketball, total])
    assert slip is not None
    assert {leg.sport for leg in slip.legs} == {"football", "basketball"}
    assert len({leg.market.split("_")[0] for leg in slip.legs}) >= 2
    assert any(leg.market == "OU_2_5_OVER" and leg.market_line == 2.5 for leg in slip.legs)
