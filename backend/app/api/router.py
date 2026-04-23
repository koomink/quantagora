from fastapi import APIRouter

from app.api.routes import approvals, health, market, portfolio, risk, settings, signals, universe

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(settings.router, prefix="/api/settings", tags=["settings"])
api_router.include_router(portfolio.router, prefix="/api/portfolio", tags=["portfolio"])
api_router.include_router(market.router, prefix="/api/market", tags=["market"])
api_router.include_router(universe.router, prefix="/api/universe", tags=["universe"])
api_router.include_router(signals.router, prefix="/api/signals", tags=["signals"])
api_router.include_router(risk.router, prefix="/api/risk", tags=["risk"])
api_router.include_router(approvals.router, prefix="/api/approvals", tags=["approvals"])
