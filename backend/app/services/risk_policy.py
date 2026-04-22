from pydantic import BaseModel, Field


class RiskPolicy(BaseModel):
    max_account_exposure_pct: float = Field(default=90, gt=0, le=100)
    min_cash_buffer_pct: float = Field(default=10, ge=0, le=100)
    max_single_stock_pct: float = Field(default=10, gt=0, le=100)
    max_broad_etf_pct: float = Field(default=20, gt=0, le=100)
    max_sector_etf_pct: float = Field(default=15, gt=0, le=100)
    max_leveraged_inverse_total_pct: float = Field(default=15, gt=0, le=100)
    max_single_leveraged_inverse_pct: float = Field(default=7, gt=0, le=100)
    daily_loss_limit_pct: float = Field(default=1, gt=0)
    weekly_loss_limit_pct: float = Field(default=3, gt=0)
    monthly_loss_limit_pct: float = Field(default=8, gt=0)
    max_drawdown_stop_pct: float = Field(default=12, gt=0)
    same_symbol_cooldown_days: int = Field(default=3, ge=0)


DEFAULT_RISK_POLICY = RiskPolicy()
