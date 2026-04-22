from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.brokers.base import BrokerAdapter
from app.brokers.schemas import BrokerCandle
from app.core.config import Settings, get_settings
from app.db.models import Asset as AssetRow
from app.db.models import Candle as CandleRow
from app.db.models import MarketQuote as MarketQuoteRow
from app.domain.models import AssetType
from app.services.market_calendar import USEquityMarketCalendar, utc_now
from app.services.universe import get_current_universe


@dataclass(frozen=True)
class FreshnessResult:
    is_fresh: bool
    age_seconds: int
    threshold_seconds: int
    reason: str


@dataclass(frozen=True)
class QuoteSnapshotResult:
    quote_id: UUID
    symbol: str
    last: Decimal
    bid: Decimal | None
    ask: Decimal | None
    currency: str
    quote_time: datetime
    freshness: FreshnessResult


@dataclass(frozen=True)
class CandleBackfillResult:
    symbol: str
    timeframe: str
    requested_start: date
    requested_end: date
    fetched_count: int
    upserted_count: int
    skipped_count: int


@dataclass(frozen=True)
class DailyRefreshResult:
    symbols: list[str]
    candle_results: list[CandleBackfillResult]
    quote_results: list[QuoteSnapshotResult]
    skipped_quote_reason: str | None
    refreshed_at: datetime


class MarketDataService:
    def __init__(
        self,
        *,
        db: Session,
        broker: BrokerAdapter,
        settings: Settings | None = None,
        calendar: USEquityMarketCalendar | None = None,
    ) -> None:
        self.db = db
        self.broker = broker
        self.settings = settings or get_settings()
        self.calendar = calendar or USEquityMarketCalendar.from_settings(self.settings)

    async def snapshot_quote(
        self,
        symbol: str,
        *,
        exchange: str = "NAS",
        enforce_regular_session: bool = True,
        now: datetime | None = None,
    ) -> QuoteSnapshotResult:
        if enforce_regular_session:
            self.calendar.assert_regular_session(now)

        normalized_symbol = symbol.upper()
        quote = await self.broker.get_quote(normalized_symbol, exchange=exchange)
        asset = self._ensure_asset(normalized_symbol, exchange)
        quote_time = utc_now(quote.quote_time)

        quote_row = MarketQuoteRow(
            asset_id=asset.id,
            symbol=normalized_symbol,
            bid=quote.bid,
            ask=quote.ask,
            last=quote.last,
            currency=quote.currency,
            quote_time=quote_time,
            source="kis",
            raw_response=_json_payload(quote.raw_response),
        )
        self.db.add(quote_row)
        self.db.commit()
        self.db.refresh(quote_row)

        return QuoteSnapshotResult(
            quote_id=quote_row.id,
            symbol=quote_row.symbol,
            last=quote_row.last,
            bid=quote_row.bid,
            ask=quote_row.ask,
            currency=quote_row.currency,
            quote_time=quote_row.quote_time,
            freshness=evaluate_quote_freshness(
                quote_row.quote_time,
                now=now,
                stale_after_seconds=self.settings.market_quote_stale_seconds,
            ),
        )

    def latest_quote(
        self,
        symbol: str,
        *,
        now: datetime | None = None,
    ) -> QuoteSnapshotResult | None:
        normalized_symbol = symbol.upper()
        quote_row = self.db.scalars(
            sa.select(MarketQuoteRow)
            .where(MarketQuoteRow.symbol == normalized_symbol)
            .order_by(MarketQuoteRow.quote_time.desc())
            .limit(1)
        ).first()
        if quote_row is None:
            return None
        return QuoteSnapshotResult(
            quote_id=quote_row.id,
            symbol=quote_row.symbol,
            last=quote_row.last,
            bid=quote_row.bid,
            ask=quote_row.ask,
            currency=quote_row.currency,
            quote_time=quote_row.quote_time,
            freshness=evaluate_quote_freshness(
                quote_row.quote_time,
                now=now,
                stale_after_seconds=self.settings.market_quote_stale_seconds,
            ),
        )

    async def backfill_candles(
        self,
        symbol: str,
        *,
        start: date | None = None,
        end: date | None = None,
        timeframe: str = "D",
        exchange: str = "NAS",
    ) -> CandleBackfillResult:
        requested_end = end or datetime.now(UTC).date()
        requested_start = start or (
            requested_end - timedelta(days=self.settings.market_daily_candle_lookback_days)
        )
        normalized_symbol = symbol.upper()
        candles = await self.broker.get_candles(
            normalized_symbol,
            start=requested_start,
            end=requested_end,
            timeframe=timeframe,
            exchange=exchange,
        )
        asset = self._ensure_asset(normalized_symbol, exchange)

        upserted_count = 0
        skipped_count = 0
        for candle in candles:
            session = self.calendar.session_hours(candle.candle_date)
            if session is None:
                skipped_count += 1
                continue
            self._upsert_candle(
                asset.id,
                normalized_symbol,
                timeframe,
                candle,
                session.open_at,
                session.close_at,
            )
            upserted_count += 1

        self.db.commit()
        return CandleBackfillResult(
            symbol=normalized_symbol,
            timeframe=timeframe,
            requested_start=requested_start,
            requested_end=requested_end,
            fetched_count=len(candles),
            upserted_count=upserted_count,
            skipped_count=skipped_count,
        )

    async def refresh_daily(
        self,
        *,
        symbols: list[str] | None = None,
        exchange: str = "NAS",
    ) -> DailyRefreshResult:
        normalized_symbols = _normalize_symbols(symbols or self.settings.market_default_symbol_list)
        refreshed_at = datetime.now(UTC)
        status = self.calendar.status(refreshed_at)
        quote_results: list[QuoteSnapshotResult] = []
        candle_results: list[CandleBackfillResult] = []

        for symbol in normalized_symbols:
            candle_results.append(
                await self.backfill_candles(symbol, exchange=exchange, end=refreshed_at.date())
            )
            if status.isOpen:
                quote_results.append(
                    await self.snapshot_quote(
                        symbol,
                        exchange=exchange,
                        enforce_regular_session=True,
                        now=refreshed_at,
                    )
                )

        return DailyRefreshResult(
            symbols=normalized_symbols,
            candle_results=candle_results,
            quote_results=quote_results,
            skipped_quote_reason=None if status.isOpen else status.reason,
            refreshed_at=refreshed_at,
        )

    def _ensure_asset(self, symbol: str, exchange: str) -> AssetRow:
        asset = self.db.scalars(sa.select(AssetRow).where(AssetRow.symbol == symbol)).first()
        if asset is not None:
            return asset

        metadata = _universe_asset_metadata(symbol)
        asset = AssetRow(
            symbol=symbol,
            name=str(metadata.get("name") or symbol),
            asset_type=str(metadata.get("asset_type") or AssetType.COMMON_STOCK.value),
            exchange=str(metadata.get("exchange") or _display_exchange(exchange)),
            currency="USD",
            country="US",
            is_us_listed=True,
            is_otc=False,
            leveraged_inverse_flag=bool(metadata.get("leveraged_inverse_flag", False)),
            supported_by_broker=True,
            asset_metadata={"created_by": "market_data_service"},
        )
        self.db.add(asset)
        self.db.flush()
        return asset

    def _upsert_candle(
        self,
        asset_id: UUID,
        symbol: str,
        timeframe: str,
        candle: BrokerCandle,
        open_time: datetime,
        close_time: datetime,
    ) -> None:
        existing = self.db.scalars(
            sa.select(CandleRow).where(
                CandleRow.asset_id == asset_id,
                CandleRow.timeframe == timeframe,
                CandleRow.open_time == open_time,
            )
        ).first()
        values = {
            "symbol": symbol,
            "timeframe": timeframe,
            "open_time": open_time,
            "close_time": close_time,
            "open": candle.open,
            "high": candle.high,
            "low": candle.low,
            "close": candle.close,
            "adjusted_close": candle.close,
            "volume": candle.volume or Decimal("0"),
            "source": "kis",
            "raw_response": {
                **_json_payload(candle.raw_response),
                "adjusted_price_policy": "kis_dailyprice_modp_1",
            },
        }
        if existing is None:
            self.db.add(CandleRow(asset_id=asset_id, **values))
            return
        for key, value in values.items():
            setattr(existing, key, value)


def evaluate_quote_freshness(
    quote_time: datetime,
    *,
    now: datetime | None = None,
    stale_after_seconds: int,
) -> FreshnessResult:
    now_utc = utc_now(now)
    quote_time_utc = utc_now(quote_time)
    age_seconds = max(int((now_utc - quote_time_utc).total_seconds()), 0)
    is_fresh = age_seconds <= stale_after_seconds
    return FreshnessResult(
        is_fresh=is_fresh,
        age_seconds=age_seconds,
        threshold_seconds=stale_after_seconds,
        reason="Fresh" if is_fresh else "Stale market data",
    )


def _normalize_symbols(symbols: list[str]) -> list[str]:
    seen: set[str] = set()
    normalized: list[str] = []
    for symbol in symbols:
        clean_symbol = symbol.strip().upper()
        if clean_symbol and clean_symbol not in seen:
            normalized.append(clean_symbol)
            seen.add(clean_symbol)
    return normalized


def _universe_asset_metadata(symbol: str) -> dict[str, Any]:
    universe = get_current_universe()
    for member in universe.members:
        if member.asset.symbol.upper() == symbol:
            return member.asset.model_dump(mode="json")
    return {}


def _display_exchange(exchange: str) -> str:
    mapping = {
        "NAS": "NASDAQ",
        "NASD": "NASDAQ",
        "NYS": "NYSE",
        "NYSE": "NYSE",
        "AMS": "NYSEAMERICAN",
        "AMEX": "NYSEAMERICAN",
    }
    return mapping.get(exchange.upper(), exchange.upper())


def _json_payload(payload: dict[str, Any]) -> dict[str, Any]:
    return payload or {}
