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


class UniverseVersion(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    version_id: str
    status: str
    members: list[UniverseMember]


class Quote(BaseModel):
    symbol: str
    bid: Decimal | None = None
    ask: Decimal | None = None
    last: Decimal
    currency: str = "USD"
    quote_time: datetime
    raw_response: dict[str, Any] = Field(default_factory=dict)


class Signal(BaseModel):
    symbol: str
    action: TradeAction
    horizon: str
    confidence: float = Field(ge=0, le=1)
    target_weight: float = Field(ge=0, le=1)
    rationale: str
    invalidation: str
    generated_at: datetime


class ApprovalRequest(BaseModel):
    approval_id: UUID
    symbol: str
    action: TradeAction
    quantity: Decimal
    limit_price: Decimal
    notional_usd: Decimal
    target_weight: float
    expires_at: datetime
