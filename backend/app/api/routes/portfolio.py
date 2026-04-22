from datetime import UTC, datetime

from fastapi import APIRouter, Depends

from app.core.security import require_admin

router = APIRouter(dependencies=[Depends(require_admin)])


@router.get("/summary")
def portfolio_summary() -> dict[str, object]:
    return {
        "asOf": datetime.now(UTC).isoformat(),
        "baseCurrency": "USD",
        "accountMode": "cash_only",
        "grossExposurePct": 0,
        "cashBufferPct": 100,
        "positions": [],
        "status": "Awaiting broker connection",
    }
