from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from app.brokers.base import BrokerAdapter
from app.domain.models import Quote


class MockBrokerAdapter(BrokerAdapter):
    async def get_quote(self, symbol: str) -> Quote:
        return Quote(
            symbol=symbol.upper(),
            bid=Decimal("99.95"),
            ask=Decimal("100.05"),
            last=Decimal("100.00"),
            quote_time=datetime.now(UTC),
        )

    async def get_account(self) -> dict[str, Any]:
        return {"mode": "mock", "accountType": "cash", "cashUsd": "0.00"}

    async def get_positions(self) -> list[dict[str, Any]]:
        return []

    async def place_order(self, planned_order: dict[str, Any]) -> dict[str, Any]:
        return {"status": "rejected", "reason": "Mock adapter does not submit live orders."}

    async def cancel_order(self, broker_order_id: str) -> None:
        return None

    async def get_fills(self, since: datetime) -> list[dict[str, Any]]:
        return []
