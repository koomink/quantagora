from fastapi import APIRouter, Depends, status

from app.core.security import require_admin
from app.services.universe import get_current_universe

router = APIRouter(dependencies=[Depends(require_admin)])


@router.get("/current")
def current_universe() -> dict[str, object]:
    return get_current_universe().model_dump(mode="json")


@router.post("/refresh", status_code=status.HTTP_202_ACCEPTED)
def refresh_universe() -> dict[str, str]:
    return {
        "status": "accepted",
        "message": "Universe refresh job is not wired yet. Phase 5 will attach the engine.",
    }
