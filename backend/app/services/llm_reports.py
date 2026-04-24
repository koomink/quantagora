from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import sqlalchemy as sa
from pydantic import BaseModel, ValidationError
from sqlalchemy.orm import Session

from app.core.config import LlmProvider, Settings, get_settings
from app.db.models import AssetUniverseVersion as AssetUniverseVersionRow
from app.db.models import LLMReport as LLMReportRow
from app.db.models import Signal as SignalRow
from app.domain.models import (
    LlmReportRecord,
    LlmReportStatus,
    LlmReportType,
    PostTradeReviewReport,
    TradeRationaleReport,
    UniverseRationaleReport,
)
from app.llm import LLMProviderError, PromptPackage
from app.llm.openai_provider import OpenAIProvider
from app.llm.openrouter_provider import OpenRouterProvider
from app.llm.prompts import PROMPT_VERSION, build_prompt
from app.services.universe import get_current_universe


class LLMReportService:
    def __init__(self, *, db: Session, settings: Settings | None = None) -> None:
        self.db = db
        self.settings = settings or get_settings()

    def list_reports(
        self,
        *,
        limit: int = 20,
        report_type: LlmReportType | None = None,
        entity_type: str | None = None,
    ) -> list[dict[str, Any]]:
        query = sa.select(LLMReportRow).order_by(LLMReportRow.generated_at.desc()).limit(limit)
        if report_type is not None:
            query = query.where(LLMReportRow.report_type == report_type.value)
        if entity_type:
            query = query.where(LLMReportRow.entity_type == entity_type)
        rows = self.db.scalars(query).all()
        return [_serialize_report_row(row) for row in rows]

    def generate_current_universe_report(self) -> dict[str, Any]:
        universe = get_current_universe(self.db)
        version_row = self.db.scalars(
            sa.select(AssetUniverseVersionRow).where(
                AssetUniverseVersionRow.version_code == universe.version_id
            )
        ).first()
        context = {
            "version_id": universe.version_id,
            "status": universe.status,
            "member_count": len(universe.members),
            "top_symbols": [member.asset.symbol for member in universe.members[:10]],
            "filters": universe.metadata.get("thresholds", {}),
            "rejected_candidates": universe.rejected_candidates[:10],
        }
        return self._generate_and_persist_report(
            report_type=LlmReportType.UNIVERSE_RATIONALE,
            entity_type="universe_version",
            entity_id=universe.version_id,
            context=context,
            universe_version_id=version_row.id if version_row is not None else None,
        )

    def generate_trade_rationale(self, *, signal_id: str) -> dict[str, Any]:
        try:
            parsed_signal_id = UUID(signal_id)
        except ValueError as exc:
            raise ValueError(f"Signal {signal_id} was not found.") from exc

        signal_row = self.db.scalars(
            sa.select(SignalRow).where(SignalRow.id == parsed_signal_id)
        ).first()
        if signal_row is None:
            raise ValueError(f"Signal {signal_id} was not found.")
        context = {
            "signal_id": str(signal_row.id),
            "symbol": signal_row.symbol,
            "action": signal_row.action,
            "horizon": signal_row.horizon,
            "confidence": float(signal_row.confidence),
            "target_weight": float(signal_row.target_weight),
            "rationale": signal_row.rationale,
            "invalidation": signal_row.invalidation,
            "generated_at": signal_row.generated_at.isoformat(),
            "expires_at": signal_row.expires_at.isoformat(),
            "signal_snapshot": signal_row.input_snapshot,
        }
        return self._generate_and_persist_report(
            report_type=LlmReportType.TRADE_RATIONALE,
            entity_type="signal",
            entity_id=str(signal_row.id),
            context=context,
            signal_id=signal_row.id,
        )

    def generate_post_trade_review(self, *, payload: dict[str, Any]) -> dict[str, Any]:
        entity_id = str(payload.get("trade_id") or payload.get("symbol") or "manual-review")
        return self._generate_and_persist_report(
            report_type=LlmReportType.POST_TRADE_REVIEW,
            entity_type="post_trade_review",
            entity_id=entity_id,
            context=payload,
        )

    def _generate_and_persist_report(
        self,
        *,
        report_type: LlmReportType,
        entity_type: str,
        entity_id: str,
        context: dict[str, Any],
        signal_id: Any | None = None,
        universe_version_id: Any | None = None,
    ) -> dict[str, Any]:
        generated_at = datetime.now(UTC)
        schema = _schema_for_report_type(report_type)
        system_prompt, user_prompt = build_prompt(report_type, context)
        prompt = PromptPackage(
            system=system_prompt,
            user=user_prompt,
            prompt_version=PROMPT_VERSION,
        )

        request_payload = {
            "context": context,
            "reportType": report_type.value,
            "promptVersion": prompt.prompt_version,
        }
        response_payload: dict[str, Any] = {}
        error_message: str | None = None
        provider_name = self.settings.llm_provider.value
        fallback_used = False

        try:
            provider = _build_provider(self.settings)
            provider_result = provider.generate_json(prompt=prompt)
            provider_name = provider_result.provider
            request_payload = {
                **request_payload,
                "providerRequest": provider_result.request_payload,
            }
            response_payload = provider_result.response_payload
            validated = _validate_report(schema, provider_result.parsed_json)
            report_json = validated.model_dump(mode="json")
            status = LlmReportStatus.GENERATED
        except (LLMProviderError, ValidationError, ValueError) as exc:
            fallback_used = True
            error_message = str(exc)
            report_json = _fallback_report(
                report_type,
                context,
                error_message,
            ).model_dump(mode="json")
            status = LlmReportStatus.FALLBACK

        row = LLMReportRow(
            signal_id=signal_id,
            universe_version_id=universe_version_id,
            report_type=report_type.value,
            entity_type=entity_type,
            entity_id=entity_id,
            provider=provider_name,
            model=self.settings.llm_model,
            status=status.value,
            prompt_version=prompt.prompt_version,
            fallback_used=fallback_used,
            error_message=error_message,
            report_json=report_json,
            request_payload=request_payload,
            response_payload=response_payload,
            generated_at=generated_at,
        )
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return _serialize_report_row(row)


def _build_provider(settings: Settings) -> Any:
    if settings.llm_provider == LlmProvider.OPENAI:
        return OpenAIProvider(settings=settings)
    if settings.llm_provider == LlmProvider.OPENROUTER:
        return OpenRouterProvider(settings=settings)
    raise ValueError(f"Unsupported LLM provider: {settings.llm_provider}")


def _schema_for_report_type(report_type: LlmReportType) -> type[BaseModel]:
    if report_type == LlmReportType.UNIVERSE_RATIONALE:
        return UniverseRationaleReport
    if report_type == LlmReportType.TRADE_RATIONALE:
        return TradeRationaleReport
    if report_type == LlmReportType.POST_TRADE_REVIEW:
        return PostTradeReviewReport
    raise ValueError(f"Unsupported report type: {report_type}")


def _validate_report(schema: type[BaseModel], payload: dict[str, Any]) -> BaseModel:
    report = schema.model_validate(payload)
    if getattr(report, "risk_decision_locked", False) is not True:
        raise ValueError("LLM report must keep risk_decision_locked=true.")
    return report


def _fallback_report(
    report_type: LlmReportType,
    context: dict[str, Any],
    error_message: str,
) -> BaseModel:
    short_error = (
        error_message
        if len(error_message) <= 220
        else f"{error_message[:217].rstrip()}..."
    )
    if report_type == LlmReportType.UNIVERSE_RATIONALE:
        top_symbols = ", ".join(context.get("top_symbols", [])[:5]) or "the active universe"
        return UniverseRationaleReport(
            summary=(
                "Fallback summary for "
                f"{context.get('version_id', 'current universe')}: {top_symbols} remain "
                "the primary tracked assets."
            ),
            key_drivers=[
                "Universe members passed deterministic eligibility filters.",
                "Liquidity, price, and spread thresholds still define the candidate set.",
            ],
            risk_flags=[
                "LLM provider output was unavailable.",
                "Review rejected candidates separately before changing thresholds.",
            ],
            selection_discipline=(
                "Universe selection remains bounded by deterministic filters and broker "
                "support checks."
            ),
            uncertainty=f"Fallback report used because the LLM layer failed: {short_error}",
            risk_decision_locked=True,
        )
    if report_type == LlmReportType.TRADE_RATIONALE:
        symbol = context.get("symbol", "the asset")
        return TradeRationaleReport(
            summary=(
                f"Fallback trade rationale for {symbol}: the signal reflects the stored "
                "technical setup without changing execution rules."
            ),
            setup=str(context.get("rationale", "Stored signal rationale is available.")),
            confirmations=[
                f"Signal confidence remains {context.get('confidence', 'n/a')}.",
                "Risk and execution decisions remain outside the LLM layer.",
            ],
            invalidation_focus=str(
                context.get(
                    "invalidation",
                    "Review the stored invalidation condition.",
                )
            ),
            risk_flags=[
                "LLM provider output was unavailable.",
                "Human approval and deterministic risk checks still govern execution.",
            ],
            uncertainty=f"Fallback report used because the LLM layer failed: {short_error}",
            risk_decision_locked=True,
        )
    return PostTradeReviewReport(
        summary=f"Fallback post-trade review for {context.get('symbol', 'the trade')}.",
        outcome=(
            "The review falls back to the stored trade snapshot because the LLM layer "
            "was unavailable."
        ),
        what_worked=["Structured post-trade context was preserved for later review."],
        what_to_improve=["Regenerate the review when the configured LLM provider is available."],
        follow_ups=["Confirm the realized outcome against broker fills and risk logs."],
        uncertainty=f"Fallback report used because the LLM layer failed: {short_error}",
        risk_decision_locked=True,
    )


def _serialize_report_row(row: LLMReportRow) -> dict[str, Any]:
    return LlmReportRecord(
        report_id=str(row.id),
        report_type=LlmReportType(row.report_type),
        entity_type=row.entity_type,
        entity_id=row.entity_id,
        provider=row.provider,
        model=row.model,
        status=LlmReportStatus(row.status),
        prompt_version=row.prompt_version,
        fallback_used=row.fallback_used,
        generated_at=row.generated_at,
        error_message=row.error_message,
        report=row.report_json or {},
    ).model_dump(mode="json")
