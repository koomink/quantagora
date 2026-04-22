from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from app.brokers.base import BrokerAdapter
from app.brokers.schemas import (
    BrokerAccount,
    BrokerBuyingPower,
    BrokerCandle,
    BrokerFill,
    BrokerOrderRequest,
    BrokerOrderResult,
    BrokerOrderStatus,
    BrokerPosition,
)
from app.domain.models import Quote


class MockBrokerAdapter(BrokerAdapter):
    async def get_quote(self, symbol: str, exchange: str = "NAS") -> Quote:
        return Quote(
            symbol=symbol.upper(),
            bid=Decimal("99.95"),
            ask=Decimal("100.05"),
            last=Decimal("100.00"),
            quote_time=datetime.now(UTC),
        )

    async def get_candles(
        self,
        symbol: str,
        start: Any = None,
        end: Any = None,
        timeframe: str = "D",
        exchange: str = "NAS",
    ) -> list[BrokerCandle]:
        return []

    async def get_account(self) -> BrokerAccount:
        return BrokerAccount(account_ref="mock", cash={"USD": Decimal("0.00")})

    async def get_positions(self) -> list[BrokerPosition]:
        return []

    async def get_buying_power(
        self,
        symbol: str,
        price: Any,
        exchange: str = "NASD",
    ) -> BrokerBuyingPower:
        return BrokerBuyingPower(
            symbol=symbol.upper(),
            exchange=exchange,
            price=Decimal(str(price)),
            cash_available=Decimal("0.00"),
            max_quantity=Decimal("0"),
        )

    async def place_order(
        self,
        planned_order: BrokerOrderRequest | dict[str, Any],
    ) -> BrokerOrderResult:
        order = (
            planned_order
            if isinstance(planned_order, BrokerOrderRequest)
            else BrokerOrderRequest.model_validate(planned_order)
        )
        return BrokerOrderResult(
            status=BrokerOrderStatus.REJECTED,
            symbol=order.symbol.upper(),
            side=order.side,
            quantity=order.quantity,
            price=order.limit_price,
            raw_response={"reason": "Mock adapter does not submit live orders."},
        )

    async def cancel_order(
        self,
        broker_order_id: str,
        *,
        symbol: str,
        quantity: Any,
        exchange: str = "NASD",
        limit_price: Any = "0",
    ) -> BrokerOrderResult:
        return BrokerOrderResult(
            broker_order_id=broker_order_id,
            status=BrokerOrderStatus.CANCELED,
            symbol=symbol.upper(),
            quantity=Decimal(str(quantity)),
            price=Decimal(str(limit_price)),
        )

    async def get_order(
        self,
        broker_order_id: str,
        *,
        symbol: str = "",
        start: Any = None,
        end: Any = None,
        exchange: str = "%",
    ) -> BrokerOrderResult:
        return BrokerOrderResult(
            broker_order_id=broker_order_id,
            status=BrokerOrderStatus.UNKNOWN,
            symbol=symbol.upper() if symbol else None,
        )

    async def get_fills(self, since: datetime) -> list[BrokerFill]:
        return []
