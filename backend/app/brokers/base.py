from abc import ABC, abstractmethod
from datetime import date, datetime
from typing import Any

from app.domain.models import Quote

from .schemas import (
    BrokerAccount,
    BrokerBuyingPower,
    BrokerCandle,
    BrokerFill,
    BrokerOrderRequest,
    BrokerOrderResult,
    BrokerPosition,
)


class BrokerAdapter(ABC):
    @abstractmethod
    async def get_quote(self, symbol: str, exchange: str = "NAS") -> Quote:
        raise NotImplementedError

    @abstractmethod
    async def get_candles(
        self,
        symbol: str,
        start: date | None = None,
        end: date | None = None,
        timeframe: str = "D",
        exchange: str = "NAS",
    ) -> list[BrokerCandle]:
        raise NotImplementedError

    @abstractmethod
    async def get_account(self) -> BrokerAccount:
        raise NotImplementedError

    @abstractmethod
    async def get_positions(self) -> list[BrokerPosition]:
        raise NotImplementedError

    @abstractmethod
    async def get_buying_power(
        self,
        symbol: str,
        price: Any,
        exchange: str = "NASD",
    ) -> BrokerBuyingPower:
        raise NotImplementedError

    @abstractmethod
    async def place_order(
        self,
        planned_order: BrokerOrderRequest | dict[str, Any],
    ) -> BrokerOrderResult:
        raise NotImplementedError

    @abstractmethod
    async def cancel_order(
        self,
        broker_order_id: str,
        *,
        symbol: str,
        quantity: Any,
        exchange: str = "NASD",
        limit_price: Any = "0",
    ) -> BrokerOrderResult:
        raise NotImplementedError

    @abstractmethod
    async def get_order(
        self,
        broker_order_id: str,
        *,
        symbol: str = "",
        start: date | None = None,
        end: date | None = None,
        exchange: str = "%",
    ) -> BrokerOrderResult:
        raise NotImplementedError

    @abstractmethod
    async def get_fills(self, since: datetime) -> list[BrokerFill]:
        raise NotImplementedError
