"""create trading domain schema

Revision ID: 0001
Revises:
Create Date: 2026-04-22
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def uuid_pk() -> sa.Column[sa.UUID]:
    return sa.Column(
        "id",
        sa.UUID(),
        server_default=sa.text("gen_random_uuid()"),
        primary_key=True,
    )


def timestamps() -> list[sa.Column[sa.DateTime]]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    ]


def json_object_column(name: str) -> sa.Column[postgresql.JSONB]:
    return sa.Column(
        name,
        postgresql.JSONB(astext_type=sa.Text()),
        server_default=sa.text("'{}'::jsonb"),
        nullable=False,
    )


def json_array_column(name: str) -> sa.Column[postgresql.JSONB]:
    return sa.Column(
        name,
        postgresql.JSONB(astext_type=sa.Text()),
        server_default=sa.text("'[]'::jsonb"),
        nullable=False,
    )


def upgrade() -> None:
    op.execute('CREATE EXTENSION IF NOT EXISTS "pgcrypto"')

    op.create_table(
        "assets",
        uuid_pk(),
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("asset_type", sa.String(length=32), nullable=False),
        sa.Column("exchange", sa.String(length=32), nullable=False),
        sa.Column("currency", sa.String(length=3), server_default="USD", nullable=False),
        sa.Column("country", sa.String(length=2), server_default="US", nullable=False),
        sa.Column("is_us_listed", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("is_otc", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("leveraged_inverse_flag", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("supported_by_broker", sa.Boolean(), server_default=sa.true(), nullable=False),
        json_object_column("metadata"),
        *timestamps(),
        sa.UniqueConstraint("symbol"),
    )
    op.create_index("ix_assets_symbol", "assets", ["symbol"])
    op.create_index("ix_assets_asset_type", "assets", ["asset_type"])

    op.create_table(
        "market_quotes",
        uuid_pk(),
        sa.Column("asset_id", sa.UUID(), nullable=False),
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.Column("bid", sa.Numeric(20, 6)),
        sa.Column("ask", sa.Numeric(20, 6)),
        sa.Column("last", sa.Numeric(20, 6), nullable=False),
        sa.Column("currency", sa.String(length=3), server_default="USD", nullable=False),
        sa.Column("quote_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source", sa.String(length=32), server_default="kis", nullable=False),
        json_object_column("raw_response"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["asset_id"], ["assets.id"]),
    )
    op.create_index("ix_market_quotes_asset_id", "market_quotes", ["asset_id"])
    op.create_index("ix_market_quotes_symbol", "market_quotes", ["symbol"])
    op.create_index("ix_market_quotes_quote_time", "market_quotes", ["quote_time"])

    op.create_table(
        "candles",
        uuid_pk(),
        sa.Column("asset_id", sa.UUID(), nullable=False),
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.Column("timeframe", sa.String(length=16), nullable=False),
        sa.Column("open_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("close_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("open", sa.Numeric(20, 6), nullable=False),
        sa.Column("high", sa.Numeric(20, 6), nullable=False),
        sa.Column("low", sa.Numeric(20, 6), nullable=False),
        sa.Column("close", sa.Numeric(20, 6), nullable=False),
        sa.Column("adjusted_close", sa.Numeric(20, 6)),
        sa.Column("volume", sa.Numeric(24, 6), server_default="0", nullable=False),
        sa.Column("source", sa.String(length=32), server_default="kis", nullable=False),
        json_object_column("raw_response"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["asset_id"], ["assets.id"]),
        sa.UniqueConstraint("asset_id", "timeframe", "open_time"),
    )
    op.create_index("ix_candles_asset_id", "candles", ["asset_id"])
    op.create_index("ix_candles_symbol_timeframe_open_time", "candles", ["symbol", "timeframe", "open_time"])

    op.create_table(
        "asset_universe_versions",
        uuid_pk(),
        sa.Column("version_code", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=24), server_default="draft", nullable=False),
        sa.Column("source", sa.String(length=32), server_default="system", nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("activated_at", sa.DateTime(timezone=True)),
        sa.Column("notes", sa.Text()),
        json_object_column("metadata"),
        sa.UniqueConstraint("version_code"),
    )

    op.create_table(
        "asset_universe_members",
        uuid_pk(),
        sa.Column("universe_version_id", sa.UUID(), nullable=False),
        sa.Column("asset_id", sa.UUID(), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        json_object_column("eligibility_snapshot"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["asset_id"], ["assets.id"]),
        sa.ForeignKeyConstraint(["universe_version_id"], ["asset_universe_versions.id"], ondelete="CASCADE"),
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
    op.create_index("ix_asset_universe_members_universe_version_id", "asset_universe_members", ["universe_version_id"])
    op.create_index("ix_asset_universe_members_asset_id", "asset_universe_members", ["asset_id"])

    op.create_table(
        "signals",
        uuid_pk(),
        sa.Column("asset_id", sa.UUID(), nullable=False),
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.Column("action", sa.String(length=24), nullable=False),
        sa.Column("horizon", sa.String(length=32), nullable=False),
        sa.Column("confidence", sa.Numeric(5, 4), nullable=False),
        sa.Column("target_weight", sa.Numeric(7, 6), nullable=False),
        sa.Column("source", sa.String(length=32), server_default="system", nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("invalidation", sa.Text(), nullable=False),
        json_object_column("input_snapshot"),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=24), server_default="new", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["asset_id"], ["assets.id"]),
    )
    op.create_index("ix_signals_asset_id", "signals", ["asset_id"])
    op.create_index("ix_signals_symbol", "signals", ["symbol"])
    op.create_index("ix_signals_generated_at", "signals", ["generated_at"])

    op.create_table(
        "risk_checks",
        uuid_pk(),
        sa.Column("asset_id", sa.UUID()),
        sa.Column("signal_id", sa.UUID()),
        sa.Column("decision", sa.String(length=48), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        json_object_column("policy_snapshot"),
        json_object_column("input_snapshot"),
        json_array_column("violations"),
        sa.Column("checked_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["asset_id"], ["assets.id"]),
        sa.ForeignKeyConstraint(["signal_id"], ["signals.id"]),
    )
    op.create_index("ix_risk_checks_asset_id", "risk_checks", ["asset_id"])
    op.create_index("ix_risk_checks_signal_id", "risk_checks", ["signal_id"])
    op.create_index("ix_risk_checks_decision", "risk_checks", ["decision"])
    op.create_index("ix_risk_checks_checked_at", "risk_checks", ["checked_at"])

    op.create_table(
        "approval_requests",
        uuid_pk(),
        sa.Column("signal_id", sa.UUID()),
        sa.Column("risk_check_id", sa.UUID()),
        sa.Column("status", sa.String(length=24), server_default="pending", nullable=False),
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.Column("action", sa.String(length=24), nullable=False),
        sa.Column("quantity", sa.Numeric(24, 8), nullable=False),
        sa.Column("limit_price", sa.Numeric(20, 6), nullable=False),
        sa.Column("notional_usd", sa.Numeric(20, 2), nullable=False),
        sa.Column("target_weight", sa.Numeric(7, 6), nullable=False),
        sa.Column("message_channel", sa.String(length=32), server_default="telegram", nullable=False),
        sa.Column("message_id", sa.String(length=128)),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("responded_at", sa.DateTime(timezone=True)),
        json_object_column("response_payload"),
        *timestamps(),
        sa.ForeignKeyConstraint(["risk_check_id"], ["risk_checks.id"]),
        sa.ForeignKeyConstraint(["signal_id"], ["signals.id"]),
    )
    op.create_index("ix_approval_requests_signal_id", "approval_requests", ["signal_id"])
    op.create_index("ix_approval_requests_risk_check_id", "approval_requests", ["risk_check_id"])
    op.create_index("ix_approval_requests_status", "approval_requests", ["status"])
    op.create_index("ix_approval_requests_symbol", "approval_requests", ["symbol"])
    op.create_index("ix_approval_requests_expires_at", "approval_requests", ["expires_at"])

    op.create_table(
        "planned_orders",
        uuid_pk(),
        sa.Column("signal_id", sa.UUID()),
        sa.Column("risk_check_id", sa.UUID()),
        sa.Column("approval_request_id", sa.UUID()),
        sa.Column("asset_id", sa.UUID(), nullable=False),
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.Column("side", sa.String(length=8), nullable=False),
        sa.Column("order_type", sa.String(length=32), server_default="marketable_limit", nullable=False),
        sa.Column("quantity", sa.Numeric(24, 8), nullable=False),
        sa.Column("limit_price", sa.Numeric(20, 6), nullable=False),
        sa.Column("notional_usd", sa.Numeric(20, 2), nullable=False),
        sa.Column("time_in_force", sa.String(length=16), server_default="day", nullable=False),
        sa.Column("status", sa.String(length=24), server_default="planned", nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("rationale", sa.Text()),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        *timestamps(),
        sa.ForeignKeyConstraint(["approval_request_id"], ["approval_requests.id"]),
        sa.ForeignKeyConstraint(["asset_id"], ["assets.id"]),
        sa.ForeignKeyConstraint(["risk_check_id"], ["risk_checks.id"]),
        sa.ForeignKeyConstraint(["signal_id"], ["signals.id"]),
        sa.UniqueConstraint("idempotency_key"),
    )
    op.create_index("ix_planned_orders_signal_id", "planned_orders", ["signal_id"])
    op.create_index("ix_planned_orders_risk_check_id", "planned_orders", ["risk_check_id"])
    op.create_index("ix_planned_orders_approval_request_id", "planned_orders", ["approval_request_id"])
    op.create_index("ix_planned_orders_asset_id", "planned_orders", ["asset_id"])
    op.create_index("ix_planned_orders_symbol", "planned_orders", ["symbol"])
    op.create_index("ix_planned_orders_status", "planned_orders", ["status"])
    op.create_index("ix_planned_orders_expires_at", "planned_orders", ["expires_at"])

    op.create_table(
        "broker_orders",
        uuid_pk(),
        sa.Column("planned_order_id", sa.UUID()),
        sa.Column("approval_request_id", sa.UUID()),
        sa.Column("risk_check_id", sa.UUID()),
        sa.Column("broker_order_id", sa.String(length=128)),
        sa.Column("broker_account_ref", sa.String(length=128), nullable=False),
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.Column("side", sa.String(length=8), nullable=False),
        sa.Column("order_type", sa.String(length=32), nullable=False),
        sa.Column("quantity", sa.Numeric(24, 8), nullable=False),
        sa.Column("limit_price", sa.Numeric(20, 6)),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True)),
        sa.Column("last_status_at", sa.DateTime(timezone=True)),
        sa.Column("canceled_at", sa.DateTime(timezone=True)),
        json_object_column("raw_request"),
        json_object_column("raw_response"),
        *timestamps(),
        sa.ForeignKeyConstraint(["approval_request_id"], ["approval_requests.id"]),
        sa.ForeignKeyConstraint(["planned_order_id"], ["planned_orders.id"]),
        sa.ForeignKeyConstraint(["risk_check_id"], ["risk_checks.id"]),
    )
    op.create_index("ix_broker_orders_planned_order_id", "broker_orders", ["planned_order_id"])
    op.create_index("ix_broker_orders_approval_request_id", "broker_orders", ["approval_request_id"])
    op.create_index("ix_broker_orders_risk_check_id", "broker_orders", ["risk_check_id"])
    op.create_index("ix_broker_orders_broker_order_id", "broker_orders", ["broker_order_id"], unique=True)
    op.create_index("ix_broker_orders_symbol", "broker_orders", ["symbol"])
    op.create_index("ix_broker_orders_status", "broker_orders", ["status"])

    op.create_table(
        "fills",
        uuid_pk(),
        sa.Column("broker_order_id", sa.UUID(), nullable=False),
        sa.Column("broker_fill_id", sa.String(length=128)),
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.Column("side", sa.String(length=8), nullable=False),
        sa.Column("quantity", sa.Numeric(24, 8), nullable=False),
        sa.Column("price", sa.Numeric(20, 6), nullable=False),
        sa.Column("gross_amount", sa.Numeric(20, 2), nullable=False),
        sa.Column("fees", sa.Numeric(20, 2), server_default="0", nullable=False),
        sa.Column("taxes", sa.Numeric(20, 2), server_default="0", nullable=False),
        sa.Column("currency", sa.String(length=3), server_default="USD", nullable=False),
        sa.Column("filled_at", sa.DateTime(timezone=True), nullable=False),
        json_object_column("raw_response"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["broker_order_id"], ["broker_orders.id"]),
    )
    op.create_index("ix_fills_broker_order_id", "fills", ["broker_order_id"])
    op.create_index("ix_fills_broker_fill_id", "fills", ["broker_fill_id"])
    op.create_index("ix_fills_symbol", "fills", ["symbol"])
    op.create_index("ix_fills_filled_at", "fills", ["filled_at"])

    op.create_table(
        "positions",
        uuid_pk(),
        sa.Column("asset_id", sa.UUID(), nullable=False),
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.Column("quantity", sa.Numeric(24, 8), nullable=False),
        sa.Column("average_cost", sa.Numeric(20, 6), nullable=False),
        sa.Column("cost_basis", sa.Numeric(20, 2), nullable=False),
        sa.Column("market_value", sa.Numeric(20, 2), nullable=False),
        sa.Column("unrealized_pnl", sa.Numeric(20, 2), server_default="0", nullable=False),
        sa.Column("currency", sa.String(length=3), server_default="USD", nullable=False),
        sa.Column("as_of", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source", sa.String(length=32), server_default="internal", nullable=False),
        json_object_column("raw_response"),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["asset_id"], ["assets.id"]),
        sa.UniqueConstraint("asset_id", "source"),
    )
    op.create_index("ix_positions_asset_id", "positions", ["asset_id"])
    op.create_index("ix_positions_symbol", "positions", ["symbol"])
    op.create_index("ix_positions_as_of", "positions", ["as_of"])

    op.create_table(
        "cash_snapshots",
        uuid_pk(),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("cash_available", sa.Numeric(20, 2), nullable=False),
        sa.Column("cash_settled", sa.Numeric(20, 2), nullable=False),
        sa.Column("buying_power", sa.Numeric(20, 2), nullable=False),
        sa.Column("fx_rate_krw", sa.Numeric(20, 6)),
        sa.Column("as_of", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source", sa.String(length=32), server_default="kis", nullable=False),
        json_object_column("raw_response"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_cash_snapshots_currency", "cash_snapshots", ["currency"])
    op.create_index("ix_cash_snapshots_as_of", "cash_snapshots", ["as_of"])

    op.create_table(
        "portfolio_snapshots",
        uuid_pk(),
        sa.Column("base_currency", sa.String(length=3), server_default="USD", nullable=False),
        sa.Column("total_equity", sa.Numeric(20, 2), nullable=False),
        sa.Column("cash_value", sa.Numeric(20, 2), nullable=False),
        sa.Column("positions_value", sa.Numeric(20, 2), nullable=False),
        sa.Column("gross_exposure_pct", sa.Numeric(7, 4), nullable=False),
        sa.Column("cash_buffer_pct", sa.Numeric(7, 4), nullable=False),
        sa.Column("daily_pnl", sa.Numeric(20, 2)),
        sa.Column("weekly_pnl", sa.Numeric(20, 2)),
        sa.Column("monthly_pnl", sa.Numeric(20, 2)),
        sa.Column("max_drawdown_pct", sa.Numeric(7, 4)),
        sa.Column("as_of", sa.DateTime(timezone=True), nullable=False),
        json_object_column("raw_snapshot"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_portfolio_snapshots_as_of", "portfolio_snapshots", ["as_of"])

    op.create_table(
        "tax_lots",
        uuid_pk(),
        sa.Column("asset_id", sa.UUID(), nullable=False),
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.Column("opening_fill_id", sa.UUID()),
        sa.Column("acquisition_date", sa.Date(), nullable=False),
        sa.Column("quantity_opened", sa.Numeric(24, 8), nullable=False),
        sa.Column("quantity_remaining", sa.Numeric(24, 8), nullable=False),
        sa.Column("cost_basis_usd", sa.Numeric(20, 2), nullable=False),
        sa.Column("cost_basis_krw", sa.Numeric(24, 2)),
        sa.Column("fx_rate_krw", sa.Numeric(20, 6)),
        sa.Column("fees_usd", sa.Numeric(20, 2), server_default="0", nullable=False),
        sa.Column("status", sa.String(length=24), server_default="open", nullable=False),
        json_object_column("raw_source"),
        *timestamps(),
        sa.ForeignKeyConstraint(["asset_id"], ["assets.id"]),
        sa.ForeignKeyConstraint(["opening_fill_id"], ["fills.id"]),
    )
    op.create_index("ix_tax_lots_asset_id", "tax_lots", ["asset_id"])
    op.create_index("ix_tax_lots_symbol", "tax_lots", ["symbol"])
    op.create_index("ix_tax_lots_opening_fill_id", "tax_lots", ["opening_fill_id"])
    op.create_index("ix_tax_lots_status", "tax_lots", ["status"])

    op.create_table(
        "tax_events",
        uuid_pk(),
        sa.Column("asset_id", sa.UUID()),
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.Column("event_type", sa.String(length=32), nullable=False),
        sa.Column("related_fill_id", sa.UUID()),
        sa.Column("tax_lot_id", sa.UUID()),
        sa.Column("event_date", sa.Date(), nullable=False),
        sa.Column("quantity", sa.Numeric(24, 8)),
        sa.Column("proceeds_usd", sa.Numeric(20, 2)),
        sa.Column("cost_basis_usd", sa.Numeric(20, 2)),
        sa.Column("realized_gain_usd", sa.Numeric(20, 2)),
        sa.Column("fees_usd", sa.Numeric(20, 2)),
        sa.Column("withholding_tax_usd", sa.Numeric(20, 2)),
        sa.Column("fx_rate_krw", sa.Numeric(20, 6)),
        sa.Column("proceeds_krw", sa.Numeric(24, 2)),
        sa.Column("realized_gain_krw", sa.Numeric(24, 2)),
        sa.Column("notes", sa.Text()),
        json_object_column("raw_source"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["asset_id"], ["assets.id"]),
        sa.ForeignKeyConstraint(["related_fill_id"], ["fills.id"]),
        sa.ForeignKeyConstraint(["tax_lot_id"], ["tax_lots.id"]),
    )
    op.create_index("ix_tax_events_asset_id", "tax_events", ["asset_id"])
    op.create_index("ix_tax_events_symbol", "tax_events", ["symbol"])
    op.create_index("ix_tax_events_event_type", "tax_events", ["event_type"])
    op.create_index("ix_tax_events_related_fill_id", "tax_events", ["related_fill_id"])
    op.create_index("ix_tax_events_tax_lot_id", "tax_events", ["tax_lot_id"])
    op.create_index("ix_tax_events_event_date", "tax_events", ["event_date"])

    op.create_table(
        "corporate_actions",
        uuid_pk(),
        sa.Column("asset_id", sa.UUID()),
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.Column("action_type", sa.String(length=32), nullable=False),
        sa.Column("effective_date", sa.Date(), nullable=False),
        sa.Column("ratio_from", sa.Numeric(20, 8)),
        sa.Column("ratio_to", sa.Numeric(20, 8)),
        sa.Column("cash_amount", sa.Numeric(20, 6)),
        sa.Column("currency", sa.String(length=3)),
        sa.Column("old_symbol", sa.String(length=32)),
        sa.Column("new_symbol", sa.String(length=32)),
        sa.Column("status", sa.String(length=32), server_default="detected", nullable=False),
        sa.Column("source", sa.String(length=32), server_default="broker", nullable=False),
        json_object_column("raw_source"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(["asset_id"], ["assets.id"]),
    )
    op.create_index("ix_corporate_actions_asset_id", "corporate_actions", ["asset_id"])
    op.create_index("ix_corporate_actions_symbol", "corporate_actions", ["symbol"])
    op.create_index("ix_corporate_actions_action_type", "corporate_actions", ["action_type"])
    op.create_index("ix_corporate_actions_effective_date", "corporate_actions", ["effective_date"])
    op.create_index("ix_corporate_actions_status", "corporate_actions", ["status"])

    op.create_table(
        "audit_logs",
        uuid_pk(),
        sa.Column("actor_type", sa.String(length=32), nullable=False),
        sa.Column("actor_id", sa.String(length=128)),
        sa.Column("action", sa.String(length=128), nullable=False),
        sa.Column("entity_type", sa.String(length=64), nullable=False),
        sa.Column("entity_id", sa.String(length=128)),
        sa.Column("before", postgresql.JSONB(astext_type=sa.Text())),
        sa.Column("after", postgresql.JSONB(astext_type=sa.Text())),
        json_object_column("metadata"),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_audit_logs_actor_type", "audit_logs", ["actor_type"])
    op.create_index("ix_audit_logs_action", "audit_logs", ["action"])
    op.create_index("ix_audit_logs_entity_type", "audit_logs", ["entity_type"])
    op.create_index("ix_audit_logs_occurred_at", "audit_logs", ["occurred_at"])


def downgrade() -> None:
    op.drop_table("audit_logs")
    op.drop_table("corporate_actions")
    op.drop_table("tax_events")
    op.drop_table("tax_lots")
    op.drop_table("portfolio_snapshots")
    op.drop_table("cash_snapshots")
    op.drop_table("positions")
    op.drop_table("fills")
    op.drop_table("broker_orders")
    op.drop_table("planned_orders")
    op.drop_table("approval_requests")
    op.drop_table("risk_checks")
    op.drop_table("signals")
    op.drop_table("asset_universe_members")
    op.drop_table("asset_universe_versions")
    op.drop_table("candles")
    op.drop_table("market_quotes")
    op.drop_table("assets")
