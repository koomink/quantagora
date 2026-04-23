from decimal import Decimal

from app.core.config import Settings
from app.domain.models import AssetType
from app.services.universe import (
    MarketMetrics,
    UniverseCandidate,
    candidate_from_symbol,
    evaluate_candidate,
    kis_exchange_code_for_symbol,
)


def test_candidate_passes_liquidity_price_and_spread_filters() -> None:
    decision = evaluate_candidate(
        candidate_from_symbol("QQQ", source="agent", rationale="High-liquidity growth ETF."),
        MarketMetrics(
            latest_price=Decimal("420"),
            bid=Decimal("419.98"),
            ask=Decimal("420.02"),
            spread_bps=Decimal("0.9524"),
            avg_dollar_volume=Decimal("5000000000"),
            history_days=60,
        ),
        settings=Settings(),
    )

    assert decision.accepted is True
    assert decision.reasons == []
    assert decision.score > 0


def test_leveraged_inverse_candidate_must_be_whitelisted() -> None:
    decision = evaluate_candidate(
        UniverseCandidate(
            symbol="QLD",
            name="ProShares Ultra QQQ",
            asset_type=AssetType.LEVERAGED_ETF.value,
            exchange="NYSEARCA",
            rationale="Non-whitelisted leverage test.",
            source="agent",
            leveraged_inverse_flag=True,
        ),
        MarketMetrics(
            latest_price=Decimal("100"),
            bid=Decimal("99.99"),
            ask=Decimal("100.01"),
            spread_bps=Decimal("2"),
            avg_dollar_volume=Decimal("100000000"),
            history_days=60,
        ),
        settings=Settings(universe_leveraged_inverse_whitelist="TQQQ,SQQQ"),
    )

    assert decision.accepted is False
    assert "leveraged_inverse_not_whitelisted" in decision.reasons


def test_candidate_rejects_low_liquidity_wide_spread_and_otc() -> None:
    decision = evaluate_candidate(
        UniverseCandidate(
            symbol="ABC.PK",
            name="OTC Test",
            asset_type=AssetType.COMMON_STOCK.value,
            exchange="OTC",
            rationale="OTC rejection test.",
            source="agent",
        ),
        MarketMetrics(
            latest_price=Decimal("3"),
            bid=Decimal("2.90"),
            ask=Decimal("3.10"),
            spread_bps=Decimal("666.67"),
            avg_dollar_volume=Decimal("1000000"),
            history_days=20,
        ),
        settings=Settings(),
    )

    assert decision.accepted is False
    assert "otc_excluded" in decision.reasons
    assert "below_min_price" in decision.reasons
    assert "below_min_liquidity" in decision.reasons
    assert "spread_too_wide" in decision.reasons


def test_kis_exchange_code_uses_metadata_exchange_mapping() -> None:
    assert kis_exchange_code_for_symbol("SPY") == "AMS"
    assert kis_exchange_code_for_symbol("QQQ") == "NAS"
    assert kis_exchange_code_for_symbol("AAPL") == "NAS"
