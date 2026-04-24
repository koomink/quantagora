from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.security import require_admin
from app.db.session import get_db_session
from app.services.signal_engine import SignalEngine

router = APIRouter(dependencies=[Depends(require_admin)])

DbSession = Annotated[Session, Depends(get_db_session)]
AppSettings = Annotated[Settings, Depends(get_settings)]
LimitQuery = Annotated[int, Query(ge=1, le=100)]


class SignalScanRequest(BaseModel):
    ignore_cooldown: bool = False


@router.get("")
def list_signals(
    db: DbSession,
    settings: AppSettings,
    limit: LimitQuery = 20,
) -> dict[str, object]:
    engine = SignalEngine(db=db, settings=settings)
    try:
        items = engine.list_signals(limit=limit)
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Signal listing requires a reachable trading database.",
        ) from exc
    active_count = sum(1 for item in items if item["status"] == "new")
    return {
        "items": items,
        "status": "No stored signals" if not items else f"{active_count} active signal candidates",
        "summary": {
            "count": len(items),
            "activeCount": active_count,
            "expiredCount": sum(1 for item in items if item["status"] == "expired"),
        },
    }


@router.post("/scan", status_code=status.HTTP_202_ACCEPTED)
def scan_signals(
    db: DbSession,
    settings: AppSettings,
    request: SignalScanRequest | None = None,
) -> dict[str, object]:
    payload = request or SignalScanRequest()
    engine = SignalEngine(db=db, settings=settings)
    try:
        result = engine.scan_active_universe(ignore_cooldown=payload.ignore_cooldown)
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Signal scan requires a reachable trading database.",
        ) from exc
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    return {
        "status": (
            "No new signal candidates generated"
            if not result.signals
            else f"{len(result.signals)} active signal candidates"
        ),
        "generatedAt": result.generated_at.isoformat(),
        "universeVersionId": result.universe_version_id,
        "regime": result.regime.model_dump(mode="json"),
        "items": result.signals,
        "skipped": result.skipped,
        "summary": {
            "count": len(result.signals),
            "activeCount": sum(1 for item in result.signals if item["status"] == "new"),
            "expiredCount": sum(1 for item in result.signals if item["status"] == "expired"),
            "skippedCount": len(result.skipped),
        },
    }
