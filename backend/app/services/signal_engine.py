from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

import sqlalchemy as sa
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.models import Asset as AssetRow
from app.db.models import Candle as CandleRow
from app.db.models import Signal as SignalRow
from app.domain.models import (
    Asset,
    AssetType,
    Signal,
    SignalIndicators,
    SignalRegime,
    TradeAction,
)
from app.services.indicators import atr, macd, realized_volatility, roc, rsi, sma
from app.services.risk_policy import DEFAULT_RISK_POLICY, RiskPolicy
from app.services.universe import get_current_universe


@dataclass(frozen=True)
class PriceBar:
    open_time: datetime
    close_time: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass(frozen=True)
class SignalCandidate:
    signal: Signal
    indicators: SignalIndicators
    regime: SignalRegime
    score: float
    strategy: str
    source_symbol: str


@dataclass(frozen=True)
class SignalScanResult:
    generated_at: datetime
    universe_version_id: str
    regime: SignalRegime
    signals: list[dict[str, Any]]
    skipped: list[dict[str, str]]


class SignalEngine:
    def __init__(
        self,
        *,
        db: Session,
        settings: Settings | None = None,
        risk_policy: RiskPolicy = DEFAULT_RISK_POLICY,
    ) -> None:
        self.db = db
        self.settings = settings or get_settings()
        self.risk_policy = risk_policy

    def list_signals(self, *, limit: int = 20) -> list[dict[str, Any]]:
        now = datetime.now(UTC)
        try:
            self._expire_stale_signals(now)
            rows = self.db.scalars(
                sa.select(SignalRow).order_by(SignalRow.generated_at.desc()).limit(limit)
            ).all()
            return [_serialize_signal_row(row) for row in rows]
        except SQLAlchemyError:
            self.db.rollback()
            return []

    def scan_active_universe(self, *, ignore_cooldown: bool = False) -> SignalScanResult:
        generated_at = datetime.now(UTC)
        self._expire_stale_signals(generated_at)
        universe = get_current_universe(self.db)
        regime = self._build_regime(universe.members)

        candidates: list[SignalCandidate] = []
        skipped: list[dict[str, str]] = []
        for member in universe.members:
            if not ignore_cooldown and self._is_on_cooldown(member.asset.symbol, generated_at):
                skipped.append({
                    "symbol": member.asset.symbol,
                    "reason": (
                        "same_symbol_cooldown_"
                        f"{self.risk_policy.same_symbol_cooldown_days}d"
                    ),
                })
                continue
            bars = self._load_daily_bars(member.asset.symbol)
            if len(bars) < self.settings.signal_min_history_days:
                skipped.append({"symbol": member.asset.symbol, "reason": "insufficient_history"})
                continue
            candidate = evaluate_signal_candidate(
                member.asset,
                bars,
                regime=regime,
                generated_at=generated_at,
                settings=self.settings,
            )
            if candidate is None:
                skipped.append({"symbol": member.asset.symbol, "reason": "no_signal"})
                continue
            candidates.append(candidate)

        candidates.sort(key=lambda candidate: candidate.score, reverse=True)
        persisted = [self._persist_signal(candidate) for candidate in candidates]
        self.db.commit()
        return SignalScanResult(
            generated_at=generated_at,
            universe_version_id=universe.version_id,
            regime=regime,
            signals=persisted,
            skipped=skipped,
        )

    def _expire_stale_signals(self, now: datetime) -> None:
        self.db.execute(
            sa.update(SignalRow)
            .where(
                SignalRow.status == "new",
                SignalRow.expires_at < now,
            )
            .values(status="expired")
        )
        self.db.flush()

    def _build_regime(self, members: list[Any]) -> SignalRegime:
        benchmark_symbol = "SPY"
        available_symbols = {member.asset.symbol for member in members}
        if benchmark_symbol not in available_symbols and "QQQ" in available_symbols:
            benchmark_symbol = "QQQ"
        bars = self._load_daily_bars(benchmark_symbol)
        if len(bars) < 200:
            return SignalRegime(
                benchmark_symbol=benchmark_symbol,
                state="unknown",
                reason="Benchmark history unavailable; falling back to symbol-level trend filters.",
            )

        indicators = _indicator_snapshot(bars)
        close = bars[-1].close
        sma200 = indicators.sma200 or close
        realized_vol20 = indicators.realized_vol20 or 0.0
        risk_on = (
            close > sma200
            and realized_vol20 <= self.settings.signal_volatility_max_annualized
        )
        return SignalRegime(
            benchmark_symbol=benchmark_symbol,
            state="risk_on" if risk_on else "risk_off",
            reason=(
                "Benchmark above 200D moving average with contained volatility."
                if risk_on
                else "Benchmark below 200D moving average or volatility regime is elevated."
            ),
            benchmark_close=round(close, 4),
            benchmark_sma200=round(sma200, 4),
            benchmark_realized_vol20=round(realized_vol20, 4),
        )

    def _load_daily_bars(self, symbol: str) -> list[PriceBar]:
        rows = self.db.scalars(
            sa.select(CandleRow)
            .where(
                CandleRow.symbol == symbol.upper(),
                CandleRow.timeframe == "D",
            )
            .order_by(CandleRow.open_time.desc())
            .limit(self.settings.signal_lookback_days)
        ).all()
        bars = [
            PriceBar(
                open_time=row.open_time,
                close_time=row.close_time,
                open=float(row.open),
                high=float(row.high),
                low=float(row.low),
                close=float(row.adjusted_close or row.close),
                volume=float(row.volume),
            )
            for row in reversed(rows)
        ]
        return bars

    def _is_on_cooldown(self, symbol: str, now: datetime) -> bool:
        threshold = now - timedelta(days=self.risk_policy.same_symbol_cooldown_days)
        row = self.db.scalars(
            sa.select(SignalRow)
            .where(
                SignalRow.symbol == symbol.upper(),
                SignalRow.generated_at >= threshold,
                SignalRow.status.in_(("new", "approved", "submitted", "filled")),
            )
            .order_by(SignalRow.generated_at.desc())
            .limit(1)
        ).first()
        return row is not None

    def _persist_signal(self, candidate: SignalCandidate) -> dict[str, Any]:
        asset_row = self._ensure_asset(candidate.source_symbol)
        signal = candidate.signal
        signal_row = SignalRow(
            asset_id=asset_row.id,
            symbol=signal.symbol,
            action=signal.action.value,
            horizon=signal.horizon,
            confidence=_decimal(signal.confidence, "0.0001"),
            target_weight=_decimal(signal.target_weight, "0.000001"),
            source=signal.source,
            rationale=signal.rationale,
            invalidation=signal.invalidation,
            input_snapshot={
                "strategy": candidate.strategy,
                "indicators": (
                    signal.indicators.model_dump(mode="json") if signal.indicators else {}
                ),
                "regime": signal.regime.model_dump(mode="json") if signal.regime else {},
                "metadata": signal.metadata,
            },
            generated_at=signal.generated_at,
            expires_at=signal.expires_at or (signal.generated_at + timedelta(days=1)),
            status=signal.status,
        )
        self.db.add(signal_row)
        self.db.flush()
        self.db.refresh(signal_row)
        return _serialize_signal_row(signal_row)

    def _ensure_asset(self, symbol: str) -> AssetRow:
        asset_row = self.db.scalars(
            sa.select(AssetRow).where(AssetRow.symbol == symbol.upper())
        ).first()
        if asset_row is None:
            raise ValueError(f"Asset {symbol.upper()} is missing from assets table.")
        return asset_row


def evaluate_signal_candidate(
    asset: Asset,
    bars: list[PriceBar],
    *,
    regime: SignalRegime,
    generated_at: datetime,
    settings: Settings | None = None,
) -> SignalCandidate | None:
    resolved_settings = settings or get_settings()
    indicators = _indicator_snapshot(bars)
    if (
        indicators.sma20 is None
        or indicators.sma50 is None
        or indicators.sma200 is None
        or indicators.rsi14 is None
        or indicators.roc20 is None
        or indicators.macd is None
        or indicators.macd_signal is None
        or indicators.macd_hist is None
        or indicators.atr14_pct is None
        or indicators.realized_vol20 is None
    ):
        return None

    closes = [bar.close for bar in bars]
    last_close = closes[-1]
    previous_close = closes[-2]
    recent_high_20 = max(closes[-20:])
    recent_low_pullback = min(closes[-resolved_settings.signal_pullback_lookback_days :])
    sma50_5 = _safe_recent(_series_sma(closes, 50), 5)

    volatility_limit = _volatility_limit(asset, resolved_settings)
    trend_base = (
        last_close > indicators.sma50 > indicators.sma200
        and indicators.sma20 >= indicators.sma50
        and sma50_5 is not None
        and indicators.sma50 > sma50_5
    )
    momentum_ok = (
        indicators.roc20 > 0
        and indicators.macd > indicators.macd_signal
        and indicators.macd_hist > 0
    )
    volatility_ok = (
        indicators.realized_vol20 <= volatility_limit
        and indicators.atr14_pct <= _atr_limit(asset)
    )
    regime_ok = _regime_allows_entry(asset, regime)

    trend_signal = None
    if (
        trend_base
        and momentum_ok
        and volatility_ok
        and regime_ok
        and indicators.rsi14 >= 52
        and indicators.rsi14 <= 78
        and last_close >= recent_high_20 * 0.99
    ):
        confidence = min(
            0.92,
            0.58
            + max(min(indicators.roc20 / 100, 0.12), 0.0)
            + min(indicators.macd_hist / max(last_close, 1.0) * 120, 0.08)
            + 0.06,
        )
        trend_signal = SignalCandidate(
            signal=_build_signal(
                asset,
                strategy="trend_following",
                horizon="medium_term",
                confidence=confidence,
                target_weight=_target_weight(asset, confidence),
                rationale=(
                    f"{asset.symbol} remains above 50D/200D trend support, momentum is positive, "
                    f"and price is holding near the 20-day high."
                ),
                invalidation="Daily close below 50D moving average or MACD bearish crossover.",
                generated_at=generated_at,
                indicators=indicators,
                regime=regime,
                settings=resolved_settings,
                metadata={
                    "trendAligned": trend_base,
                    "momentumConfirmed": momentum_ok,
                    "volatilityPassed": volatility_ok,
                },
            ),
            indicators=indicators,
            regime=regime,
            score=confidence,
            strategy="trend_following",
            source_symbol=asset.symbol,
        )

    pullback_signal = None
    if (
        trend_base
        and volatility_ok
        and regime_ok
        and recent_low_pullback <= indicators.sma20 * 1.01
        and last_close > indicators.sma20
        and previous_close <= indicators.sma20
        and indicators.rsi14 >= 45
        and indicators.rsi14 <= 68
        and indicators.macd_hist > _safe_recent(_series_macd_hist(closes), 1, default=-1.0)
    ):
        confidence = min(
            0.88,
            0.54
            + max(min((indicators.rsi14 - 45) / 100, 0.08), 0.0)
            + max(min(indicators.roc20 / 100, 0.1), 0.0)
            + 0.05,
        )
        pullback_signal = SignalCandidate(
            signal=_build_signal(
                asset,
                strategy="pullback",
                horizon="swing",
                confidence=confidence,
                target_weight=_target_weight(asset, confidence),
                rationale=(
                    f"{asset.symbol} pulled back toward the 20D average inside an intact uptrend "
                    f"and is showing renewed upside confirmation."
                ),
                invalidation="Daily close below the 20D moving average and recent pullback low.",
                generated_at=generated_at,
                indicators=indicators,
                regime=regime,
                settings=resolved_settings,
                metadata={
                    "trendAligned": trend_base,
                    "momentumConfirmed": momentum_ok,
                    "volatilityPassed": volatility_ok,
                    "recentPullbackLow": round(recent_low_pullback, 4),
                },
            ),
            indicators=indicators,
            regime=regime,
            score=confidence,
            strategy="pullback",
            source_symbol=asset.symbol,
        )

    if trend_signal and pullback_signal:
        return trend_signal if trend_signal.score >= pullback_signal.score else pullback_signal
    return trend_signal or pullback_signal


def _indicator_snapshot(bars: list[PriceBar]) -> SignalIndicators:
    closes = [bar.close for bar in bars]
    highs = [bar.high for bar in bars]
    lows = [bar.low for bar in bars]
    sma20_series = sma(closes, 20)
    sma50_series = sma(closes, 50)
    sma200_series = sma(closes, 200)
    rsi14_series = rsi(closes, 14)
    roc20_series = roc(closes, 20)
    macd_series, macd_signal_series, macd_hist_series = macd(closes)
    atr14_series = atr(highs, lows, closes, 14)
    realized_vol20_series = realized_volatility(closes, 20)
    latest_close = closes[-1]
    atr14 = atr14_series[-1]
    return SignalIndicators(
        sma20=_round_or_none(sma20_series[-1]),
        sma50=_round_or_none(sma50_series[-1]),
        sma200=_round_or_none(sma200_series[-1]),
        rsi14=_round_or_none(rsi14_series[-1]),
        roc20=_round_or_none(roc20_series[-1]),
        macd=_round_or_none(macd_series[-1]),
        macd_signal=_round_or_none(macd_signal_series[-1]),
        macd_hist=_round_or_none(macd_hist_series[-1]),
        atr14_pct=_round_or_none((atr14 / latest_close) if atr14 and latest_close else None),
        realized_vol20=_round_or_none(realized_vol20_series[-1]),
    )


def _build_signal(
    asset: Asset,
    *,
    strategy: str,
    horizon: str,
    confidence: float,
    target_weight: float,
    rationale: str,
    invalidation: str,
    generated_at: datetime,
    indicators: SignalIndicators,
    regime: SignalRegime,
    settings: Settings,
    metadata: dict[str, Any],
) -> Signal:
    return Signal(
        symbol=asset.symbol,
        action=TradeAction.BUY,
        horizon=horizon,
        confidence=round(confidence, 4),
        target_weight=round(target_weight, 4),
        rationale=rationale,
        invalidation=invalidation,
        generated_at=generated_at,
        signal_type=strategy,
        source="signal_engine",
        expires_at=generated_at + timedelta(days=settings.signal_expiry_days),
        status="new",
        indicators=indicators,
        regime=regime,
        metadata={
            **metadata,
            "assetType": asset.asset_type.value,
            "leveragedInverse": asset.leveraged_inverse_flag,
        },
    )


def _volatility_limit(asset: Asset, settings: Settings) -> float:
    if asset.asset_type in {AssetType.LEVERAGED_ETF, AssetType.INVERSE_ETF}:
        return settings.signal_leveraged_volatility_max_annualized
    return settings.signal_volatility_max_annualized


def _atr_limit(asset: Asset) -> float:
    if asset.asset_type in {AssetType.LEVERAGED_ETF, AssetType.INVERSE_ETF}:
        return 0.16
    return 0.09


def _regime_allows_entry(asset: Asset, regime: SignalRegime) -> bool:
    if regime.state == "unknown":
        return True
    if asset.asset_type == AssetType.INVERSE_ETF:
        return regime.state == "risk_off"
    return regime.state == "risk_on"


def _target_weight(asset: Asset, confidence: float) -> float:
    if asset.asset_type == AssetType.BROAD_ETF:
        base = 0.12
    elif asset.asset_type == AssetType.SECTOR_ETF:
        base = 0.10
    elif asset.asset_type in {AssetType.LEVERAGED_ETF, AssetType.INVERSE_ETF}:
        base = 0.04
    else:
        base = 0.08
    return min(base * (0.75 + confidence * 0.5), base)


def _series_sma(closes: list[float], period: int) -> list[float | None]:
    return sma(closes, period)


def _series_macd_hist(closes: list[float]) -> list[float | None]:
    return macd(closes)[2]


def _safe_recent(
    values: list[float | None],
    periods_ago: int,
    *,
    default: float | None = None,
) -> float | None:
    index = len(values) - 1 - periods_ago
    if index < 0:
        return default
    value = values[index]
    return value if value is not None else default


def _serialize_signal_row(row: SignalRow) -> dict[str, Any]:
    snapshot = row.input_snapshot or {}
    return {
        "signalId": str(row.id),
        "symbol": row.symbol,
        "action": row.action,
        "strategy": snapshot.get("strategy", "unknown"),
        "horizon": row.horizon,
        "confidence": float(row.confidence),
        "targetWeight": float(row.target_weight),
        "source": row.source,
        "status": row.status,
        "rationale": row.rationale,
        "invalidation": row.invalidation,
        "generatedAt": row.generated_at.isoformat(),
        "expiresAt": row.expires_at.isoformat(),
        "indicators": snapshot.get("indicators", {}),
        "regime": snapshot.get("regime", {}),
        "metadata": snapshot.get("metadata", {}),
    }


def _decimal(value: float, pattern: str) -> Decimal:
    return Decimal(str(value)).quantize(Decimal(pattern), rounding=ROUND_HALF_UP)


def _round_or_none(value: float | None) -> float | None:
    return round(value, 4) if value is not None else None
