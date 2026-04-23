from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.brokers.kis import KISBrokerAdapter
from app.core.config import Settings, get_settings
from app.core.security import require_admin
from app.db.session import get_db_session
from app.services.market_calendar import MarketClosedError, USEquityMarketCalendar
from app.services.market_data import MarketDataService
from app.services.universe import (
    UniverseCandidate,
    UniverseEngine,
    get_current_universe,
    kis_exchange_code_for_symbol,
)

router = APIRouter(dependencies=[Depends(require_admin)])

DbSession = Annotated[Session, Depends(get_db_session)]
AppSettings = Annotated[Settings, Depends(get_settings)]


class AgentCandidatePayload(BaseModel):
    symbol: str
    name: str | None = None
    asset_type: str | None = None
    exchange: str | None = None
    rationale: str = "Agent-recommended universe candidate."
    is_us_listed: bool = True
    is_otc: bool = False
    leveraged_inverse_flag: bool = False
    supported_by_broker: bool = True


class UniverseRefreshRequest(BaseModel):
    agent_candidates: list[AgentCandidatePayload] = Field(default_factory=list)
    fetch_market_data: bool = True
    force_new_version: bool = False
    notes: str | None = None


@router.get("/current")
def current_universe(db: DbSession) -> dict[str, object]:
    return get_current_universe(db).model_dump(mode="json")


@router.post("/refresh", status_code=status.HTTP_202_ACCEPTED)
async def refresh_universe(
    db: DbSession,
    settings: AppSettings,
    request: UniverseRefreshRequest | None = None,
) -> dict[str, object]:
    payload = request or UniverseRefreshRequest()
    engine = UniverseEngine(db=db, settings=settings)
    agent_candidates = [
        _agent_candidate_from_payload(candidate) for candidate in payload.agent_candidates
    ]
    market_data_errors: list[dict[str, str]] = []

    if payload.fetch_market_data:
        market_data_errors = await _refresh_candidate_market_data(
            db=db,
            settings=settings,
            symbols=[
                *engine.candidate_symbols(),
                *[candidate.symbol for candidate in agent_candidates],
            ],
        )

    try:
        result = engine.refresh_universe(
            agent_candidates=agent_candidates,
            force_new_version=payload.force_new_version,
            notes=payload.notes,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "message": str(exc),
                "marketDataErrors": market_data_errors,
            },
        ) from exc

    response = result.universe.model_dump(mode="json")
    response["refreshStatus"] = "accepted"
    response["acceptedCount"] = result.accepted_count
    response["rejectedCount"] = result.rejected_count
    response["marketDataErrors"] = market_data_errors
    response["refreshedAt"] = result.generated_at.isoformat()
    return response


def _agent_candidate_from_payload(payload: AgentCandidatePayload) -> UniverseCandidate:
    asset_type = payload.asset_type or "common_stock"
    return UniverseCandidate(
        symbol=payload.symbol.upper(),
        name=payload.name or payload.symbol.upper(),
        asset_type=asset_type,
        exchange=payload.exchange or "NASDAQ",
        rationale=payload.rationale,
        source="agent",
        is_us_listed=payload.is_us_listed,
        is_otc=payload.is_otc,
        leveraged_inverse_flag=payload.leveraged_inverse_flag
        or asset_type in {"leveraged_etf", "inverse_etf"},
        supported_by_broker=payload.supported_by_broker,
    )


async def _refresh_candidate_market_data(
    *,
    db: Session,
    settings: Settings,
    symbols: list[str],
) -> list[dict[str, str]]:
    broker = KISBrokerAdapter(settings=settings)
    service = MarketDataService(db=db, broker=broker, settings=settings)
    calendar = USEquityMarketCalendar.from_settings(settings)
    status_snapshot = calendar.status()
    errors: list[dict[str, str]] = []
    seen: set[str] = set()

    try:
        for raw_symbol in symbols:
            symbol = raw_symbol.strip().upper()
            if not symbol or symbol in seen:
                continue
            seen.add(symbol)
            try:
                exchange = kis_exchange_code_for_symbol(symbol)
                await service.backfill_candles(symbol, exchange=exchange)
                if status_snapshot.isOpen:
                    await service.snapshot_quote(symbol, exchange=exchange, now=datetime.now(UTC))
            except MarketClosedError:
                continue
            except Exception as exc:  # noqa: BLE001
                db.rollback()
                errors.append({"symbol": symbol, "error": str(exc)})
    finally:
        await broker.close()
    return errors
