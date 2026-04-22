from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.brokers.kis import KISBrokerAdapter
from app.core.config import Settings, get_settings
from app.core.security import require_admin
from app.db.session import get_db_session
from app.services.market_calendar import (
    MarketClosedError,
    USEquityMarketCalendar,
)
from app.services.market_data import (
    CandleBackfillResult,
    DailyRefreshResult,
    MarketDataService,
    QuoteSnapshotResult,
)

router = APIRouter(dependencies=[Depends(require_admin)])

DbSession = Annotated[Session, Depends(get_db_session)]
AppSettings = Annotated[Settings, Depends(get_settings)]
ExchangeQuery = Annotated[str, Query()]
RegularSessionQuery = Annotated[bool, Query()]
DateQuery = Annotated[date | None, Query()]
TimeframeQuery = Annotated[str, Query()]
SymbolsQuery = Annotated[str, Query()]


@router.get("/status")
def market_status(settings: AppSettings) -> dict[str, object]:
    calendar = USEquityMarketCalendar.from_settings(settings)
    return calendar.status().model_dump(mode="json")


@router.get("/quotes/{symbol}/latest")
def latest_quote(symbol: str, db: DbSession, settings: AppSettings) -> dict[str, object]:
    service = MarketDataService(
        db=db,
        broker=KISBrokerAdapter(settings=settings),
        settings=settings,
    )
    result = service.latest_quote(symbol)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No quote snapshot exists for {symbol.upper()}.",
        )
    return _quote_result(result)


@router.post("/quotes/{symbol}/snapshot")
async def snapshot_quote(
    symbol: str,
    db: DbSession,
    settings: AppSettings,
    exchange: ExchangeQuery = "NAS",
    enforce_regular_session: RegularSessionQuery = True,
) -> dict[str, object]:
    broker = KISBrokerAdapter(settings=settings)
    service = MarketDataService(db=db, broker=broker, settings=settings)
    try:
        result = await service.snapshot_quote(
            symbol,
            exchange=exchange,
            enforce_regular_session=enforce_regular_session,
        )
    except MarketClosedError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    finally:
        await broker.close()
    return _quote_result(result)


@router.post("/candles/{symbol}/backfill")
async def backfill_candles(
    symbol: str,
    db: DbSession,
    settings: AppSettings,
    start: DateQuery = None,
    end: DateQuery = None,
    timeframe: TimeframeQuery = "D",
    exchange: ExchangeQuery = "NAS",
) -> dict[str, object]:
    broker = KISBrokerAdapter(settings=settings)
    service = MarketDataService(db=db, broker=broker, settings=settings)
    try:
        result = await service.backfill_candles(
            symbol,
            start=start,
            end=end,
            timeframe=timeframe,
            exchange=exchange,
        )
    finally:
        await broker.close()
    return _candle_result(result)


@router.post("/refresh/daily")
async def refresh_daily(
    db: DbSession,
    settings: AppSettings,
    symbols: SymbolsQuery = "",
    exchange: ExchangeQuery = "NAS",
) -> dict[str, object]:
    requested_symbols = [symbol.strip() for symbol in symbols.split(",") if symbol.strip()]
    broker = KISBrokerAdapter(settings=settings)
    service = MarketDataService(db=db, broker=broker, settings=settings)
    try:
        result = await service.refresh_daily(
            symbols=requested_symbols or None,
            exchange=exchange,
        )
    finally:
        await broker.close()
    return _daily_refresh_result(result)


def _quote_result(result: QuoteSnapshotResult) -> dict[str, object]:
    return {
        "quoteId": str(result.quote_id),
        "symbol": result.symbol,
        "last": str(result.last),
        "bid": str(result.bid) if result.bid is not None else None,
        "ask": str(result.ask) if result.ask is not None else None,
        "currency": result.currency,
        "quoteTime": result.quote_time.isoformat(),
        "freshness": {
            "isFresh": result.freshness.is_fresh,
            "ageSeconds": result.freshness.age_seconds,
            "thresholdSeconds": result.freshness.threshold_seconds,
            "reason": result.freshness.reason,
        },
    }


def _candle_result(result: CandleBackfillResult) -> dict[str, object]:
    return {
        "symbol": result.symbol,
        "timeframe": result.timeframe,
        "requestedStart": result.requested_start.isoformat(),
        "requestedEnd": result.requested_end.isoformat(),
        "fetchedCount": result.fetched_count,
        "upsertedCount": result.upserted_count,
        "skippedCount": result.skipped_count,
    }


def _daily_refresh_result(result: DailyRefreshResult) -> dict[str, object]:
    return {
        "symbols": result.symbols,
        "candleResults": [_candle_result(candle_result) for candle_result in result.candle_results],
        "quoteResults": [_quote_result(quote_result) for quote_result in result.quote_results],
        "skippedQuoteReason": result.skipped_quote_reason,
        "refreshedAt": result.refreshed_at.isoformat(),
    }
