from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.security import require_admin
from app.db.session import get_db_session
from app.domain.models import LlmReportType
from app.services.llm_reports import LLMReportService

router = APIRouter(dependencies=[Depends(require_admin)])

DbSession = Annotated[Session, Depends(get_db_session)]
AppSettings = Annotated[Settings, Depends(get_settings)]
LimitQuery = Annotated[int, Query(ge=1, le=100)]


class PostTradeReviewRequest(BaseModel):
    trade_id: str | None = None
    symbol: str
    side: str
    entry_price: float | None = None
    exit_price: float | None = None
    pnl_pct: float | None = None
    holding_days: int | None = None
    notes: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


@router.get("/reports")
def list_reports(
    db: DbSession,
    settings: AppSettings,
    limit: LimitQuery = 20,
    report_type: LlmReportType | None = None,
    entity_type: str | None = None,
) -> dict[str, object]:
    service = LLMReportService(db=db, settings=settings)
    try:
        items = service.list_reports(limit=limit, report_type=report_type, entity_type=entity_type)
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="LLM report listing requires a reachable trading database.",
        ) from exc
    return {
        "items": items,
        "status": "No stored LLM reports" if not items else f"{len(items)} LLM reports",
    }


@router.post("/reports/universe/current", status_code=status.HTTP_202_ACCEPTED)
def generate_current_universe_report(db: DbSession, settings: AppSettings) -> dict[str, Any]:
    service = LLMReportService(db=db, settings=settings)
    try:
        return service.generate_current_universe_report()
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Universe explanation requires a reachable trading database.",
        ) from exc


@router.post("/reports/signals/{signal_id}", status_code=status.HTTP_202_ACCEPTED)
def generate_trade_rationale(
    signal_id: str,
    db: DbSession,
    settings: AppSettings,
) -> dict[str, Any]:
    service = LLMReportService(db=db, settings=settings)
    try:
        return service.generate_trade_rationale(signal_id=signal_id)
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Trade explanation requires a reachable trading database.",
        ) from exc
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/reports/post-trade-review", status_code=status.HTTP_202_ACCEPTED)
def generate_post_trade_review(
    request: PostTradeReviewRequest,
    db: DbSession,
    settings: AppSettings,
) -> dict[str, Any]:
    service = LLMReportService(db=db, settings=settings)
    try:
        return service.generate_post_trade_review(payload=request.model_dump(mode="json"))
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Post-trade review requires a reachable trading database.",
        ) from exc
