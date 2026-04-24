import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

import httpx
import pytest

from app.core.config import LlmProvider, Settings
from app.llm.base import LLMProviderResult, PromptPackage
from app.llm.openai_provider import OpenAIProvider
from app.llm.openrouter_provider import OpenRouterProvider
from app.services.llm_reports import LLMReportService


def _signal_row() -> SimpleNamespace:
    generated_at = datetime(2026, 4, 24, tzinfo=UTC)
    return SimpleNamespace(
        id=uuid4(),
        symbol="QQQ",
        action="buy",
        horizon="swing",
        confidence=Decimal("0.7300"),
        target_weight=Decimal("0.120000"),
        rationale="Trend and momentum remain aligned.",
        invalidation="Close below the 20D moving average.",
        generated_at=generated_at,
        expires_at=generated_at + timedelta(days=5),
        input_snapshot={"strategy": "trend_following", "indicators": {}, "regime": {}},
    )


def test_openai_provider_parses_json_chat_completion() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == "Bearer test-openai-key"
        payload = json.loads(request.content.decode("utf-8"))
        assert payload["model"] == "gpt-5-mini"
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "summary": "Structured response",
                                    "setup": "Stored signal setup",
                                    "confirmations": ["Trend is positive"],
                                    "invalidation_focus": "Watch trend support",
                                    "risk_flags": ["Review volatility"],
                                    "uncertainty": "Model confidence is moderate.",
                                    "risk_decision_locked": True,
                                }
                            )
                        }
                    }
                ]
            },
        )

    provider = OpenAIProvider(
        settings=Settings(openai_api_key="test-openai-key"),
        transport=httpx.MockTransport(handler),
    )

    result = provider.generate_json(
        prompt=PromptPackage(system="Return JSON.", user="Explain.", prompt_version="v1")
    )

    assert result.provider == "openai"
    assert result.parsed_json["summary"] == "Structured response"


def test_openrouter_provider_sends_openrouter_headers() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == "Bearer test-openrouter-key"
        assert request.headers["X-Title"] == "QuantAgora"
        assert request.headers["HTTP-Referer"] == "https://quantagora.local"
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "summary": "Universe summary",
                                    "key_drivers": ["High liquidity"],
                                    "risk_flags": ["Leverage review required"],
                                    "selection_discipline": "Filters remain deterministic.",
                                    "uncertainty": "Macro regime may shift.",
                                    "risk_decision_locked": True,
                                }
                            )
                        }
                    }
                ]
            },
        )

    provider = OpenRouterProvider(
        settings=Settings(
            llm_provider=LlmProvider.OPENROUTER,
            openrouter_api_key="test-openrouter-key",
            openrouter_site_url="https://quantagora.local",
        ),
        transport=httpx.MockTransport(handler),
    )

    result = provider.generate_json(
        prompt=PromptPackage(system="Return JSON.", user="Explain.", prompt_version="v1")
    )

    assert result.provider == "openrouter"
    assert result.parsed_json["summary"] == "Universe summary"


def test_trade_report_falls_back_when_provider_credentials_are_missing() -> None:
    session = Mock()
    session.scalars.return_value.first.return_value = _signal_row()

    result = LLMReportService(db=session, settings=Settings()).generate_trade_rationale(
        signal_id=str(session.scalars.return_value.first.return_value.id)
    )

    assert result["status"] == "fallback"
    assert result["fallback_used"] is True
    assert result["report"]["risk_decision_locked"] is True
    session.add.assert_called_once()
    session.commit.assert_called_once()


def test_trade_report_rejects_forbidden_extra_fields_from_llm(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = Mock()
    signal_row = _signal_row()
    session.scalars.return_value.first.return_value = signal_row

    class FakeProvider:
        def generate_json(self, *, prompt: PromptPackage) -> LLMProviderResult:
            return LLMProviderResult(
                provider="openai",
                model="gpt-5-mini",
                parsed_json={
                    "summary": "Trade summary for the stored signal setup.",
                    "setup": "Trend setup",
                    "confirmations": ["Momentum positive"],
                    "invalidation_focus": "Trend support",
                    "risk_flags": ["Volatility elevated"],
                    "uncertainty": "Moderate uncertainty",
                    "risk_decision_locked": True,
                    "decision": "approve_immediately",
                },
                request_payload={"model": "gpt-5-mini"},
                response_payload={"id": "resp_123"},
            )

    monkeypatch.setattr("app.services.llm_reports._build_provider", lambda settings: FakeProvider())

    result = LLMReportService(
        db=session,
        settings=Settings(openai_api_key="test-openai-key"),
    ).generate_trade_rationale(signal_id=str(signal_row.id))

    assert result["status"] == "fallback"
    assert result["fallback_used"] is True
    assert "Extra inputs are not permitted" in (result["error_message"] or "")


def test_trade_report_persists_valid_structured_output(monkeypatch: pytest.MonkeyPatch) -> None:
    session = Mock()
    signal_row = _signal_row()
    session.scalars.return_value.first.return_value = signal_row

    class FakeProvider:
        def generate_json(self, *, prompt: PromptPackage) -> LLMProviderResult:
            return LLMProviderResult(
                provider="openai",
                model="gpt-5-mini",
                parsed_json={
                    "summary": "Trade summary for the stored signal setup.",
                    "setup": "Trend setup remains constructive.",
                    "confirmations": ["Momentum positive", "Volatility contained"],
                    "invalidation_focus": "Watch the 20D moving average.",
                    "risk_flags": ["Leveraged ETF sizing still matters."],
                    "uncertainty": "Macro tape can still change quickly.",
                    "risk_decision_locked": True,
                },
                request_payload={"model": "gpt-5-mini"},
                response_payload={"id": "resp_456"},
            )

    monkeypatch.setattr("app.services.llm_reports._build_provider", lambda settings: FakeProvider())

    result = LLMReportService(
        db=session,
        settings=Settings(openai_api_key="test-openai-key"),
    ).generate_trade_rationale(signal_id=str(signal_row.id))

    assert result["status"] == "generated"
    assert result["fallback_used"] is False
    assert result["provider"] == "openai"
    assert result["report"]["summary"] == "Trade summary for the stored signal setup."
