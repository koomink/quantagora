from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class AssetType(str, Enum):
    COMMON_STOCK = "common_stock"
    BROAD_ETF = "broad_etf"
    SECTOR_ETF = "sector_etf"
    LEVERAGED_ETF = "leveraged_etf"
    INVERSE_ETF = "inverse_etf"


class TradeAction(str, Enum):
    BUY = "buy"
    SELL = "sell"
    REBALANCE = "rebalance"
    EXIT = "exit"


class RiskDecision(str, Enum):
    APPROVED_FOR_HUMAN_REVIEW = "approved_for_human_review"
    REJECTED = "rejected"
    AUTO_EXIT_REQUIRED = "auto_exit_required"
    BLOCK_NEW_ENTRIES = "block_new_entries"


class LlmReportType(str, Enum):
    UNIVERSE_RATIONALE = "universe_rationale"
    TRADE_RATIONALE = "trade_rationale"
    POST_TRADE_REVIEW = "post_trade_review"


class LlmReportStatus(str, Enum):
    GENERATED = "generated"
    FALLBACK = "fallback"


class Money(BaseModel):
    amount: Decimal
    currency: str = Field(min_length=3, max_length=3)


class Asset(BaseModel):
    symbol: str
    name: str
    asset_type: AssetType
    exchange: str
    is_us_listed: bool = True
    is_otc: bool = False
    leveraged_inverse_flag: bool = False
    supported_by_broker: bool = True


class UniverseMember(BaseModel):
    asset: Asset
    rank: int
    rationale: str
    eligibility: dict[str, Any] = Field(default_factory=dict)


class UniverseVersion(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    version_id: str
    status: str
    members: list[UniverseMember]
    source: str = "system"
    generated_at: datetime | None = None
    activated_at: datetime | None = None
    notes: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    rejected_candidates: list[dict[str, Any]] = Field(default_factory=list)


class Quote(BaseModel):
    symbol: str
    bid: Decimal | None = None
    ask: Decimal | None = None
    last: Decimal
    currency: str = "USD"
    quote_time: datetime
    raw_response: dict[str, Any] = Field(default_factory=dict)


class SignalIndicators(BaseModel):
    sma20: float | None = None
    sma50: float | None = None
    sma200: float | None = None
    rsi14: float | None = None
    roc20: float | None = None
    macd: float | None = None
    macd_signal: float | None = None
    macd_hist: float | None = None
    atr14_pct: float | None = None
    realized_vol20: float | None = None


class SignalRegime(BaseModel):
    benchmark_symbol: str
    state: str
    reason: str
    benchmark_close: float | None = None
    benchmark_sma200: float | None = None
    benchmark_realized_vol20: float | None = None


class Signal(BaseModel):
    symbol: str
    action: TradeAction
    horizon: str
    confidence: float = Field(ge=0, le=1)
    target_weight: float = Field(ge=0, le=1)
    rationale: str
    invalidation: str
    generated_at: datetime
    signal_type: str = "trend_following"
    source: str = "signal_engine"
    expires_at: datetime | None = None
    status: str = "new"
    indicators: SignalIndicators | None = None
    regime: SignalRegime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class UniverseRationaleReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: str = Field(min_length=20, max_length=700)
    key_drivers: list[str] = Field(default_factory=list, max_length=5)
    risk_flags: list[str] = Field(default_factory=list, max_length=5)
    selection_discipline: str = Field(min_length=10, max_length=500)
    uncertainty: str = Field(min_length=10, max_length=400)
    risk_decision_locked: bool = True


class TradeRationaleReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: str = Field(min_length=20, max_length=700)
    setup: str = Field(min_length=10, max_length=500)
    confirmations: list[str] = Field(default_factory=list, max_length=5)
    invalidation_focus: str = Field(min_length=10, max_length=400)
    risk_flags: list[str] = Field(default_factory=list, max_length=5)
    uncertainty: str = Field(min_length=10, max_length=400)
    risk_decision_locked: bool = True


class PostTradeReviewReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: str = Field(min_length=20, max_length=700)
    outcome: str = Field(min_length=10, max_length=400)
    what_worked: list[str] = Field(default_factory=list, max_length=5)
    what_to_improve: list[str] = Field(default_factory=list, max_length=5)
    follow_ups: list[str] = Field(default_factory=list, max_length=5)
    uncertainty: str = Field(min_length=10, max_length=400)
    risk_decision_locked: bool = True


class LlmReportRecord(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    report_id: str
    report_type: LlmReportType
    entity_type: str
    entity_id: str
    provider: str
    model: str
    status: LlmReportStatus
    prompt_version: str
    fallback_used: bool = False
    generated_at: datetime
    error_message: str | None = None
    report: dict[str, Any] = Field(default_factory=dict)


class ApprovalRequest(BaseModel):
    approval_id: UUID
    symbol: str
    action: TradeAction
    quantity: Decimal
    limit_price: Decimal
    notional_usd: Decimal
    target_weight: float
    expires_at: datetime
