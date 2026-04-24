from datetime import UTC, datetime, timedelta
from math import sin
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import ProcessRole, Settings
from app.domain.models import Asset, AssetType
from app.domain.models import SignalRegime as DomainSignalRegime
from app.services.indicators import macd, roc, rsi, sma
from app.services.scheduler import start_scheduler
from app.services.signal_engine import PriceBar, SignalEngine, evaluate_signal_candidate


def _bars_from_closes(closes: list[float]) -> list[PriceBar]:
    start = datetime(2025, 1, 1, tzinfo=UTC)
    bars: list[PriceBar] = []
    for index, close in enumerate(closes):
        timestamp = start + timedelta(days=index)
        bars.append(
            PriceBar(
                open_time=timestamp,
                close_time=timestamp + timedelta(hours=6),
                open=close * 0.995,
                high=close * 1.01,
                low=close * 0.99,
                close=close,
                volume=1_000_000 + (index * 1_000),
            )
        )
    return bars


def test_indicator_functions_return_latest_values() -> None:
    closes = [100 + (index * 0.5) for index in range(80)]

    assert sma(closes, 20)[-1] is not None
    assert rsi(closes, 14)[-1] is not None
    assert roc(closes, 20)[-1] is not None
    macd_line, signal_line, hist = macd(closes)
    assert macd_line[-1] is not None
    assert signal_line[-1] is not None
    assert hist[-1] is not None


def test_trend_following_signal_is_generated_for_risk_on_asset() -> None:
    closes = [100 + (index * 0.08) + sin(index / 2.5) * 2.5 for index in range(220)]
    asset = Asset(
        symbol="QQQ",
        name="Invesco QQQ Trust",
        asset_type=AssetType.BROAD_ETF,
        exchange="NASDAQ",
    )
    regime = DomainSignalRegime(
        benchmark_symbol="SPY",
        state="risk_on",
        reason="Benchmark trend is constructive.",
    )

    candidate = evaluate_signal_candidate(
        asset,
        _bars_from_closes(closes),
        regime=regime,
        generated_at=datetime(2026, 4, 24, tzinfo=UTC),
        settings=Settings(),
    )

    assert candidate is not None
    assert candidate.signal.action == "buy"
    assert candidate.signal.signal_type in {"trend_following", "pullback"}
    assert candidate.signal.confidence > 0.5


def test_risk_off_inverse_asset_can_generate_buy_signal() -> None:
    closes = [50 + (index * 0.08) + sin(index / 2.5) * 1.5 for index in range(220)]
    asset = Asset(
        symbol="SQQQ",
        name="ProShares UltraPro Short QQQ",
        asset_type=AssetType.INVERSE_ETF,
        exchange="NASDAQ",
        leveraged_inverse_flag=True,
    )
    regime = DomainSignalRegime(
        benchmark_symbol="SPY",
        state="risk_off",
        reason="Benchmark trend is defensive.",
    )

    candidate = evaluate_signal_candidate(
        asset,
        _bars_from_closes(closes),
        regime=regime,
        generated_at=datetime(2026, 4, 24, tzinfo=UTC),
        settings=Settings(),
    )

    assert candidate is not None
    assert candidate.signal.symbol == "SQQQ"
    assert candidate.signal.action == "buy"


def test_no_signal_is_generated_for_flat_series() -> None:
    closes = [100 + ((index % 4) * 0.03) for index in range(220)]
    asset = Asset(
        symbol="SPY",
        name="SPDR S&P 500 ETF Trust",
        asset_type=AssetType.BROAD_ETF,
        exchange="NYSEARCA",
    )
    regime = DomainSignalRegime(
        benchmark_symbol="SPY",
        state="risk_on",
        reason="Benchmark trend is constructive.",
    )

    candidate = evaluate_signal_candidate(
        asset,
        _bars_from_closes(closes),
        regime=regime,
        generated_at=datetime(2026, 4, 24, tzinfo=UTC),
        settings=Settings(),
    )

    assert candidate is None


def test_list_signals_commits_expired_status_updates() -> None:
    now = datetime(2026, 4, 25, tzinfo=UTC)
    session = Mock()
    session.execute.return_value = SimpleNamespace(rowcount=2)
    session.scalars.return_value.all.return_value = [
        SimpleNamespace(
            id="signal-1",
            symbol="QQQ",
            action="buy",
            horizon="swing",
            confidence=0.71,
            target_weight=0.12,
            source="signal_engine",
            status="expired",
            rationale="Test rationale",
            invalidation="Test invalidation",
            generated_at=now - timedelta(days=2),
            expires_at=now - timedelta(days=1),
            input_snapshot={"strategy": "pullback", "indicators": {}, "regime": {}, "metadata": {}},
        )
    ]

    items = SignalEngine(db=session, settings=Settings()).list_signals(limit=10)

    assert len(items) == 1
    session.commit.assert_called_once()


def test_list_signals_surfaces_database_errors() -> None:
    session = Mock()
    session.execute.return_value = SimpleNamespace(rowcount=0)
    session.scalars.side_effect = SQLAlchemyError("db down")

    with pytest.raises(SQLAlchemyError):
        SignalEngine(db=session, settings=Settings()).list_signals(limit=10)


def test_scheduler_does_not_start_inside_api_role(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_scheduler_factory = Mock()
    monkeypatch.setattr(
        "app.services.scheduler.get_settings",
        lambda: Settings(signal_scheduler_enabled=True, process_role=ProcessRole.API),
    )
    monkeypatch.setattr("app.services.scheduler.BackgroundScheduler", fake_scheduler_factory)
    app = SimpleNamespace(state=SimpleNamespace())

    start_scheduler(app)

    assert app.state.scheduler is None
    fake_scheduler_factory.assert_not_called()
