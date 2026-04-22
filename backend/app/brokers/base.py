from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any

from app.domain.models import Quote


class BrokerAdapter(ABC):
    @abstractmethod
    async def get_quote(self, symbol: str) -> Quote:
        raise NotImplementedError

    @abstractmethod
    async def get_account(self) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    async def get_positions(self) -> list[dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    async def place_order(self, planned_order: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    async def cancel_order(self, broker_order_id: str) -> None:
        raise NotImplementedError

    @abstractmethod
    async def get_fills(self, since: datetime) -> list[dict[str, Any]]:
        raise NotImplementedError
