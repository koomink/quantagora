from fastapi import APIRouter, Depends

from app.core.security import require_admin
from app.services.risk_policy import DEFAULT_RISK_POLICY

router = APIRouter(dependencies=[Depends(require_admin)])


@router.get("/status")
def risk_status() -> dict[str, object]:
    return {
        "state": "idle",
        "newEntriesAllowed": False,
        "reason": "Broker account and market data are not connected yet.",
        "policy": DEFAULT_RISK_POLICY.model_dump(mode="json"),
    }
