from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from pydantic import BaseModel

from app.core.config import Settings, get_settings

US_EQUITY_TIMEZONE = ZoneInfo("America/New_York")
US_EQUITY_EXCHANGE = "XNYS"
REGULAR_OPEN = time(9, 30)
REGULAR_CLOSE = time(16, 0)
EARLY_CLOSE = time(13, 0)


class MarketClosedError(RuntimeError):
    pass


class MarketSessionStatus(BaseModel):
    exchange: str
    timezone: str
    nowUtc: datetime
    nowLocal: datetime
    marketDate: date
    state: str
    isOpen: bool
    regularSessionOnlyAllowed: bool
    reason: str
    sessionOpenUtc: datetime | None = None
    sessionCloseUtc: datetime | None = None
    nextOpenUtc: datetime
    nextCloseUtc: datetime


@dataclass(frozen=True)
class SessionHours:
    market_date: date
    open_at: datetime
    close_at: datetime
    is_early_close: bool = False


class USEquityMarketCalendar:
    def __init__(
        self,
        *,
        extra_closed_dates: list[date] | None = None,
        extra_early_close_dates: list[date] | None = None,
    ) -> None:
        self.extra_closed_dates = set(extra_closed_dates or [])
        self.extra_early_close_dates = set(extra_early_close_dates or [])

    @classmethod
    def from_settings(cls, settings: Settings | None = None) -> "USEquityMarketCalendar":
        resolved_settings = settings or get_settings()
        return cls(
            extra_closed_dates=_parse_dates(resolved_settings.market_extra_closed_date_list),
            extra_early_close_dates=_parse_dates(
                resolved_settings.market_extra_early_close_date_list
            ),
        )

    def status(self, now: datetime | None = None) -> MarketSessionStatus:
        now_utc = utc_now(now)
        now_local = now_utc.astimezone(US_EQUITY_TIMEZONE)
        market_date = now_local.date()
        session = self.session_hours(market_date)
        next_session = self.next_session(now_utc)
        next_open_session = next_session
        if session is not None and now_utc >= session.open_at:
            next_open_session = self.next_session(session.close_at + timedelta(microseconds=1))

        if session is None:
            state = "closed"
            is_open = False
            reason = self.closed_reason(market_date) or "Weekend"
            session_open = None
            session_close = None
        elif now_utc < session.open_at:
            state = "pre_market"
            is_open = False
            reason = "Regular session has not opened"
            session_open = session.open_at
            session_close = session.close_at
        elif now_utc >= session.close_at:
            state = "after_hours"
            is_open = False
            reason = "Regular session is closed"
            session_open = session.open_at
            session_close = session.close_at
        else:
            state = "open"
            is_open = True
            reason = "US regular session is open"
            session_open = session.open_at
            session_close = session.close_at

        return MarketSessionStatus(
            exchange=US_EQUITY_EXCHANGE,
            timezone=str(US_EQUITY_TIMEZONE),
            nowUtc=now_utc,
            nowLocal=now_local,
            marketDate=market_date,
            state=state,
            isOpen=is_open,
            regularSessionOnlyAllowed=is_open,
            reason=reason,
            sessionOpenUtc=session_open,
            sessionCloseUtc=session_close,
            nextOpenUtc=next_open_session.open_at,
            nextCloseUtc=next_session.close_at,
        )

    def assert_regular_session(self, now: datetime | None = None) -> None:
        status = self.status(now)
        if not status.isOpen:
            raise MarketClosedError(status.reason)

    def session_hours(self, market_date: date) -> SessionHours | None:
        if not self.is_trading_day(market_date):
            return None

        close_time = EARLY_CLOSE if self.is_early_close(market_date) else REGULAR_CLOSE
        return SessionHours(
            market_date=market_date,
            open_at=_local_datetime(market_date, REGULAR_OPEN).astimezone(UTC),
            close_at=_local_datetime(market_date, close_time).astimezone(UTC),
            is_early_close=close_time == EARLY_CLOSE,
        )

    def is_trading_day(self, market_date: date) -> bool:
        return market_date.weekday() < 5 and self.closed_reason(market_date) is None

    def is_early_close(self, market_date: date) -> bool:
        if market_date in self.extra_early_close_dates:
            return True
        if market_date == _thanksgiving(market_date.year) + timedelta(days=1):
            return self.is_trading_day(market_date)
        if market_date.month == 12 and market_date.day == 24:
            return self.is_trading_day(market_date)
        if market_date.month == 7 and market_date.day == 3:
            return self.is_trading_day(market_date)
        return False

    def closed_reason(self, market_date: date) -> str | None:
        if market_date in self.extra_closed_dates:
            return "Configured market closure"
        if market_date.weekday() >= 5:
            return "Weekend"
        return _standard_holidays(market_date.year).get(market_date)

    def next_session(self, now: datetime | None = None) -> SessionHours:
        now_utc = utc_now(now)
        market_date = now_utc.astimezone(US_EQUITY_TIMEZONE).date()

        for offset in range(0, 15):
            candidate = market_date + timedelta(days=offset)
            session = self.session_hours(candidate)
            if session is None:
                continue
            if now_utc < session.close_at:
                return session

        raise MarketClosedError("Unable to find the next US equity session within 15 days.")


def utc_now(value: datetime | None = None) -> datetime:
    if value is None:
        return datetime.now(UTC)
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _parse_dates(values: list[str]) -> list[date]:
    parsed_dates: list[date] = []
    for value in values:
        parsed_dates.append(date.fromisoformat(value))
    return parsed_dates


def _local_datetime(market_date: date, local_time: time) -> datetime:
    return datetime.combine(market_date, local_time, tzinfo=US_EQUITY_TIMEZONE)


def _standard_holidays(year: int) -> dict[date, str]:
    holidays = {
        _observed_new_year(year): "New Year's Day",
        _nth_weekday(year, 1, 0, 3): "Martin Luther King Jr. Day",
        _nth_weekday(year, 2, 0, 3): "Washington's Birthday",
        _good_friday(year): "Good Friday",
        _last_weekday(year, 5, 0): "Memorial Day",
        _observed_fixed_holiday(year, 6, 19): "Juneteenth National Independence Day",
        _observed_fixed_holiday(year, 7, 4): "Independence Day",
        _nth_weekday(year, 9, 0, 1): "Labor Day",
        _thanksgiving(year): "Thanksgiving Day",
        _observed_fixed_holiday(year, 12, 25): "Christmas Day",
    }
    return {holiday: name for holiday, name in holidays.items() if holiday.year == year}


def _observed_new_year(year: int) -> date:
    holiday = date(year, 1, 1)
    if holiday.weekday() == 6:
        return holiday + timedelta(days=1)
    return holiday


def _observed_fixed_holiday(year: int, month: int, day: int) -> date:
    holiday = date(year, month, day)
    if holiday.weekday() == 5:
        return holiday - timedelta(days=1)
    if holiday.weekday() == 6:
        return holiday + timedelta(days=1)
    return holiday


def _nth_weekday(year: int, month: int, weekday: int, n: int) -> date:
    current = date(year, month, 1)
    days_until_weekday = (weekday - current.weekday()) % 7
    return current + timedelta(days=days_until_weekday + (n - 1) * 7)


def _last_weekday(year: int, month: int, weekday: int) -> date:
    if month == 12:
        current = date(year + 1, 1, 1) - timedelta(days=1)
    else:
        current = date(year, month + 1, 1) - timedelta(days=1)
    days_since_weekday = (current.weekday() - weekday) % 7
    return current - timedelta(days=days_since_weekday)


def _thanksgiving(year: int) -> date:
    return _nth_weekday(year, 11, 3, 4)


def _good_friday(year: int) -> date:
    return _easter_sunday(year) - timedelta(days=2)


def _easter_sunday(year: int) -> date:
    a = year % 19
    b = year // 100
    c = year % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    le = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * le) // 451
    month = (h + le - 7 * m + 114) // 31
    day = ((h + le - 7 * m + 114) % 31) + 1
    return date(year, month, day)
