from typing import Annotated

from fastapi import APIRouter, Depends

from app.core.config import Settings, get_settings
from app.core.security import require_admin

router = APIRouter(dependencies=[Depends(require_admin)])


@router.get("/runtime")
def runtime_settings(settings: Annotated[Settings, Depends(get_settings)]) -> dict[str, str]:
    return {
        "environment": settings.app_env.value,
        "broker": "kis",
        "brokerMode": settings.kis_mode.value,
        "llmProvider": settings.llm_provider.value,
        "llmModel": settings.llm_model,
        "tradingSession": "US regular session only",
    }
