import asyncio
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any

import httpx

from app.brokers.base import BrokerAdapter
from app.brokers.schemas import (
    BrokerAccount,
    BrokerBuyingPower,
    BrokerCandle,
    BrokerFill,
    BrokerOrderRequest,
    BrokerOrderResult,
    BrokerOrderSide,
    BrokerOrderStatus,
    BrokerOrderType,
    BrokerPosition,
)
from app.core.config import KisMode, Settings, get_settings
from app.domain.models import Quote


class KISBrokerError(RuntimeError):
    pass


class KISConfigurationError(KISBrokerError):
    pass


class KISAPIError(KISBrokerError):
    def __init__(
        self,
        message: str,
        *,
        status_code: int,
        error_code: str | None = None,
        body: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.error_code = error_code
        self.body = body or {}


@dataclass(frozen=True)
class KISAPIResponse:
    status_code: int
    headers: dict[str, str]
    body: dict[str, Any]
    tr_id: str | None = None

    def raw(self) -> dict[str, Any]:
        return {
            "status_code": self.status_code,
            "headers": self.headers,
            "body": self.body,
            "tr_id": self.tr_id,
        }


class AsyncRateLimiter:
    def __init__(self, calls_per_second: float) -> None:
        self._min_interval = 1.0 / calls_per_second if calls_per_second > 0 else 0.0
        self._lock = asyncio.Lock()
        self._last_call = 0.0

    async def wait(self) -> None:
        if self._min_interval <= 0:
            return
        async with self._lock:
            loop = asyncio.get_running_loop()
            now = loop.time()
            sleep_for = self._last_call + self._min_interval - now
            if sleep_for > 0:
                await asyncio.sleep(sleep_for)
            self._last_call = loop.time()


class KISBrokerAdapter(BrokerAdapter):
    ORDER_PATH = "/uapi/overseas-stock/v1/trading/order"
    CANCEL_PATH = "/uapi/overseas-stock/v1/trading/order-rvsecncl"
    ORDER_HISTORY_PATH = "/uapi/overseas-stock/v1/trading/inquire-ccnl"
    BALANCE_PATH = "/uapi/overseas-stock/v1/trading/inquire-present-balance"
    POSITIONS_PATH = "/uapi/overseas-stock/v1/trading/inquire-balance"
    BUYING_POWER_PATH = "/uapi/overseas-stock/v1/trading/inquire-psamount"
    QUOTE_PATH = "/uapi/overseas-price/v1/quotations/price"
    DAILY_PRICE_PATH = "/uapi/overseas-price/v1/quotations/dailyprice"

    def __init__(
        self,
        settings: Settings | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self._client = client
        self._owns_client = client is None
        self._access_token: str | None = None
        self._token_expires_at: datetime | None = None
        self._rate_limiter = AsyncRateLimiter(self.settings.kis_rate_limit_per_second)

    async def close(self) -> None:
        if self._client and self._owns_client:
            await self._client.aclose()
            self._client = None

    async def get_quote(self, symbol: str, exchange: str = "NAS") -> Quote:
        response = await self._request(
            "GET",
            self.QUOTE_PATH,
            "HHDFS00000300",
            params={
                "AUTH": "",
                "EXCD": self._price_exchange_code(exchange),
                "SYMB": symbol.upper(),
            },
        )
        output = self._first_output(response.body, "output")
        last = self._decimal_required(self._first(output, "last", "ovrs_now_pric", "clos", "base"))
        return Quote(
            symbol=symbol.upper(),
            bid=self._decimal_optional(self._first(output, "pbid", "bid", "ovrs_bidp")),
            ask=self._decimal_optional(self._first(output, "pask", "ask", "ovrs_askp")),
            last=last,
            currency="USD",
            quote_time=datetime.now(UTC),
        )

    async def get_candles(
        self,
        symbol: str,
        start: date | None = None,
        end: date | None = None,
        timeframe: str = "D",
        exchange: str = "NAS",
    ) -> list[BrokerCandle]:
        end_date = end or datetime.now(UTC).date()
        response = await self._request(
            "GET",
            self.DAILY_PRICE_PATH,
            "HHDFS76240000",
            params={
                "AUTH": "",
                "EXCD": self._price_exchange_code(exchange),
                "SYMB": symbol.upper(),
                "GUBN": self._timeframe_code(timeframe),
                "BYMD": end_date.strftime("%Y%m%d"),
                "MODP": "1",
            },
        )
        rows = self._output_list(response.body, "output2")
        candles = [self._parse_candle(symbol.upper(), row, response.raw()) for row in rows]
        if start:
            candles = [candle for candle in candles if candle.candle_date >= start]
        return candles

    async def get_account(self) -> BrokerAccount:
        self._require_account()
        response = await self._request(
            "GET",
            self.BALANCE_PATH,
            self._paper_tr_id("CTRP6504R"),
            params={
                "CANO": self.settings.kis_cano,
                "ACNT_PRDT_CD": self.settings.kis_product_code,
                "WCRC_FRCR_DVSN_CD": "02",
                "NATN_CD": "840",
                "TR_MKET_CD": "00",
                "INQR_DVSN_CD": "00",
            },
        )
        raw = response.raw()
        position_rows = self._output_list(response.body, "output1")
        cash_rows = self._output_list(response.body, "output2") + self._output_list(
            response.body, "output3"
        )
        return BrokerAccount(
            account_ref=self.settings.kis_cano,
            cash=self._parse_cash(cash_rows),
            total_equity=self._decimal_optional(
                self._first_from_rows(
                    cash_rows,
                    "tot_evlu_pfls_amt",
                    "evlu_amt_smtl_amt",
                    "frcr_evlu_tota",
                    "tot_asst_amt",
                )
            ),
            positions=self._parse_positions(position_rows, raw),
            raw_response=raw,
        )

    async def get_positions(self) -> list[BrokerPosition]:
        self._require_account()
        response = await self._request(
            "GET",
            self.POSITIONS_PATH,
            self._paper_tr_id("TTTS3012R"),
            params={
                "CANO": self.settings.kis_cano,
                "ACNT_PRDT_CD": self.settings.kis_product_code,
                "OVRS_EXCG_CD": "NASD",
                "TR_CRCY_CD": "USD",
                "CTX_AREA_FK200": "",
                "CTX_AREA_NK200": "",
            },
        )
        return self._parse_positions(self._output_list(response.body, "output1"), response.raw())

    async def get_buying_power(
        self,
        symbol: str,
        price: Any,
        exchange: str = "NASD",
    ) -> BrokerBuyingPower:
        self._require_account()
        order_price = self._decimal_required(price)
        response = await self._request(
            "GET",
            self.BUYING_POWER_PATH,
            self._paper_tr_id("TTTS3007R"),
            params={
                "CANO": self.settings.kis_cano,
                "ACNT_PRDT_CD": self.settings.kis_product_code,
                "OVRS_EXCG_CD": self._order_exchange_code(exchange),
                "OVRS_ORD_UNPR": self._decimal_str(order_price),
                "ITEM_CD": symbol.upper(),
            },
        )
        output = self._first_output(response.body, "output")
        return BrokerBuyingPower(
            symbol=symbol.upper(),
            exchange=self._order_exchange_code(exchange),
            price=order_price,
            cash_available=self._decimal_optional(
                self._first(output, "ord_psbl_frcr_amt", "frcr_ord_psbl_amt1", "ord_psbl_cash")
            ),
            max_quantity=self._decimal_optional(
                self._first(output, "max_ord_psbl_qty", "ord_psbl_qty", "nrcvb_buy_qty")
            ),
            raw_response=response.raw(),
        )

    async def place_order(
        self,
        planned_order: BrokerOrderRequest | dict[str, Any],
    ) -> BrokerOrderResult:
        self._require_account()
        order = (
            planned_order
            if isinstance(planned_order, BrokerOrderRequest)
            else BrokerOrderRequest.model_validate(planned_order)
        )
        exchange = self._order_exchange_code(order.exchange)
        tr_id = self._order_tr_id(order.side, exchange)
        body = {
            "CANO": self.settings.kis_cano,
            "ACNT_PRDT_CD": self.settings.kis_product_code,
            "OVRS_EXCG_CD": exchange,
            "PDNO": order.symbol.upper(),
            "ORD_QTY": self._decimal_str(order.quantity),
            "OVRS_ORD_UNPR": self._decimal_str(order.limit_price),
            "CTAC_TLNO": "",
            "MGCO_APTM_ODNO": order.client_order_id or "",
            "SLL_TYPE": "00" if order.side == BrokerOrderSide.SELL else "",
            "ORD_SVR_DVSN_CD": "0",
            "ORD_DVSN": self._order_type_code(order.side, order.order_type),
        }
        response = await self._request(
            "POST",
            self.ORDER_PATH,
            tr_id,
            json_body=body,
            hash_payload=True,
        )
        output = self._first_output(response.body, "output")
        return BrokerOrderResult(
            broker_order_id=self._string_optional(self._first(output, "ODNO", "odno")),
            status=BrokerOrderStatus.SUBMITTED,
            symbol=order.symbol.upper(),
            side=order.side,
            quantity=order.quantity,
            price=order.limit_price,
            submitted_at=datetime.now(UTC),
            raw_response=response.raw(),
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
        self._require_account()
        order_price = self._decimal_required(limit_price)
        response = await self._request(
            "POST",
            self.CANCEL_PATH,
            self._paper_tr_id("TTTT1004U"),
            json_body={
                "CANO": self.settings.kis_cano,
                "ACNT_PRDT_CD": self.settings.kis_product_code,
                "OVRS_EXCG_CD": self._order_exchange_code(exchange),
                "PDNO": symbol.upper(),
                "ORGN_ODNO": broker_order_id,
                "RVSE_CNCL_DVSN_CD": "02",
                "ORD_QTY": self._decimal_str(self._decimal_required(quantity)),
                "OVRS_ORD_UNPR": self._decimal_str(order_price),
                "MGCO_APTM_ODNO": "",
                "ORD_SVR_DVSN_CD": "0",
            },
            hash_payload=True,
        )
        return BrokerOrderResult(
            broker_order_id=broker_order_id,
            status=BrokerOrderStatus.CANCELED,
            symbol=symbol.upper(),
            quantity=self._decimal_required(quantity),
            price=order_price,
            raw_response=response.raw(),
        )

    async def get_order(
        self,
        broker_order_id: str,
        *,
        symbol: str = "",
        start: date | None = None,
        end: date | None = None,
        exchange: str = "%",
    ) -> BrokerOrderResult:
        rows, raw = await self._get_order_history(
            start=start,
            end=end,
            symbol=symbol,
            exchange=exchange,
            broker_order_id=broker_order_id,
            fill_filter="00",
        )
        if not rows:
            return BrokerOrderResult(
                broker_order_id=broker_order_id,
                status=BrokerOrderStatus.UNKNOWN,
                symbol=symbol.upper() if symbol else None,
                raw_response=raw,
            )
        return self._parse_order_result(rows[0], raw)

    async def get_fills(self, since: datetime) -> list[BrokerFill]:
        rows, raw = await self._get_order_history(
            start=since.date(),
            end=datetime.now(UTC).date(),
            fill_filter="01",
        )
        return [self._parse_fill(row, raw) for row in rows]

    async def _get_order_history(
        self,
        *,
        start: date | None,
        end: date | None,
        symbol: str = "",
        exchange: str = "%",
        broker_order_id: str = "",
        fill_filter: str = "00",
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        self._require_account()
        end_date = end or datetime.now(UTC).date()
        start_date = start or end_date
        response = await self._request(
            "GET",
            self.ORDER_HISTORY_PATH,
            self._paper_tr_id("TTTS3035R"),
            params={
                "CANO": self.settings.kis_cano,
                "ACNT_PRDT_CD": self.settings.kis_product_code,
                "PDNO": symbol.upper() if symbol else "%",
                "ORD_STRT_DT": start_date.strftime("%Y%m%d"),
                "ORD_END_DT": end_date.strftime("%Y%m%d"),
                "SLL_BUY_DVSN": "00",
                "CCLD_NCCS_DVSN": fill_filter,
                "SORT_SQN": "DS",
                "ORD_DT": "",
                "ORD_GNO_BRNO": "",
                "ODNO": broker_order_id,
                "OVRS_EXCG_CD": exchange,
                "CTX_AREA_NK200": "",
                "CTX_AREA_FK200": "",
            },
        )
        return self._output_list(response.body, "output"), response.raw()

    async def _request(
        self,
        method: str,
        path: str,
        tr_id: str,
        *,
        params: Mapping[str, Any] | None = None,
        json_body: Mapping[str, Any] | None = None,
        tr_cont: str = "",
        hash_payload: bool = False,
    ) -> KISAPIResponse:
        self._require_api_credentials()
        token = await self._get_access_token()
        headers = {
            "content-type": "application/json",
            "authorization": f"Bearer {token}",
            "appkey": self.settings.kis_app_key,
            "appsecret": self.settings.kis_app_secret,
            "tr_id": tr_id,
            "custtype": "P",
            "tr_cont": tr_cont,
        }
        if hash_payload and json_body is not None:
            headers["hashkey"] = await self._hashkey(dict(json_body))

        await self._rate_limiter.wait()
        response = await self._client_instance().request(
            method,
            f"{self.settings.kis_effective_base_url}{path}",
            headers=headers,
            params=params,
            json=json_body,
        )
        body = self._json_body(response)
        self._raise_for_error(response.status_code, body)
        return KISAPIResponse(
            status_code=response.status_code,
            headers={key.lower(): value for key, value in response.headers.items()},
            body=body,
            tr_id=tr_id,
        )

    async def _get_access_token(self) -> str:
        now = datetime.now(UTC)
        if self._access_token and self._token_expires_at and now < self._token_expires_at:
            return self._access_token

        self._require_api_credentials()
        response = await self._client_instance().post(
            f"{self.settings.kis_effective_base_url}/oauth2/tokenP",
            headers={"content-type": "application/json"},
            json={
                "grant_type": "client_credentials",
                "appkey": self.settings.kis_app_key,
                "appsecret": self.settings.kis_app_secret,
            },
        )
        body = self._json_body(response)
        self._raise_for_error(response.status_code, body)
        token = body.get("access_token")
        if not token:
            raise KISAPIError(
                "KIS token response did not include access_token.",
                status_code=200,
                body=body,
            )
        self._access_token = str(token)
        expires_in = self._decimal_optional(body.get("expires_in"))
        token_seconds = int(expires_in) if expires_in else 60 * 60 * 23
        self._token_expires_at = now + timedelta(seconds=max(token_seconds - 300, 60))
        return self._access_token

    async def _hashkey(self, payload: dict[str, Any]) -> str:
        await self._rate_limiter.wait()
        response = await self._client_instance().post(
            f"{self.settings.kis_effective_base_url}/uapi/hashkey",
            headers={
                "content-type": "application/json",
                "appkey": self.settings.kis_app_key,
                "appsecret": self.settings.kis_app_secret,
            },
            json=payload,
        )
        body = self._json_body(response)
        self._raise_for_error(response.status_code, body)
        hash_value = body.get("HASH")
        if not hash_value:
            raise KISAPIError(
                "KIS hashkey response did not include HASH.",
                status_code=200,
                body=body,
            )
        return str(hash_value)

    def _client_instance(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self.settings.kis_timeout_seconds)
        return self._client

    def _require_api_credentials(self) -> None:
        if not self.settings.kis_app_key or not self.settings.kis_app_secret:
            raise KISConfigurationError("KIS_APP_KEY and KIS_APP_SECRET are required.")

    def _require_account(self) -> None:
        if not self.settings.kis_cano or not self.settings.kis_product_code:
            raise KISConfigurationError("KIS_ACCOUNT_NO and KIS_ACCOUNT_PRODUCT_CODE are required.")

    def _paper_tr_id(self, tr_id: str) -> str:
        if self.settings.kis_mode == KisMode.PAPER and tr_id[:1] in {"T", "J", "C"}:
            return "V" + tr_id[1:]
        return tr_id

    def _order_tr_id(self, side: BrokerOrderSide, exchange: str) -> str:
        if exchange not in {"NASD", "NYSE", "AMEX"}:
            raise KISConfigurationError(f"Unsupported US order exchange: {exchange}")
        tr_id = "TTTT1002U" if side == BrokerOrderSide.BUY else "TTTT1006U"
        return self._paper_tr_id(tr_id)

    def _order_type_code(self, side: BrokerOrderSide, order_type: BrokerOrderType) -> str:
        mapping = {
            BrokerOrderType.LIMIT: "00",
            BrokerOrderType.MARKETABLE_LIMIT: "00",
            BrokerOrderType.LOO: "32",
            BrokerOrderType.LOC: "34",
        }
        if side == BrokerOrderSide.SELL:
            mapping |= {BrokerOrderType.MOO: "31", BrokerOrderType.MOC: "33"}
        if order_type not in mapping:
            raise KISConfigurationError(
                f"Unsupported KIS order type for {side.value}: {order_type.value}"
            )
        return mapping[order_type]

    def _order_exchange_code(self, exchange: str) -> str:
        exchange = exchange.upper()
        return {
            "NAS": "NASD",
            "NASDAQ": "NASD",
            "NASD": "NASD",
            "NYS": "NYSE",
            "NYSE": "NYSE",
            "AMS": "AMEX",
            "AMEX": "AMEX",
        }.get(exchange, exchange)

    def _price_exchange_code(self, exchange: str) -> str:
        exchange = exchange.upper()
        return {
            "NASDAQ": "NAS",
            "NASD": "NAS",
            "NAS": "NAS",
            "NYSE": "NYS",
            "NYS": "NYS",
            "AMEX": "AMS",
            "AMS": "AMS",
        }.get(exchange, exchange)

    def _timeframe_code(self, timeframe: str) -> str:
        return {"D": "0", "DAY": "0", "W": "1", "WEEK": "1", "M": "2", "MONTH": "2"}.get(
            timeframe.upper(),
            "0",
        )

    def _parse_candle(
        self,
        symbol: str,
        row: dict[str, Any],
        raw: dict[str, Any],
    ) -> BrokerCandle:
        raw_date = self._string_required(self._first(row, "xymd", "stck_bsop_date", "date"))
        return BrokerCandle(
            symbol=symbol,
            candle_date=datetime.strptime(raw_date, "%Y%m%d").date(),
            open=self._decimal_required(self._first(row, "open", "ovrs_nmix_oprc")),
            high=self._decimal_required(self._first(row, "high", "ovrs_nmix_hgpr")),
            low=self._decimal_required(self._first(row, "low", "ovrs_nmix_lwpr")),
            close=self._decimal_required(self._first(row, "clos", "close", "ovrs_nmix_prpr")),
            volume=self._decimal_optional(self._first(row, "tvol", "volume", "acml_vol")),
            raw_response=raw,
        )

    def _parse_positions(
        self,
        rows: list[dict[str, Any]],
        raw: dict[str, Any],
    ) -> list[BrokerPosition]:
        positions: list[BrokerPosition] = []
        for row in rows:
            symbol = self._string_optional(
                self._first(row, "pdno", "ovrs_pdno", "symb", "ovrs_item_cd")
            )
            quantity = self._decimal_optional(
                self._first(row, "ovrs_cblc_qty", "cblc_qty13", "qty", "hldg_qty")
            )
            if not symbol or quantity is None:
                continue
            positions.append(self._parse_position(row, raw, symbol, quantity))
        return positions

    def _parse_position(
        self,
        row: dict[str, Any],
        raw: dict[str, Any],
        symbol: str,
        quantity: Decimal,
    ) -> BrokerPosition:
        return BrokerPosition(
            symbol=symbol.upper(),
            quantity=quantity,
            average_price=self._decimal_optional(
                self._first(row, "pchs_avg_pric", "avg_unpr3", "avg_price")
            ),
            market_value=self._decimal_optional(
                self._first(row, "frcr_evlu_amt2", "ovrs_stck_evlu_amt", "market_value")
            ),
            unrealized_pnl=self._decimal_optional(
                self._first(row, "evlu_pfls_amt2", "evlu_pfls_amt", "unrealized_pnl")
            ),
            currency=self._string_optional(self._first(row, "tr_crcy_cd", "crcy_cd")) or "USD",
            raw_response=raw,
        )

    def _parse_cash(self, rows: list[dict[str, Any]]) -> dict[str, Decimal]:
        cash: dict[str, Decimal] = {}
        for row in rows:
            currency = (
                self._string_optional(self._first(row, "crcy_cd", "tr_crcy_cd", "curr_cd"))
                or "USD"
            )
            amount = self._decimal_optional(
                self._first(
                    row,
                    "frcr_dncl_amt_2",
                    "frcr_ord_psbl_amt1",
                    "ord_psbl_cash",
                    "cash",
                )
            )
            if amount is not None:
                cash[currency] = amount
        return cash

    def _parse_order_result(self, row: dict[str, Any], raw: dict[str, Any]) -> BrokerOrderResult:
        return BrokerOrderResult(
            broker_order_id=self._string_optional(self._first(row, "odno", "ODNO")),
            status=self._normalize_order_status(row),
            symbol=self._string_optional(self._first(row, "pdno", "ovrs_pdno", "symb")),
            side=self._normalize_side(self._first(row, "sll_buy_dvsn_cd", "sll_buy_dvsn_name")),
            quantity=self._decimal_optional(self._first(row, "ft_ord_qty", "ord_qty", "qty")),
            price=self._decimal_optional(
                self._first(row, "ft_ord_unpr3", "ovrs_ord_unpr", "price")
            ),
            raw_response=raw,
        )

    def _parse_fill(self, row: dict[str, Any], raw: dict[str, Any]) -> BrokerFill:
        return BrokerFill(
            broker_order_id=self._string_optional(self._first(row, "odno", "ODNO")),
            broker_fill_id=self._string_optional(self._first(row, "odno", "exec_no", "ccnl_no")),
            symbol=self._string_optional(self._first(row, "pdno", "ovrs_pdno", "symb")),
            side=self._normalize_side(self._first(row, "sll_buy_dvsn_cd", "sll_buy_dvsn_name")),
            quantity=self._decimal_optional(self._first(row, "ft_ccld_qty", "ccld_qty", "qty")),
            price=self._decimal_optional(self._first(row, "ft_ccld_unpr3", "ccld_unpr", "price")),
            raw_response=raw,
        )

    def _normalize_order_status(self, row: dict[str, Any]) -> BrokerOrderStatus:
        raw_status = (
            self._string_optional(self._first(row, "ord_stat_name", "status")) or ""
        ).lower()
        if "거부" in raw_status or "reject" in raw_status:
            return BrokerOrderStatus.REJECTED
        if "취소" in raw_status or "cancel" in raw_status:
            return BrokerOrderStatus.CANCELED
        if "체결" in raw_status or "fill" in raw_status:
            remaining = self._decimal_optional(self._first(row, "nccs_qty", "rmn_qty"))
            if remaining and remaining > 0:
                return BrokerOrderStatus.PARTIALLY_FILLED
            return BrokerOrderStatus.FILLED
        return BrokerOrderStatus.UNKNOWN

    def _normalize_side(self, value: Any) -> BrokerOrderSide | None:
        text = str(value or "").lower()
        if text in {"02", "buy"} or "매수" in text:
            return BrokerOrderSide.BUY
        if text in {"01", "sell"} or "매도" in text:
            return BrokerOrderSide.SELL
        return None

    def _raise_for_error(self, status_code: int, body: dict[str, Any]) -> None:
        if status_code >= 400:
            raise KISAPIError(
                body.get("msg1") or body.get("error_description") or "KIS HTTP request failed.",
                status_code=status_code,
                error_code=body.get("msg_cd") or body.get("error"),
                body=body,
            )
        if body.get("rt_cd") not in (None, "0"):
            raise KISAPIError(
                body.get("msg1") or "KIS API request failed.",
                status_code=status_code,
                error_code=body.get("msg_cd"),
                body=body,
            )

    def _json_body(self, response: httpx.Response) -> dict[str, Any]:
        try:
            body = response.json()
        except ValueError as exc:
            raise KISAPIError(
                "KIS response was not JSON.",
                status_code=response.status_code,
                body={"text": response.text},
            ) from exc
        return body if isinstance(body, dict) else {"data": body}

    def _first_output(self, body: dict[str, Any], key: str) -> dict[str, Any]:
        values = self._output_list(body, key)
        return values[0] if values else {}

    def _output_list(self, body: dict[str, Any], key: str) -> list[dict[str, Any]]:
        output = body.get(key)
        if isinstance(output, list):
            return [item for item in output if isinstance(item, dict)]
        if isinstance(output, dict):
            return [output]
        return []

    def _first_from_rows(self, rows: list[dict[str, Any]], *keys: str) -> Any:
        for row in rows:
            value = self._first(row, *keys)
            if value not in (None, ""):
                return value
        return None

    def _first(self, row: Mapping[str, Any], *keys: str) -> Any:
        for key in keys:
            if key in row and row[key] not in (None, ""):
                return row[key]
        return None

    def _decimal_required(self, value: Any) -> Decimal:
        parsed = self._decimal_optional(value)
        if parsed is None:
            raise KISAPIError("Expected numeric KIS field was empty.", status_code=200)
        return parsed

    def _decimal_optional(self, value: Any) -> Decimal | None:
        if value in (None, ""):
            return None
        try:
            return Decimal(str(value).replace(",", "").strip())
        except (InvalidOperation, ValueError) as exc:
            raise KISAPIError(f"Invalid numeric KIS field: {value}", status_code=200) from exc

    def _decimal_str(self, value: Decimal) -> str:
        return format(value.normalize(), "f")

    def _string_required(self, value: Any) -> str:
        parsed = self._string_optional(value)
        if parsed is None:
            raise KISAPIError("Expected text KIS field was empty.", status_code=200)
        return parsed

    def _string_optional(self, value: Any) -> str | None:
        if value in (None, ""):
            return None
        return str(value).strip()
