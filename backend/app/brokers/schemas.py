from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class BrokerOrderSide(str, Enum):
    BUY = "buy"
    SELL = "sell"


class BrokerOrderType(str, Enum):
    LIMIT = "limit"
    MARKETABLE_LIMIT = "marketable_limit"
    LOO = "loo"
    LOC = "loc"
    MOO = "moo"
    MOC = "moc"


class BrokerOrderStatus(str, Enum):
    SUBMITTED = "submitted"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    CANCELED = "canceled"
    REJECTED = "rejected"
    UNKNOWN = "unknown"


class BrokerRawResponse(BaseModel):
    status_code: int
    headers: dict[str, str] = Field(default_factory=dict)
    body: dict[str, Any] = Field(default_factory=dict)
    tr_id: str | None = None


class BrokerCandle(BaseModel):
    symbol: str
    candle_date: date
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal | None = None
    currency: str = "USD"
    raw_response: dict[str, Any] = Field(default_factory=dict)


class BrokerPosition(BaseModel):
    symbol: str
    quantity: Decimal
    average_price: Decimal | None = None
    market_value: Decimal | None = None
    unrealized_pnl: Decimal | None = None
    currency: str = "USD"
    raw_response: dict[str, Any] = Field(default_factory=dict)


class BrokerAccount(BaseModel):
    account_ref: str
    cash: dict[str, Decimal] = Field(default_factory=dict)
    total_equity: Decimal | None = None
    positions: list[BrokerPosition] = Field(default_factory=list)
    raw_response: dict[str, Any] = Field(default_factory=dict)


class BrokerBuyingPower(BaseModel):
    symbol: str
    exchange: str
    price: Decimal
    currency: str = "USD"
    cash_available: Decimal | None = None
    max_quantity: Decimal | None = None
    raw_response: dict[str, Any] = Field(default_factory=dict)


class BrokerOrderRequest(BaseModel):
    symbol: str
    side: BrokerOrderSide
    quantity: Decimal = Field(gt=0)
    limit_price: Decimal = Field(ge=0)
    exchange: str = "NASD"
    order_type: BrokerOrderType = BrokerOrderType.MARKETABLE_LIMIT
    currency: str = "USD"
    client_order_id: str | None = None
    planned_order_id: str | None = None


class BrokerOrderResult(BaseModel):
    broker_order_id: str | None = None
    status: BrokerOrderStatus = BrokerOrderStatus.UNKNOWN
    symbol: str | None = None
    side: BrokerOrderSide | None = None
    quantity: Decimal | None = None
    price: Decimal | None = None
    submitted_at: datetime | None = None
    raw_response: dict[str, Any] = Field(default_factory=dict)


class BrokerFill(BaseModel):
    broker_order_id: str | None = None
    broker_fill_id: str | None = None
    symbol: str | None = None
    side: BrokerOrderSide | None = None
    quantity: Decimal | None = None
    price: Decimal | None = None
    filled_at: datetime | None = None
    raw_response: dict[str, Any] = Field(default_factory=dict)
