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
    max_picks_per_day: int = 8  # generate more candidates so slip-builder can pack 3-5 highest-conf
    min_confidence: float = 60.0
    min_agreement: float = 55.0
    min_ev: float = 0.02
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
