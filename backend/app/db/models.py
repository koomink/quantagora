from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

UUID_PK = sa.UUID(as_uuid=True)
JSON_OBJECT_DEFAULT = sa.text("'{}'::jsonb")
JSON_ARRAY_DEFAULT = sa.text("'[]'::jsonb")


def uuid_pk_column() -> Mapped[UUID]:
    return mapped_column(
        UUID_PK,
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
    )


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        server_default=sa.func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        server_default=sa.func.now(),
        onupdate=sa.func.now(),
        nullable=False,
    )


class Asset(TimestampMixin, Base):
    __tablename__ = "assets"

    id: Mapped[UUID] = uuid_pk_column()
    symbol: Mapped[str] = mapped_column(sa.String(32), nullable=False, unique=True, index=True)
    name: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    asset_type: Mapped[str] = mapped_column(sa.String(32), nullable=False, index=True)
    exchange: Mapped[str] = mapped_column(sa.String(32), nullable=False)
    currency: Mapped[str] = mapped_column(sa.String(3), nullable=False, server_default="USD")
    country: Mapped[str] = mapped_column(sa.String(2), nullable=False, server_default="US")
    is_us_listed: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, server_default=sa.true())
    is_otc: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, server_default=sa.false())
    leveraged_inverse_flag: Mapped[bool] = mapped_column(
        sa.Boolean,
        nullable=False,
        server_default=sa.false(),
    )
    supported_by_broker: Mapped[bool] = mapped_column(
        sa.Boolean,
        nullable=False,
        server_default=sa.true(),
    )
    asset_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata",
        JSONB,
        nullable=False,
        server_default=JSON_OBJECT_DEFAULT,
    )

    universe_members: Mapped[list["AssetUniverseMember"]] = relationship(back_populates="asset")


class MarketQuote(Base):
    __tablename__ = "market_quotes"

    id: Mapped[UUID] = uuid_pk_column()
    asset_id: Mapped[UUID] = mapped_column(sa.ForeignKey("assets.id"), nullable=False, index=True)
    symbol: Mapped[str] = mapped_column(sa.String(32), nullable=False, index=True)
    bid: Mapped[Decimal | None] = mapped_column(sa.Numeric(20, 6))
    ask: Mapped[Decimal | None] = mapped_column(sa.Numeric(20, 6))
    last: Mapped[Decimal] = mapped_column(sa.Numeric(20, 6), nullable=False)
    currency: Mapped[str] = mapped_column(sa.String(3), nullable=False, server_default="USD")
    quote_time: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        index=True,
    )
    source: Mapped[str] = mapped_column(sa.String(32), nullable=False, server_default="kis")
    raw_response: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=JSON_OBJECT_DEFAULT,
    )
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        server_default=sa.func.now(),
        nullable=False,
    )


class Candle(Base):
    __tablename__ = "candles"
    __table_args__ = (
        sa.UniqueConstraint("asset_id", "timeframe", "open_time"),
        sa.Index("ix_candles_symbol_timeframe_open_time", "symbol", "timeframe", "open_time"),
    )

    id: Mapped[UUID] = uuid_pk_column()
    asset_id: Mapped[UUID] = mapped_column(sa.ForeignKey("assets.id"), nullable=False, index=True)
    symbol: Mapped[str] = mapped_column(sa.String(32), nullable=False)
    timeframe: Mapped[str] = mapped_column(sa.String(16), nullable=False)
    open_time: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False)
    close_time: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False)
    open: Mapped[Decimal] = mapped_column(sa.Numeric(20, 6), nullable=False)
    high: Mapped[Decimal] = mapped_column(sa.Numeric(20, 6), nullable=False)
    low: Mapped[Decimal] = mapped_column(sa.Numeric(20, 6), nullable=False)
    close: Mapped[Decimal] = mapped_column(sa.Numeric(20, 6), nullable=False)
    adjusted_close: Mapped[Decimal | None] = mapped_column(sa.Numeric(20, 6))
    volume: Mapped[Decimal] = mapped_column(sa.Numeric(24, 6), nullable=False, server_default="0")
    source: Mapped[str] = mapped_column(sa.String(32), nullable=False, server_default="kis")
    raw_response: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=JSON_OBJECT_DEFAULT,
    )
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        server_default=sa.func.now(),
        nullable=False,
    )


class AssetUniverseVersion(Base):
    __tablename__ = "asset_universe_versions"

    id: Mapped[UUID] = uuid_pk_column()
    version_code: Mapped[str] = mapped_column(sa.String(64), nullable=False, unique=True)
    status: Mapped[str] = mapped_column(sa.String(24), nullable=False, server_default="draft")
    source: Mapped[str] = mapped_column(sa.String(32), nullable=False, server_default="system")
    generated_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False)
    activated_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    notes: Mapped[str | None] = mapped_column(sa.Text)
    version_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata",
        JSONB,
        nullable=False,
        server_default=JSON_OBJECT_DEFAULT,
    )

    members: Mapped[list["AssetUniverseMember"]] = relationship(back_populates="universe_version")


class AssetUniverseMember(Base):
    __tablename__ = "asset_universe_members"
    __table_args__ = (
        sa.UniqueConstraint(
            "universe_version_id",
            "asset_id",
            name="uq_asset_universe_members_version_asset",
        ),
        sa.UniqueConstraint(
            "universe_version_id",
            "rank",
            name="uq_asset_universe_members_version_rank",
        ),
    )

    id: Mapped[UUID] = uuid_pk_column()
    universe_version_id: Mapped[UUID] = mapped_column(
        sa.ForeignKey("asset_universe_versions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    asset_id: Mapped[UUID] = mapped_column(sa.ForeignKey("assets.id"), nullable=False, index=True)
    rank: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    rationale: Mapped[str] = mapped_column(sa.Text, nullable=False)
    eligibility_snapshot: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=JSON_OBJECT_DEFAULT,
    )
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        server_default=sa.func.now(),
        nullable=False,
    )

    universe_version: Mapped[AssetUniverseVersion] = relationship(back_populates="members")
    asset: Mapped[Asset] = relationship(back_populates="universe_members")


class Signal(Base):
    __tablename__ = "signals"

    id: Mapped[UUID] = uuid_pk_column()
    asset_id: Mapped[UUID] = mapped_column(sa.ForeignKey("assets.id"), nullable=False, index=True)
    symbol: Mapped[str] = mapped_column(sa.String(32), nullable=False, index=True)
    action: Mapped[str] = mapped_column(sa.String(24), nullable=False)
    horizon: Mapped[str] = mapped_column(sa.String(32), nullable=False)
    confidence: Mapped[Decimal] = mapped_column(sa.Numeric(5, 4), nullable=False)
    target_weight: Mapped[Decimal] = mapped_column(sa.Numeric(7, 6), nullable=False)
    source: Mapped[str] = mapped_column(sa.String(32), nullable=False, server_default="system")
    rationale: Mapped[str] = mapped_column(sa.Text, nullable=False)
    invalidation: Mapped[str] = mapped_column(sa.Text, nullable=False)
    input_snapshot: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=JSON_OBJECT_DEFAULT,
    )
    generated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        index=True,
    )
    expires_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(sa.String(24), nullable=False, server_default="new")
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        server_default=sa.func.now(),
        nullable=False,
    )


class RiskCheck(Base):
    __tablename__ = "risk_checks"

    id: Mapped[UUID] = uuid_pk_column()
    asset_id: Mapped[UUID | None] = mapped_column(sa.ForeignKey("assets.id"), index=True)
    signal_id: Mapped[UUID | None] = mapped_column(sa.ForeignKey("signals.id"), index=True)
    decision: Mapped[str] = mapped_column(sa.String(48), nullable=False, index=True)
    reason: Mapped[str] = mapped_column(sa.Text, nullable=False)
    policy_snapshot: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=JSON_OBJECT_DEFAULT,
    )
    input_snapshot: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=JSON_OBJECT_DEFAULT,
    )
    violations: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=JSON_ARRAY_DEFAULT,
    )
    checked_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        index=True,
    )


class ApprovalRequest(TimestampMixin, Base):
    __tablename__ = "approval_requests"

    id: Mapped[UUID] = uuid_pk_column()
    signal_id: Mapped[UUID | None] = mapped_column(sa.ForeignKey("signals.id"), index=True)
    risk_check_id: Mapped[UUID | None] = mapped_column(sa.ForeignKey("risk_checks.id"), index=True)
    status: Mapped[str] = mapped_column(
        sa.String(24),
        nullable=False,
        server_default="pending",
        index=True,
    )
    symbol: Mapped[str] = mapped_column(sa.String(32), nullable=False, index=True)
    action: Mapped[str] = mapped_column(sa.String(24), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(sa.Numeric(24, 8), nullable=False)
    limit_price: Mapped[Decimal] = mapped_column(sa.Numeric(20, 6), nullable=False)
    notional_usd: Mapped[Decimal] = mapped_column(sa.Numeric(20, 2), nullable=False)
    target_weight: Mapped[Decimal] = mapped_column(sa.Numeric(7, 6), nullable=False)
    message_channel: Mapped[str] = mapped_column(
        sa.String(32),
        nullable=False,
        server_default="telegram",
    )
    message_id: Mapped[str | None] = mapped_column(sa.String(128))
    requested_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        index=True,
    )
    responded_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    response_payload: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=JSON_OBJECT_DEFAULT,
    )


class PlannedOrder(TimestampMixin, Base):
    __tablename__ = "planned_orders"

    id: Mapped[UUID] = uuid_pk_column()
    signal_id: Mapped[UUID | None] = mapped_column(sa.ForeignKey("signals.id"), index=True)
    risk_check_id: Mapped[UUID | None] = mapped_column(sa.ForeignKey("risk_checks.id"), index=True)
    approval_request_id: Mapped[UUID | None] = mapped_column(
        sa.ForeignKey("approval_requests.id"),
        index=True,
    )
    asset_id: Mapped[UUID] = mapped_column(sa.ForeignKey("assets.id"), nullable=False, index=True)
    symbol: Mapped[str] = mapped_column(sa.String(32), nullable=False, index=True)
    side: Mapped[str] = mapped_column(sa.String(8), nullable=False)
    order_type: Mapped[str] = mapped_column(
        sa.String(32),
        nullable=False,
        server_default="marketable_limit",
    )
    quantity: Mapped[Decimal] = mapped_column(sa.Numeric(24, 8), nullable=False)
    limit_price: Mapped[Decimal] = mapped_column(sa.Numeric(20, 6), nullable=False)
    notional_usd: Mapped[Decimal] = mapped_column(sa.Numeric(20, 2), nullable=False)
    time_in_force: Mapped[str] = mapped_column(sa.String(16), nullable=False, server_default="day")
    status: Mapped[str] = mapped_column(
        sa.String(24),
        nullable=False,
        server_default="planned",
        index=True,
    )
    idempotency_key: Mapped[str] = mapped_column(sa.String(128), nullable=False, unique=True)
    rationale: Mapped[str | None] = mapped_column(sa.Text)
    expires_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        index=True,
    )


class BrokerOrder(TimestampMixin, Base):
    __tablename__ = "broker_orders"
    __table_args__ = (sa.Index("ix_broker_orders_broker_order_id", "broker_order_id", unique=True),)

    id: Mapped[UUID] = uuid_pk_column()
    planned_order_id: Mapped[UUID | None] = mapped_column(
        sa.ForeignKey("planned_orders.id"),
        index=True,
    )
    approval_request_id: Mapped[UUID | None] = mapped_column(
        sa.ForeignKey("approval_requests.id"),
        index=True,
    )
    risk_check_id: Mapped[UUID | None] = mapped_column(sa.ForeignKey("risk_checks.id"), index=True)
    broker_order_id: Mapped[str | None] = mapped_column(sa.String(128))
    broker_account_ref: Mapped[str] = mapped_column(sa.String(128), nullable=False)
    symbol: Mapped[str] = mapped_column(sa.String(32), nullable=False, index=True)
    side: Mapped[str] = mapped_column(sa.String(8), nullable=False)
    order_type: Mapped[str] = mapped_column(sa.String(32), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(sa.Numeric(24, 8), nullable=False)
    limit_price: Mapped[Decimal | None] = mapped_column(sa.Numeric(20, 6))
    status: Mapped[str] = mapped_column(sa.String(32), nullable=False, index=True)
    submitted_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    last_status_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    canceled_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    raw_request: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=JSON_OBJECT_DEFAULT,
    )
    raw_response: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=JSON_OBJECT_DEFAULT,
    )


class Fill(Base):
    __tablename__ = "fills"

    id: Mapped[UUID] = uuid_pk_column()
    broker_order_id: Mapped[UUID] = mapped_column(
        sa.ForeignKey("broker_orders.id"),
        nullable=False,
        index=True,
    )
    broker_fill_id: Mapped[str | None] = mapped_column(sa.String(128), index=True)
    symbol: Mapped[str] = mapped_column(sa.String(32), nullable=False, index=True)
    side: Mapped[str] = mapped_column(sa.String(8), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(sa.Numeric(24, 8), nullable=False)
    price: Mapped[Decimal] = mapped_column(sa.Numeric(20, 6), nullable=False)
    gross_amount: Mapped[Decimal] = mapped_column(sa.Numeric(20, 2), nullable=False)
    fees: Mapped[Decimal] = mapped_column(sa.Numeric(20, 2), nullable=False, server_default="0")
    taxes: Mapped[Decimal] = mapped_column(sa.Numeric(20, 2), nullable=False, server_default="0")
    currency: Mapped[str] = mapped_column(sa.String(3), nullable=False, server_default="USD")
    filled_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        index=True,
    )
    raw_response: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=JSON_OBJECT_DEFAULT,
    )
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        server_default=sa.func.now(),
        nullable=False,
    )


class Position(Base):
    __tablename__ = "positions"
    __table_args__ = (sa.UniqueConstraint("asset_id", "source"),)

    id: Mapped[UUID] = uuid_pk_column()
    asset_id: Mapped[UUID] = mapped_column(sa.ForeignKey("assets.id"), nullable=False, index=True)
    symbol: Mapped[str] = mapped_column(sa.String(32), nullable=False, index=True)
    quantity: Mapped[Decimal] = mapped_column(sa.Numeric(24, 8), nullable=False)
    average_cost: Mapped[Decimal] = mapped_column(sa.Numeric(20, 6), nullable=False)
    cost_basis: Mapped[Decimal] = mapped_column(sa.Numeric(20, 2), nullable=False)
    market_value: Mapped[Decimal] = mapped_column(sa.Numeric(20, 2), nullable=False)
    unrealized_pnl: Mapped[Decimal] = mapped_column(
        sa.Numeric(20, 2),
        nullable=False,
        server_default="0",
    )
    currency: Mapped[str] = mapped_column(sa.String(3), nullable=False, server_default="USD")
    as_of: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False, index=True)
    source: Mapped[str] = mapped_column(sa.String(32), nullable=False, server_default="internal")
    raw_response: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=JSON_OBJECT_DEFAULT,
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        server_default=sa.func.now(),
        onupdate=sa.func.now(),
        nullable=False,
    )


class CashSnapshot(Base):
    __tablename__ = "cash_snapshots"

    id: Mapped[UUID] = uuid_pk_column()
    currency: Mapped[str] = mapped_column(sa.String(3), nullable=False, index=True)
    cash_available: Mapped[Decimal] = mapped_column(sa.Numeric(20, 2), nullable=False)
    cash_settled: Mapped[Decimal] = mapped_column(sa.Numeric(20, 2), nullable=False)
    buying_power: Mapped[Decimal] = mapped_column(sa.Numeric(20, 2), nullable=False)
    fx_rate_krw: Mapped[Decimal | None] = mapped_column(sa.Numeric(20, 6))
    as_of: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False, index=True)
    source: Mapped[str] = mapped_column(sa.String(32), nullable=False, server_default="kis")
    raw_response: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=JSON_OBJECT_DEFAULT,
    )
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        server_default=sa.func.now(),
        nullable=False,
    )


class PortfolioSnapshot(Base):
    __tablename__ = "portfolio_snapshots"

    id: Mapped[UUID] = uuid_pk_column()
    base_currency: Mapped[str] = mapped_column(sa.String(3), nullable=False, server_default="USD")
    total_equity: Mapped[Decimal] = mapped_column(sa.Numeric(20, 2), nullable=False)
    cash_value: Mapped[Decimal] = mapped_column(sa.Numeric(20, 2), nullable=False)
    positions_value: Mapped[Decimal] = mapped_column(sa.Numeric(20, 2), nullable=False)
    gross_exposure_pct: Mapped[Decimal] = mapped_column(sa.Numeric(7, 4), nullable=False)
    cash_buffer_pct: Mapped[Decimal] = mapped_column(sa.Numeric(7, 4), nullable=False)
    daily_pnl: Mapped[Decimal | None] = mapped_column(sa.Numeric(20, 2))
    weekly_pnl: Mapped[Decimal | None] = mapped_column(sa.Numeric(20, 2))
    monthly_pnl: Mapped[Decimal | None] = mapped_column(sa.Numeric(20, 2))
    max_drawdown_pct: Mapped[Decimal | None] = mapped_column(sa.Numeric(7, 4))
    as_of: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False, index=True)
    raw_snapshot: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=JSON_OBJECT_DEFAULT,
    )
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        server_default=sa.func.now(),
        nullable=False,
    )


class TaxLot(TimestampMixin, Base):
    __tablename__ = "tax_lots"

    id: Mapped[UUID] = uuid_pk_column()
    asset_id: Mapped[UUID] = mapped_column(sa.ForeignKey("assets.id"), nullable=False, index=True)
    symbol: Mapped[str] = mapped_column(sa.String(32), nullable=False, index=True)
    opening_fill_id: Mapped[UUID | None] = mapped_column(sa.ForeignKey("fills.id"), index=True)
    acquisition_date: Mapped[date] = mapped_column(sa.Date, nullable=False)
    quantity_opened: Mapped[Decimal] = mapped_column(sa.Numeric(24, 8), nullable=False)
    quantity_remaining: Mapped[Decimal] = mapped_column(sa.Numeric(24, 8), nullable=False)
    cost_basis_usd: Mapped[Decimal] = mapped_column(sa.Numeric(20, 2), nullable=False)
    cost_basis_krw: Mapped[Decimal | None] = mapped_column(sa.Numeric(24, 2))
    fx_rate_krw: Mapped[Decimal | None] = mapped_column(sa.Numeric(20, 6))
    fees_usd: Mapped[Decimal] = mapped_column(sa.Numeric(20, 2), nullable=False, server_default="0")
    status: Mapped[str] = mapped_column(
        sa.String(24),
        nullable=False,
        server_default="open",
        index=True,
    )
    raw_source: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=JSON_OBJECT_DEFAULT,
    )


class TaxEvent(Base):
    __tablename__ = "tax_events"

    id: Mapped[UUID] = uuid_pk_column()
    asset_id: Mapped[UUID | None] = mapped_column(sa.ForeignKey("assets.id"), index=True)
    symbol: Mapped[str] = mapped_column(sa.String(32), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(sa.String(32), nullable=False, index=True)
    related_fill_id: Mapped[UUID | None] = mapped_column(sa.ForeignKey("fills.id"), index=True)
    tax_lot_id: Mapped[UUID | None] = mapped_column(sa.ForeignKey("tax_lots.id"), index=True)
    event_date: Mapped[date] = mapped_column(sa.Date, nullable=False, index=True)
    quantity: Mapped[Decimal | None] = mapped_column(sa.Numeric(24, 8))
    proceeds_usd: Mapped[Decimal | None] = mapped_column(sa.Numeric(20, 2))
    cost_basis_usd: Mapped[Decimal | None] = mapped_column(sa.Numeric(20, 2))
    realized_gain_usd: Mapped[Decimal | None] = mapped_column(sa.Numeric(20, 2))
    fees_usd: Mapped[Decimal | None] = mapped_column(sa.Numeric(20, 2))
    withholding_tax_usd: Mapped[Decimal | None] = mapped_column(sa.Numeric(20, 2))
    fx_rate_krw: Mapped[Decimal | None] = mapped_column(sa.Numeric(20, 6))
    proceeds_krw: Mapped[Decimal | None] = mapped_column(sa.Numeric(24, 2))
    realized_gain_krw: Mapped[Decimal | None] = mapped_column(sa.Numeric(24, 2))
    notes: Mapped[str | None] = mapped_column(sa.Text)
    raw_source: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=JSON_OBJECT_DEFAULT,
    )
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        server_default=sa.func.now(),
        nullable=False,
    )


class CorporateAction(Base):
    __tablename__ = "corporate_actions"

    id: Mapped[UUID] = uuid_pk_column()
    asset_id: Mapped[UUID | None] = mapped_column(sa.ForeignKey("assets.id"), index=True)
    symbol: Mapped[str] = mapped_column(sa.String(32), nullable=False, index=True)
    action_type: Mapped[str] = mapped_column(sa.String(32), nullable=False, index=True)
    effective_date: Mapped[date] = mapped_column(sa.Date, nullable=False, index=True)
    ratio_from: Mapped[Decimal | None] = mapped_column(sa.Numeric(20, 8))
    ratio_to: Mapped[Decimal | None] = mapped_column(sa.Numeric(20, 8))
    cash_amount: Mapped[Decimal | None] = mapped_column(sa.Numeric(20, 6))
    currency: Mapped[str | None] = mapped_column(sa.String(3))
    old_symbol: Mapped[str | None] = mapped_column(sa.String(32))
    new_symbol: Mapped[str | None] = mapped_column(sa.String(32))
    status: Mapped[str] = mapped_column(
        sa.String(32),
        nullable=False,
        server_default="detected",
        index=True,
    )
    source: Mapped[str] = mapped_column(sa.String(32), nullable=False, server_default="broker")
    raw_source: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=JSON_OBJECT_DEFAULT,
    )
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        server_default=sa.func.now(),
        nullable=False,
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[UUID] = uuid_pk_column()
    actor_type: Mapped[str] = mapped_column(sa.String(32), nullable=False, index=True)
    actor_id: Mapped[str | None] = mapped_column(sa.String(128))
    action: Mapped[str] = mapped_column(sa.String(128), nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(sa.String(64), nullable=False, index=True)
    entity_id: Mapped[str | None] = mapped_column(sa.String(128))
    before: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    after: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    audit_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata",
        JSONB,
        nullable=False,
        server_default=JSON_OBJECT_DEFAULT,
    )
    occurred_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        index=True,
    )
