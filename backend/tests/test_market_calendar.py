from datetime import UTC, datetime

from app.services.market_calendar import USEquityMarketCalendar
from app.services.market_data import evaluate_quote_freshness


def test_market_status_open_during_regular_session() -> None:
    calendar = USEquityMarketCalendar()
    status = calendar.status(datetime(2026, 4, 22, 14, 0, tzinfo=UTC))

    assert status.state == "open"
    assert status.isOpen is True
    assert status.sessionOpenUtc == datetime(2026, 4, 22, 13, 30, tzinfo=UTC)
    assert status.sessionCloseUtc == datetime(2026, 4, 22, 20, 0, tzinfo=UTC)


def test_good_friday_is_closed() -> None:
    calendar = USEquityMarketCalendar()
    status = calendar.status(datetime(2026, 4, 3, 15, 0, tzinfo=UTC))

    assert status.state == "closed"
    assert status.isOpen is False
    assert status.reason == "Good Friday"
    assert status.nextOpenUtc == datetime(2026, 4, 6, 13, 30, tzinfo=UTC)


def test_day_after_thanksgiving_uses_early_close() -> None:
    calendar = USEquityMarketCalendar()
    status = calendar.status(datetime(2026, 11, 27, 17, 0, tzinfo=UTC))

    assert status.state == "open"
    assert status.sessionOpenUtc == datetime(2026, 11, 27, 14, 30, tzinfo=UTC)
    assert status.sessionCloseUtc == datetime(2026, 11, 27, 18, 0, tzinfo=UTC)


def test_extra_closed_date_override_blocks_session() -> None:
    calendar = USEquityMarketCalendar(
        extra_closed_dates=[datetime(2026, 5, 4, tzinfo=UTC).date()]
    )
    status = calendar.status(datetime(2026, 5, 4, 15, 0, tzinfo=UTC))

    assert status.state == "closed"
    assert status.reason == "Configured market closure"


def test_quote_freshness_marks_stale_data() -> None:
    result = evaluate_quote_freshness(
        datetime(2026, 4, 22, 14, 0, tzinfo=UTC),
        now=datetime(2026, 4, 22, 14, 16, tzinfo=UTC),
        stale_after_seconds=900,
    )

    assert result.is_fresh is False
    assert result.age_seconds == 960
    assert result.reason == "Stale market data"
