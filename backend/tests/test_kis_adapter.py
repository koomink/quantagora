import asyncio
import json
from decimal import Decimal

import httpx
import pytest

from app.brokers.kis import KISAPIError, KISBrokerAdapter
from app.brokers.schemas import BrokerOrderRequest, BrokerOrderSide, BrokerOrderStatus
from app.core.config import KisMode, Settings


def make_settings() -> Settings:
    return Settings(
        kis_app_key="app-key",
        kis_app_secret="app-secret",
        kis_account_no="12345678-01",
        kis_mode=KisMode.PAPER,
        kis_rate_limit_per_second=0,
    )


def test_get_quote_uses_token_and_normalizes_quote() -> None:
    asyncio.run(_test_get_quote_uses_token_and_normalizes_quote())


async def _test_get_quote_uses_token_and_normalizes_quote() -> None:
    seen_requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_requests.append(request)
        if request.url.path == "/oauth2/tokenP":
            return httpx.Response(200, json={"access_token": "token", "expires_in": 86400})
        if request.url.path == "/uapi/overseas-price/v1/quotations/price":
            assert request.headers["authorization"] == "Bearer token"
            assert request.headers["tr_id"] == "HHDFS00000300"
            assert request.url.params["EXCD"] == "NAS"
            assert request.url.params["SYMB"] == "AAPL"
            return httpx.Response(
                200,
                json={
                    "rt_cd": "0",
                    "msg_cd": "ok",
                    "msg1": "ok",
                    "output": {"last": "187.12", "pbid": "187.10", "pask": "187.13"},
                },
            )
        raise AssertionError(f"unexpected request: {request.url}")

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="https://test")
    adapter = KISBrokerAdapter(settings=make_settings(), client=client)

    quote = await adapter.get_quote("aapl")

    assert len(seen_requests) == 2
    assert quote.symbol == "AAPL"
    assert quote.last == Decimal("187.12")
    assert quote.bid == Decimal("187.10")
    assert quote.ask == Decimal("187.13")
    await client.aclose()


def test_place_order_uses_paper_tr_id_hashkey_and_order_body() -> None:
    asyncio.run(_test_place_order_uses_paper_tr_id_hashkey_and_order_body())


async def _test_place_order_uses_paper_tr_id_hashkey_and_order_body() -> None:
    seen_order_body: dict[str, object] | None = None

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal seen_order_body
        if request.url.path == "/oauth2/tokenP":
            return httpx.Response(200, json={"access_token": "token", "expires_in": 86400})
        if request.url.path == "/uapi/hashkey":
            return httpx.Response(200, json={"HASH": "hash-value"})
        if request.url.path == "/uapi/overseas-stock/v1/trading/order":
            seen_order_body = json.loads(request.content.decode())
            assert request.headers["tr_id"] == "VTTT1002U"
            assert request.headers["hashkey"] == "hash-value"
            return httpx.Response(
                200,
                json={
                    "rt_cd": "0",
                    "msg_cd": "ok",
                    "msg1": "ok",
                    "output": {"ODNO": "KIS12345"},
                },
            )
        raise AssertionError(f"unexpected request: {request.url}")

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="https://test")
    adapter = KISBrokerAdapter(settings=make_settings(), client=client)

    result = await adapter.place_order(
        BrokerOrderRequest(
            symbol="QQQ",
            side=BrokerOrderSide.BUY,
            quantity=Decimal("3"),
            limit_price=Decimal("451.25"),
        )
    )

    assert seen_order_body == {
        "CANO": "12345678",
        "ACNT_PRDT_CD": "01",
        "OVRS_EXCG_CD": "NASD",
        "PDNO": "QQQ",
        "ORD_QTY": "3",
        "OVRS_ORD_UNPR": "451.25",
        "CTAC_TLNO": "",
        "MGCO_APTM_ODNO": "",
        "SLL_TYPE": "",
        "ORD_SVR_DVSN_CD": "0",
        "ORD_DVSN": "00",
    }
    assert result.broker_order_id == "KIS12345"
    assert result.status == BrokerOrderStatus.SUBMITTED
    await client.aclose()


def test_api_error_is_normalized() -> None:
    asyncio.run(_test_api_error_is_normalized())


async def _test_api_error_is_normalized() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/oauth2/tokenP":
            return httpx.Response(200, json={"access_token": "token", "expires_in": 86400})
        return httpx.Response(200, json={"rt_cd": "1", "msg_cd": "EGW001", "msg1": "failed"})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="https://test")
    adapter = KISBrokerAdapter(settings=make_settings(), client=client)

    with pytest.raises(KISAPIError) as exc_info:
        await adapter.get_quote("AAPL")

    assert exc_info.value.error_code == "EGW001"
    assert "failed" in str(exc_info.value)
    await client.aclose()


def test_get_positions_uses_overseas_balance_endpoint() -> None:
    asyncio.run(_test_get_positions_uses_overseas_balance_endpoint())


async def _test_get_positions_uses_overseas_balance_endpoint() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/oauth2/tokenP":
            return httpx.Response(200, json={"access_token": "token", "expires_in": 86400})
        if request.url.path == "/uapi/overseas-stock/v1/trading/inquire-balance":
            assert request.headers["tr_id"] == "VTTS3012R"
            assert request.url.params["OVRS_EXCG_CD"] == "NASD"
            assert request.url.params["TR_CRCY_CD"] == "USD"
            return httpx.Response(
                200,
                json={
                    "rt_cd": "0",
                    "output1": [
                        {
                            "ovrs_pdno": "AAPL",
                            "ovrs_cblc_qty": "2",
                            "pchs_avg_pric": "180.5",
                            "frcr_evlu_amt2": "375.0",
                            "evlu_pfls_amt2": "14.0",
                        }
                    ],
                },
            )
        raise AssertionError(f"unexpected request: {request.url}")

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="https://test")
    adapter = KISBrokerAdapter(settings=make_settings(), client=client)

    positions = await adapter.get_positions()

    assert len(positions) == 1
    assert positions[0].symbol == "AAPL"
    assert positions[0].quantity == Decimal("2")
    assert positions[0].average_price == Decimal("180.5")
    await client.aclose()
