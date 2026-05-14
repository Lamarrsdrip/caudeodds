import pytest

pytest.importorskip("emergentintegrations")

from consensus import evaluate
from filters import filter_fixtures
from models import Fixture, Settings


def _fixture(**overrides):
    base = {
        "sport": "football",
        "league": "Premier League",
        "home": "Home FC",
        "away": "Away FC",
        "kickoff": "2026-05-14T18:00:00Z",
        "odds": {"1X2": {"home": 2.0, "draw": 3.2, "away": 3.5}},
        "line_movement": {"delta_pct": 0},
        "sharp_money_pct": {"home": 52, "away": 48},
        "public_money_pct": {"home": 50, "away": 50},
        "liquidity_score": 0.8,
        "volatility": 0.2,
        "injuries": [],
    }
    base.update(overrides)
    return Fixture(**base)


def test_low_research_rejects_before_models():
    _, rej = evaluate(
        _fixture(),
        None,
        None,
        Settings(),
        "2026-05-14",
        research={"research_quality_score": 49},
    )
    assert rej.reason_code == "LOW_RESEARCH"


def test_filter_counts_real_api_football_injuries():
    fixture = _fixture(
        af_home_injuries=[{"player": "A"}, {"player": "B"}],
        af_away_injuries=[{"player": "C"}, {"player": "D"}],
    )
    kept, rejected = filter_fixtures([fixture], "2026-05-14")
    assert kept == []
    assert rejected[0].reason_code == "INJURY_CHAOS"
