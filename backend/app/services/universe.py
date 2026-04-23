from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from math import log10
from typing import Any

import sqlalchemy as sa
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.models import Asset as AssetRow
from app.db.models import AssetUniverseMember as AssetUniverseMemberRow
from app.db.models import AssetUniverseVersion as AssetUniverseVersionRow
from app.db.models import Candle as CandleRow
from app.db.models import MarketQuote as MarketQuoteRow
from app.domain.models import Asset, AssetType, UniverseMember, UniverseVersion

SUPPORTED_ASSET_TYPES = {
    AssetType.COMMON_STOCK.value,
    AssetType.BROAD_ETF.value,
    AssetType.SECTOR_ETF.value,
    AssetType.LEVERAGED_ETF.value,
    AssetType.INVERSE_ETF.value,
}
OTC_EXCHANGES = {"OTC", "OTCM", "OTCQB", "OTCQX", "PINK", "GREY"}


@dataclass(frozen=True)
class UniverseCandidate:
    symbol: str
    name: str
    asset_type: str
    exchange: str
    rationale: str
    source: str
    is_us_listed: bool = True
    is_otc: bool = False
    leveraged_inverse_flag: bool = False
    supported_by_broker: bool = True


@dataclass(frozen=True)
class MarketMetrics:
    latest_price: Decimal | None = None
    latest_quote_time: datetime | None = None
    bid: Decimal | None = None
    ask: Decimal | None = None
    spread_bps: Decimal | None = None
    avg_dollar_volume: Decimal | None = None
    history_days: int = 0


@dataclass(frozen=True)
class UniverseFilterDecision:
    candidate: UniverseCandidate
    accepted: bool
    score: float
    reasons: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    metrics: MarketMetrics = field(default_factory=MarketMetrics)

    def snapshot(self) -> dict[str, Any]:
        return {
            "symbol": self.candidate.symbol,
            "source": self.candidate.source,
            "accepted": self.accepted,
            "score": round(self.score, 4),
            "reasons": self.reasons,
            "warnings": self.warnings,
            "metrics": {
                "latestPrice": _decimal_or_none(self.metrics.latest_price),
                "latestQuoteTime": (
                    self.metrics.latest_quote_time.isoformat()
                    if self.metrics.latest_quote_time
                    else None
                ),
                "bid": _decimal_or_none(self.metrics.bid),
                "ask": _decimal_or_none(self.metrics.ask),
                "spreadBps": _decimal_or_none(self.metrics.spread_bps),
                "avgDollarVolume": _decimal_or_none(self.metrics.avg_dollar_volume),
                "historyDays": self.metrics.history_days,
            },
        }


@dataclass(frozen=True)
class UniverseRefreshResult:
    universe: UniverseVersion
    accepted_count: int
    rejected_count: int
    generated_at: datetime


class UniverseEngine:
    def __init__(self, *, db: Session, settings: Settings | None = None) -> None:
        self.db = db
        self.settings = settings or get_settings()

    def candidate_symbols(self) -> list[str]:
        return _dedupe_symbols(self.settings.universe_seed_symbol_list)

    def get_current_universe(self) -> UniverseVersion:
        return get_current_universe(self.db)

    def refresh_universe(
        self,
        *,
        agent_candidates: list[UniverseCandidate] | None = None,
        force_new_version: bool = False,
        notes: str | None = None,
    ) -> UniverseRefreshResult:
        generated_at = datetime.now(UTC)
        candidates = self._dedupe_candidates(
            [
                *self._configured_candidates(),
                *(agent_candidates or []),
                *self._asset_candidates_from_market_data(),
            ]
        )
        decisions = [
            evaluate_candidate(
                candidate,
                self._market_metrics(candidate.symbol),
                settings=self.settings,
            )
            for candidate in candidates
        ]
        accepted_decisions = sorted(
            [decision for decision in decisions if decision.accepted],
            key=lambda decision: decision.score,
            reverse=True,
        )[: self.settings.universe_max_members]
        rejected_decisions = [decision for decision in decisions if not decision.accepted]
        if not accepted_decisions:
            raise ValueError("Universe refresh produced no eligible assets.")

        version_row = self._persist_version(
            accepted_decisions,
            rejected_decisions,
            generated_at=generated_at,
            force_new_version=force_new_version,
            notes=notes,
        )
        universe = _version_from_row(version_row, rejected_decisions=rejected_decisions)
        return UniverseRefreshResult(
            universe=universe,
            accepted_count=len(universe.members),
            rejected_count=len(rejected_decisions),
            generated_at=generated_at,
        )

    def _configured_candidates(self) -> list[UniverseCandidate]:
        return [
            candidate_from_symbol(symbol, source="configured", rationale="Configured seed symbol.")
            for symbol in self.candidate_symbols()
        ]

    def _asset_candidates_from_market_data(self) -> list[UniverseCandidate]:
        rows = self.db.scalars(
            sa.select(AssetRow)
            .where(
                sa.or_(
                    AssetRow.id.in_(sa.select(MarketQuoteRow.asset_id)),
                    AssetRow.id.in_(sa.select(CandleRow.asset_id)),
                )
            )
            .order_by(AssetRow.symbol)
        ).all()
        return [
            UniverseCandidate(
                symbol=row.symbol.upper(),
                name=row.name,
                asset_type=row.asset_type,
                exchange=row.exchange,
                rationale="Observed in KIS market data history.",
                source="kis_market_data",
                is_us_listed=row.is_us_listed,
                is_otc=row.is_otc,
                leveraged_inverse_flag=row.leveraged_inverse_flag,
                supported_by_broker=row.supported_by_broker,
            )
            for row in rows
        ]

    def _market_metrics(self, symbol: str) -> MarketMetrics:
        normalized_symbol = symbol.upper()
        quote = self.db.scalars(
            sa.select(MarketQuoteRow)
            .where(MarketQuoteRow.symbol == normalized_symbol)
            .order_by(MarketQuoteRow.quote_time.desc())
            .limit(1)
        ).first()
        since = datetime.now(UTC) - timedelta(days=self.settings.universe_liquidity_lookback_days)
        candles = self.db.scalars(
            sa.select(CandleRow)
            .where(
                CandleRow.symbol == normalized_symbol,
                CandleRow.timeframe == "D",
                CandleRow.open_time >= since,
            )
            .order_by(CandleRow.open_time.desc())
        ).all()

        latest_price = quote.last if quote else None
        latest_quote_time = quote.quote_time if quote else None
        bid = quote.bid if quote else None
        ask = quote.ask if quote else None
        spread_bps = _spread_bps(bid, ask)
        avg_dollar_volume = _average_dollar_volume(candles)
        if latest_price is None and candles:
            latest_price = candles[0].adjusted_close or candles[0].close

        return MarketMetrics(
            latest_price=latest_price,
            latest_quote_time=latest_quote_time,
            bid=bid,
            ask=ask,
            spread_bps=spread_bps,
            avg_dollar_volume=avg_dollar_volume,
            history_days=len(candles),
        )

    def _persist_version(
        self,
        accepted_decisions: list[UniverseFilterDecision],
        rejected_decisions: list[UniverseFilterDecision],
        *,
        generated_at: datetime,
        force_new_version: bool,
        notes: str | None,
    ) -> AssetUniverseVersionRow:
        version_code = _weekly_version_code(generated_at)
        if force_new_version:
            version_code = f"{version_code}-{generated_at:%Y%m%d%H%M%S}"

        version_row = self.db.scalars(
            sa.select(AssetUniverseVersionRow).where(
                AssetUniverseVersionRow.version_code == version_code
            )
        ).first()
        if version_row is None:
            version_row = AssetUniverseVersionRow(
                version_code=version_code,
                status="active",
                source="universe_engine",
                generated_at=generated_at,
                activated_at=generated_at,
                notes=notes,
                version_metadata={},
            )
            self.db.add(version_row)
            self.db.flush()
        else:
            version_row.status = "active"
            version_row.generated_at = generated_at
            version_row.activated_at = generated_at
            version_row.notes = notes
            self.db.execute(
                sa.delete(AssetUniverseMemberRow).where(
                    AssetUniverseMemberRow.universe_version_id == version_row.id
                )
            )

        self.db.execute(
            sa.update(AssetUniverseVersionRow)
            .where(
                AssetUniverseVersionRow.id != version_row.id,
                AssetUniverseVersionRow.status == "active",
            )
            .values(status="archived")
        )

        version_row.version_metadata = {
            "engine": "phase_5_universe_engine",
            "acceptedCount": len(accepted_decisions),
            "rejectedCount": len(rejected_decisions),
            "thresholds": _threshold_snapshot(self.settings),
            "rejectedCandidates": [decision.snapshot() for decision in rejected_decisions],
        }
        for rank, decision in enumerate(accepted_decisions, start=1):
            asset_row = self._upsert_asset(decision.candidate)
            self.db.add(
                AssetUniverseMemberRow(
                    universe_version_id=version_row.id,
                    asset_id=asset_row.id,
                    rank=rank,
                    rationale=decision.candidate.rationale,
                    eligibility_snapshot=decision.snapshot(),
                )
            )

        self.db.commit()
        self.db.refresh(version_row)
        self.db.expire(version_row, ["members"])
        return version_row

    def _upsert_asset(self, candidate: UniverseCandidate) -> AssetRow:
        asset = self.db.scalars(
            sa.select(AssetRow).where(AssetRow.symbol == candidate.symbol)
        ).first()
        metadata = {
            "universeSource": candidate.source,
            "lastUniverseRefreshAt": datetime.now(UTC).isoformat(),
        }
        if asset is None:
            asset = AssetRow(
                symbol=candidate.symbol,
                name=candidate.name,
                asset_type=candidate.asset_type,
                exchange=candidate.exchange,
                currency="USD",
                country="US",
                is_us_listed=candidate.is_us_listed,
                is_otc=candidate.is_otc,
                leveraged_inverse_flag=candidate.leveraged_inverse_flag,
                supported_by_broker=candidate.supported_by_broker,
                asset_metadata=metadata,
            )
            self.db.add(asset)
            self.db.flush()
            return asset

        asset.name = candidate.name
        asset.asset_type = candidate.asset_type
        asset.exchange = candidate.exchange
        asset.is_us_listed = candidate.is_us_listed
        asset.is_otc = candidate.is_otc
        asset.leveraged_inverse_flag = candidate.leveraged_inverse_flag
        asset.supported_by_broker = candidate.supported_by_broker
        asset.asset_metadata = {**(asset.asset_metadata or {}), **metadata}
        return asset

    def _dedupe_candidates(self, candidates: list[UniverseCandidate]) -> list[UniverseCandidate]:
        seen: dict[str, UniverseCandidate] = {}
        for candidate in candidates:
            normalized = _normalize_candidate(candidate)
            if normalized.symbol not in seen or normalized.source == "agent":
                seen[normalized.symbol] = normalized
        return list(seen.values())


def get_current_universe(db: Session | None = None) -> UniverseVersion:
    if db is not None:
        try:
            version_row = db.scalars(
                sa.select(AssetUniverseVersionRow)
                .where(AssetUniverseVersionRow.status == "active")
                .order_by(
                    AssetUniverseVersionRow.activated_at.desc().nullslast(),
                    AssetUniverseVersionRow.generated_at.desc(),
                )
                .limit(1)
            ).first()
        except SQLAlchemyError:
            db.rollback()
            return _bootstrap_universe()
        if version_row is not None:
            return _version_from_row(version_row)
    return _bootstrap_universe()


def candidate_from_symbol(
    symbol: str,
    *,
    source: str,
    rationale: str,
    name: str | None = None,
    asset_type: str | None = None,
    exchange: str | None = None,
) -> UniverseCandidate:
    normalized_symbol = symbol.strip().upper()
    metadata = DEFAULT_ASSET_METADATA.get(normalized_symbol, {})
    resolved_asset_type = asset_type or str(
        metadata.get("asset_type") or AssetType.COMMON_STOCK.value
    )
    leveraged_inverse = resolved_asset_type in {
        AssetType.LEVERAGED_ETF.value,
        AssetType.INVERSE_ETF.value,
    }
    return UniverseCandidate(
        symbol=normalized_symbol,
        name=name or str(metadata.get("name") or normalized_symbol),
        asset_type=resolved_asset_type,
        exchange=exchange or str(metadata.get("exchange") or "NASDAQ"),
        rationale=rationale,
        source=source,
        leveraged_inverse_flag=leveraged_inverse,
        is_otc=_looks_otc(normalized_symbol, exchange or str(metadata.get("exchange") or "")),
    )


def kis_exchange_code_for_symbol(symbol: str) -> str:
    metadata = DEFAULT_ASSET_METADATA.get(symbol.strip().upper(), {})
    exchange = str(metadata.get("exchange") or "NASDAQ").upper()
    if exchange in {"NYSEARCA", "NYSEAMERICAN", "AMEX"}:
        return "AMS"
    if exchange == "NYSE":
        return "NYS"
    return "NAS"


def evaluate_candidate(
    candidate: UniverseCandidate,
    metrics: MarketMetrics,
    *,
    settings: Settings | None = None,
) -> UniverseFilterDecision:
    resolved_settings = settings or get_settings()
    normalized = _normalize_candidate(candidate)
    reasons: list[str] = []
    warnings: list[str] = []

    if not normalized.is_us_listed:
        reasons.append("not_us_listed")
    if normalized.is_otc or _looks_otc(normalized.symbol, normalized.exchange):
        reasons.append("otc_excluded")
    if not normalized.supported_by_broker:
        reasons.append("unsupported_by_broker")
    if normalized.asset_type not in SUPPORTED_ASSET_TYPES:
        reasons.append("unsupported_asset_type")
    if normalized.leveraged_inverse_flag and (
        normalized.symbol not in resolved_settings.universe_leveraged_inverse_whitelist_set
    ):
        reasons.append("leveraged_inverse_not_whitelisted")
    if metrics.latest_price is None:
        reasons.append("missing_latest_price")
    elif metrics.latest_price < resolved_settings.universe_min_price_usd:
        reasons.append("below_min_price")
    elif metrics.latest_price > resolved_settings.universe_max_price_usd:
        reasons.append("above_max_price")
    if metrics.avg_dollar_volume is None:
        reasons.append("missing_liquidity_history")
    elif metrics.avg_dollar_volume < resolved_settings.universe_min_avg_dollar_volume_usd:
        reasons.append("below_min_liquidity")
    if metrics.spread_bps is None:
        warnings.append("missing_bid_ask_spread")
    elif metrics.spread_bps > resolved_settings.universe_max_bid_ask_spread_bps:
        reasons.append("spread_too_wide")

    accepted = not reasons
    return UniverseFilterDecision(
        candidate=normalized,
        accepted=accepted,
        score=_candidate_score(normalized, metrics) if accepted else 0,
        reasons=reasons,
        warnings=warnings,
        metrics=metrics,
    )


def _bootstrap_universe() -> UniverseVersion:
    members = [
        UniverseMember(
            rank=1,
            asset=Asset(
                symbol="SPY",
                name="SPDR S&P 500 ETF Trust",
                asset_type=AssetType.BROAD_ETF,
                exchange="NYSEARCA",
            ),
            rationale="Baseline broad-market ETF used as a liquidity and regime anchor.",
        ),
        UniverseMember(
            rank=2,
            asset=Asset(
                symbol="QQQ",
                name="Invesco QQQ Trust",
                asset_type=AssetType.BROAD_ETF,
                exchange="NASDAQ",
            ),
            rationale="Highly liquid growth benchmark for swing and medium-term signals.",
        ),
        UniverseMember(
            rank=3,
            asset=Asset(
                symbol="TQQQ",
                name="ProShares UltraPro QQQ",
                asset_type=AssetType.LEVERAGED_ETF,
                exchange="NASDAQ",
                leveraged_inverse_flag=True,
            ),
            rationale="Whitelisted leveraged ETF with strict exposure limits.",
        ),
        UniverseMember(
            rank=4,
            asset=Asset(
                symbol="SQQQ",
                name="ProShares UltraPro Short QQQ",
                asset_type=AssetType.INVERSE_ETF,
                exchange="NASDAQ",
                leveraged_inverse_flag=True,
            ),
            rationale="Whitelisted inverse ETF for risk-off exposure under strict limits.",
        ),
    ]
    return UniverseVersion(version_id="bootstrap", status="bootstrap", members=members)


def _version_from_row(
    version_row: AssetUniverseVersionRow,
    *,
    rejected_decisions: list[UniverseFilterDecision] | None = None,
) -> UniverseVersion:
    members = sorted(version_row.members, key=lambda member: member.rank)
    metadata = version_row.version_metadata or {}
    rejected = (
        [decision.snapshot() for decision in rejected_decisions]
        if rejected_decisions is not None
        else metadata.get("rejectedCandidates", [])
    )
    return UniverseVersion(
        version_id=version_row.version_code,
        status=version_row.status,
        source=version_row.source,
        generated_at=version_row.generated_at,
        activated_at=version_row.activated_at,
        notes=version_row.notes,
        metadata=metadata,
        rejected_candidates=list(rejected),
        members=[
            UniverseMember(
                rank=member.rank,
                asset=Asset(
                    symbol=member.asset.symbol,
                    name=member.asset.name,
                    asset_type=AssetType(member.asset.asset_type),
                    exchange=member.asset.exchange,
                    is_us_listed=member.asset.is_us_listed,
                    is_otc=member.asset.is_otc,
                    leveraged_inverse_flag=member.asset.leveraged_inverse_flag,
                    supported_by_broker=member.asset.supported_by_broker,
                ),
                rationale=member.rationale,
                eligibility=member.eligibility_snapshot or {},
            )
            for member in members
        ],
    )


def _normalize_candidate(candidate: UniverseCandidate) -> UniverseCandidate:
    symbol = candidate.symbol.strip().upper()
    asset_type = candidate.asset_type.strip().lower()
    leveraged_inverse = candidate.leveraged_inverse_flag or asset_type in {
        AssetType.LEVERAGED_ETF.value,
        AssetType.INVERSE_ETF.value,
    }
    return UniverseCandidate(
        symbol=symbol,
        name=candidate.name.strip() or symbol,
        asset_type=asset_type,
        exchange=candidate.exchange.strip().upper() or "NASDAQ",
        rationale=candidate.rationale.strip() or "Universe candidate.",
        source=candidate.source.strip() or "system",
        is_us_listed=candidate.is_us_listed,
        is_otc=candidate.is_otc,
        leveraged_inverse_flag=leveraged_inverse,
        supported_by_broker=candidate.supported_by_broker,
    )


def _weekly_version_code(generated_at: datetime) -> str:
    iso_year, iso_week, _ = generated_at.isocalendar()
    return f"universe-{iso_year}-W{iso_week:02d}"


def _average_dollar_volume(candles: list[CandleRow]) -> Decimal | None:
    if not candles:
        return None
    total = Decimal("0")
    for candle in candles:
        close = candle.adjusted_close or candle.close
        total += close * candle.volume
    return total / Decimal(len(candles))


def _spread_bps(bid: Decimal | None, ask: Decimal | None) -> Decimal | None:
    if bid is None or ask is None or bid <= 0 or ask <= 0 or ask < bid:
        return None
    midpoint = (bid + ask) / Decimal("2")
    if midpoint <= 0:
        return None
    return ((ask - bid) / midpoint) * Decimal("10000")


def _candidate_score(candidate: UniverseCandidate, metrics: MarketMetrics) -> float:
    liquidity_score = 0.0
    if metrics.avg_dollar_volume and metrics.avg_dollar_volume > 0:
        liquidity_score = min(log10(float(metrics.avg_dollar_volume)), 12.0)
    spread_penalty = float(metrics.spread_bps or Decimal("0")) / 100
    source_bonus = 1.0 if candidate.source == "agent" else 0.0
    etf_bonus = 0.5 if candidate.asset_type != AssetType.COMMON_STOCK.value else 0.0
    return liquidity_score + source_bonus + etf_bonus - spread_penalty


def _dedupe_symbols(symbols: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for symbol in symbols:
        normalized = symbol.strip().upper()
        if normalized and normalized not in seen:
            result.append(normalized)
            seen.add(normalized)
    return result


def _looks_otc(symbol: str, exchange: str) -> bool:
    return "." in symbol or exchange.strip().upper() in OTC_EXCHANGES


def _threshold_snapshot(settings: Settings) -> dict[str, str | int]:
    return {
        "maxMembers": settings.universe_max_members,
        "minPriceUsd": str(settings.universe_min_price_usd),
        "maxPriceUsd": str(settings.universe_max_price_usd),
        "minAvgDollarVolumeUsd": str(settings.universe_min_avg_dollar_volume_usd),
        "maxBidAskSpreadBps": str(settings.universe_max_bid_ask_spread_bps),
        "liquidityLookbackDays": settings.universe_liquidity_lookback_days,
        "leveragedInverseWhitelist": ",".join(
            sorted(settings.universe_leveraged_inverse_whitelist_set)
        ),
    }


def _decimal_or_none(value: Decimal | None) -> str | None:
    return str(value) if value is not None else None


DEFAULT_ASSET_METADATA: dict[str, dict[str, str]] = {
    "SPY": {
        "name": "SPDR S&P 500 ETF Trust",
        "asset_type": AssetType.BROAD_ETF.value,
        "exchange": "NYSEARCA",
    },
    "QQQ": {
        "name": "Invesco QQQ Trust",
        "asset_type": AssetType.BROAD_ETF.value,
        "exchange": "NASDAQ",
    },
    "DIA": {
        "name": "SPDR Dow Jones Industrial Average ETF Trust",
        "asset_type": AssetType.BROAD_ETF.value,
        "exchange": "NYSEARCA",
    },
    "IWM": {
        "name": "iShares Russell 2000 ETF",
        "asset_type": AssetType.BROAD_ETF.value,
        "exchange": "NYSEARCA",
    },
    "VTI": {
        "name": "Vanguard Total Stock Market ETF",
        "asset_type": AssetType.BROAD_ETF.value,
        "exchange": "NYSEARCA",
    },
    "TLT": {
        "name": "iShares 20+ Year Treasury Bond ETF",
        "asset_type": AssetType.BROAD_ETF.value,
        "exchange": "NASDAQ",
    },
    "GLD": {
        "name": "SPDR Gold Shares",
        "asset_type": AssetType.BROAD_ETF.value,
        "exchange": "NYSEARCA",
    },
    "XLK": {
        "name": "Technology Select Sector SPDR Fund",
        "asset_type": AssetType.SECTOR_ETF.value,
        "exchange": "NYSEARCA",
    },
    "XLF": {
        "name": "Financial Select Sector SPDR Fund",
        "asset_type": AssetType.SECTOR_ETF.value,
        "exchange": "NYSEARCA",
    },
    "XLV": {
        "name": "Health Care Select Sector SPDR Fund",
        "asset_type": AssetType.SECTOR_ETF.value,
        "exchange": "NYSEARCA",
    },
    "XLE": {
        "name": "Energy Select Sector SPDR Fund",
        "asset_type": AssetType.SECTOR_ETF.value,
        "exchange": "NYSEARCA",
    },
    "XLI": {
        "name": "Industrial Select Sector SPDR Fund",
        "asset_type": AssetType.SECTOR_ETF.value,
        "exchange": "NYSEARCA",
    },
    "XLY": {
        "name": "Consumer Discretionary Select Sector SPDR Fund",
        "asset_type": AssetType.SECTOR_ETF.value,
        "exchange": "NYSEARCA",
    },
    "XLP": {
        "name": "Consumer Staples Select Sector SPDR Fund",
        "asset_type": AssetType.SECTOR_ETF.value,
        "exchange": "NYSEARCA",
    },
    "SMH": {
        "name": "VanEck Semiconductor ETF",
        "asset_type": AssetType.SECTOR_ETF.value,
        "exchange": "NASDAQ",
    },
    "TQQQ": {
        "name": "ProShares UltraPro QQQ",
        "asset_type": AssetType.LEVERAGED_ETF.value,
        "exchange": "NASDAQ",
    },
    "SQQQ": {
        "name": "ProShares UltraPro Short QQQ",
        "asset_type": AssetType.INVERSE_ETF.value,
        "exchange": "NASDAQ",
    },
    "SOXL": {
        "name": "Direxion Daily Semiconductor Bull 3X Shares",
        "asset_type": AssetType.LEVERAGED_ETF.value,
        "exchange": "NYSEARCA",
    },
    "SOXS": {
        "name": "Direxion Daily Semiconductor Bear 3X Shares",
        "asset_type": AssetType.INVERSE_ETF.value,
        "exchange": "NYSEARCA",
    },
    "UPRO": {
        "name": "ProShares UltraPro S&P500",
        "asset_type": AssetType.LEVERAGED_ETF.value,
        "exchange": "NYSEARCA",
    },
    "SPXU": {
        "name": "ProShares UltraPro Short S&P500",
        "asset_type": AssetType.INVERSE_ETF.value,
        "exchange": "NYSEARCA",
    },
    "AAPL": {
        "name": "Apple Inc.",
        "asset_type": AssetType.COMMON_STOCK.value,
        "exchange": "NASDAQ",
    },
    "MSFT": {
        "name": "Microsoft Corporation",
        "asset_type": AssetType.COMMON_STOCK.value,
        "exchange": "NASDAQ",
    },
    "NVDA": {
        "name": "NVIDIA Corporation",
        "asset_type": AssetType.COMMON_STOCK.value,
        "exchange": "NASDAQ",
    },
    "AMZN": {
        "name": "Amazon.com Inc.",
        "asset_type": AssetType.COMMON_STOCK.value,
        "exchange": "NASDAQ",
    },
    "GOOGL": {
        "name": "Alphabet Inc. Class A",
        "asset_type": AssetType.COMMON_STOCK.value,
        "exchange": "NASDAQ",
    },
    "META": {
        "name": "Meta Platforms Inc.",
        "asset_type": AssetType.COMMON_STOCK.value,
        "exchange": "NASDAQ",
    },
    "TSLA": {
        "name": "Tesla Inc.",
        "asset_type": AssetType.COMMON_STOCK.value,
        "exchange": "NASDAQ",
    },
}
