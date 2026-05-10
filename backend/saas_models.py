"""Auth + subscription + admin Pydantic models for CLAUDEODD SaaS."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field
import uuid


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class RegisterPayload(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    name: str = Field(min_length=1, max_length=80)
    dob: Optional[str] = None  # YYYY-MM-DD
    age_18_plus: bool
    accept_terms: bool


class LoginPayload(BaseModel):
    email: EmailStr
    password: str


class UserPublic(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    email: EmailStr
    name: str
    role: Literal["user", "admin"] = "user"
    dob: Optional[str] = None
    created_at: str
    subscription_status: Literal["trial", "active", "expired", "none"] = "none"
    trial_ends_at: Optional[str] = None
    subscription_ends_at: Optional[str] = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserPublic


class Subscription(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    plan: Literal["monthly", "trial"] = "trial"
    status: Literal["trial", "active", "expired", "cancelled"] = "trial"
    started_at: str = Field(default_factory=utcnow_iso)
    ends_at: str
    last_payment_id: Optional[str] = None


class PaymentInitPayload(BaseModel):
    plan: Literal["monthly"] = "monthly"
    method: Literal["flutterwave", "bank_transfer"] = "flutterwave"


class BankTransferProofPayload(BaseModel):
    amount: float
    reference: str  # the transfer reference / narration
    sender_name: str
    proof_data_url: str  # base64 dataURL of receipt screenshot


class Payment(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    user_email: str
    amount: float
    currency: str = "NGN"
    method: Literal["flutterwave", "bank_transfer"] = "flutterwave"
    status: Literal["pending", "successful", "failed", "rejected"] = "pending"
    tx_ref: Optional[str] = None
    flutterwave_id: Optional[str] = None
    flutterwave_link: Optional[str] = None
    proof_data_url: Optional[str] = None
    sender_name: Optional[str] = None
    reference: Optional[str] = None
    admin_note: Optional[str] = None
    created_at: str = Field(default_factory=utcnow_iso)
    updated_at: str = Field(default_factory=utcnow_iso)


class AdminConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")
    # Pricing
    price_ngn: float = 5000.0
    plan_label: str = "VIP Daily Slip"
    trial_days: int = 3
    # Bank transfer
    bank_name: str = ""
    bank_account_number: str = ""
    bank_account_name: str = ""
    bank_instructions: str = "Use your registered email as the transfer narration."
    # Flutterwave (sandbox by default)
    flw_environment: Literal["sandbox", "production"] = "sandbox"
    flw_public_key: str = ""
    flw_secret_key: str = ""
    flw_encryption_key: str = ""
    flw_webhook_secret: str = ""
    # Notifications (placeholders, not active in Phase 1)
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from_email: str = ""
    telegram_bot_token: str = ""
    telegram_channel_id: str = ""
    # Branding / homepage
    brand_tagline: str = "AI-quant betting intelligence — disciplined daily edge."
    sportybet_handle: str = "https://www.sportybet.com/ng/"
    # Sports-data API source (admin-overridable; falls back to .env if blank)
    odds_api_provider: str = "the_odds_api"
    odds_api_base_url: str = "https://api.the-odds-api.com/v4"
    odds_api_key: str = ""  # if blank, server uses THE_ODDS_API_KEY from .env
    # API-Football enrichment (real injuries / form / xG)
    apifootball_key: str = ""  # if blank, server uses APIFOOTBALL_KEY from .env
    apifootball_base_url: str = "https://v3.football.api-sports.io"
    # API-Basketball enrichment (real form / H2H — sister product, separate sub)
    apibasketball_key: str = ""
    apibasketball_base_url: str = "https://v1.basketball.api-sports.io"
    # Daily cron
    cron_enabled: bool = True
    cron_hour_utc: int = Field(default=8, ge=0, le=23)  # 08:00 UTC = 09:00 Lagos
    cron_minute_utc: int = Field(default=0, ge=0, le=59)
    # Slip quality gate — minimum average data_richness required to publish a slip.
    # 0.0 = ship anything (price-only allowed), 0.4 = require partial intel,
    # 0.7 = require full intel only. Default 0.4 — hides obvious fakes from users.
    min_slip_data_richness: float = Field(default=0.4, ge=0.0, le=1.0)
    # Auto-settlement cron (settles past picks against API-Football final scores)
    autosettle_enabled: bool = True
    autosettle_interval_hours: int = Field(default=2, ge=1, le=24)
    # Web Push
    push_enabled: bool = True
    push_subject_email: str = "admin@claudeodd.com"
    updated_at: str = Field(default_factory=utcnow_iso)


class SlipLeg(BaseModel):
    model_config = ConfigDict(extra="ignore")
    match: str
    league: str
    country: str = ""
    country_code: str = ""
    sport: str
    market: str
    selection_label: str
    odds: float
    confidence: float
    edge_pct: float
    expected_value: float = 0.0  # calibrated, per-leg
    book_implied_prob: float = 0.0  # 1/odds, exposed for transparency
    data_richness: float = 0.0  # 0-1: how much real intel (injuries/form/h2h) we had
    kickoff: str = ""  # ISO datetime
    reasoning: str


class CombinedSlip(BaseModel):
    model_config = ConfigDict(extra="ignore")
    date: str
    legs: List[SlipLeg]
    leg_count: int
    combined_odds: float
    combined_confidence: float
    expected_value: float
    risk_level: Literal["LOW", "MEDIUM", "HIGH"]
    sportybet_code: str
    sportybet_url: str
    summary: str
    locked: bool = False  # true if user must subscribe to unlock
