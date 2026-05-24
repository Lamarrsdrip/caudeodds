"""Pydantic models for CLAUDEODD."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field
import uuid


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class Fixture(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    sport: Literal["football", "basketball"]
    league: str
    home: str
    away: str
    kickoff: str
    odds: dict
    line_movement: dict
    sharp_money_pct: dict
    public_money_pct: dict
    liquidity_score: float
    volatility: float
    injuries: List[str] = []
    notes: Optional[str] = None
    xg: Optional[dict] = None
    pace: Optional[dict] = None
    home_form: Optional[List[str]] = None
    away_form: Optional[List[str]] = None
    travel_fatigue: Optional[dict] = None
    referee_tendency: Optional[str] = None
    weather: Optional[str] = None
    # API-Football enrichment (real data — football)
    af_home_form: Optional[dict] = None  # {wins,draws,losses,goals_for,goals_against,ppg,form_string}
    af_away_form: Optional[dict] = None
    af_home_injuries: Optional[List[dict]] = None  # [{player, type, reason}]
    af_away_injuries: Optional[List[dict]] = None
    af_h2h: Optional[dict] = None
    # API-Basketball enrichment (real data — basketball)
    ab_home_form: Optional[dict] = None  # {wins,losses,pts_for,pts_against,win_pct,form_string}
    ab_away_form: Optional[dict] = None
    ab_h2h: Optional[dict] = None
    data_richness: float = 0.0  # 0-1 score of how much real intel we have


class QuantOutput(BaseModel):
    model_config = ConfigDict(extra="ignore")
    market: str
    selection_label: str
    fair_prob: float
    book_implied_prob: float
    expected_value: float
    confidence: float
    edge_pct: float
    rationale: str
    flags: List[str] = []


class ReasoningOutput(BaseModel):
    """Reasoning agent independently picks a market AND notes if it agrees with quant."""
    model_config = ConfigDict(extra="ignore")
    agrees_with_quant: bool = True
    recommended_market: str = "NO_BET"
    tactical_confidence: float = 0.0
    narrative_risk: float = 50.0
    key_factors: List[str] = []
    red_flags: List[str] = []
    reasoning: str = ""


class Pick(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    date: str
    sport: str
    league: str
    match: str
    kickoff: str
    market: str
    selection_label: str
    odds: float
    market_line: Optional[float] = None
    confidence: float
    agreement: float
    expected_value: float
    edge_pct: float
    risk_level: Literal["LOW", "MEDIUM", "HIGH"]
    kelly_stake_pct: float
    stake_units: float
    reasoning: str
    quant_view: QuantOutput
    reasoning_view: ReasoningOutput
    data_richness: float = 0.0
    status: Literal["pending", "won", "lost", "void"] = "pending"
    settled_at: Optional[str] = None
    created_at: str = Field(default_factory=utcnow_iso)


class RejectionLog(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    date: str
    match: str
    sport: str
    reason_code: str
    reason: str
    created_at: str = Field(default_factory=utcnow_iso)


class Settings(BaseModel):
    model_config = ConfigDict(extra="ignore")
    bankroll: float = 1000.0
    kelly_fraction: float = 0.25
    max_picks_per_day: int = 24  # candidate board size; the official slip is capped separately at 5 legs
    min_confidence: float = 68.0
    min_agreement: float = 62.0
    min_ev: float = 0.035
    sport_filter: Literal["all", "football", "basketball"] = "all"
    updated_at: str = Field(default_factory=utcnow_iso)


class SettlePayload(BaseModel):
    result: Literal["won", "lost", "void"]


class GenerateResponse(BaseModel):
    date: str
    picks: List[Pick]
    rejected_count: int
    fixtures_analyzed: int
    cached: bool
