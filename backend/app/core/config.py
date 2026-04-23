from decimal import Decimal
from enum import Enum
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppEnv(str, Enum):
    LOCAL = "local"
    PAPER = "paper"
    LIVE = "live"


class KisMode(str, Enum):
    PAPER = "paper"
    LIVE = "live"


class LlmProvider(str, Enum):
    OPENAI = "openai"
    OPENROUTER = "openrouter"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "QuantAgora Trading Assistant"
    app_env: AppEnv = AppEnv.LOCAL
    log_level: str = "INFO"
    admin_api_token: str = "dev-admin-token"
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    database_url: str = "postgresql+psycopg://quantagora:quantagora@localhost:5432/quantagora"

    kis_app_key: str = ""
    kis_app_secret: str = ""
    kis_account_no: str = ""
    kis_account_product_code: str = ""
    kis_base_url: str = ""
    kis_live_base_url: str = "https://openapi.koreainvestment.com:9443"
    kis_paper_base_url: str = "https://openapivts.koreainvestment.com:29443"
    kis_mode: KisMode = KisMode.PAPER
    kis_timeout_seconds: float = 10.0
    kis_rate_limit_per_second: float = 5.0

    market_quote_stale_seconds: int = 900
    market_daily_candle_lookback_days: int = 365
    market_data_default_symbols: str = "SPY,QQQ,TQQQ,SQQQ"
    market_extra_closed_dates: str = ""
    market_extra_early_close_dates: str = ""

    universe_seed_symbols: str = (
        "SPY,QQQ,DIA,IWM,VTI,TLT,GLD,XLK,XLF,XLV,XLE,XLI,XLY,XLP,SMH,"
        "TQQQ,SQQQ,SOXL,SOXS,UPRO,SPXU,AAPL,MSFT,NVDA,AMZN,GOOGL,META,TSLA"
    )
    universe_max_members: int = 30
    universe_min_price_usd: Decimal = Decimal("5")
    universe_max_price_usd: Decimal = Decimal("1000")
    universe_min_avg_dollar_volume_usd: Decimal = Decimal("50000000")
    universe_max_bid_ask_spread_bps: Decimal = Decimal("50")
    universe_liquidity_lookback_days: int = 60
    universe_leveraged_inverse_whitelist: str = "TQQQ,SQQQ,SOXL,SOXS,UPRO,SPXU"

    signal_lookback_days: int = 260
    signal_min_history_days: int = 200
    signal_expiry_days: int = 5
    signal_pullback_lookback_days: int = 5
    signal_scan_hour_utc: int = 21
    signal_scan_minute_utc: int = 15
    signal_scheduler_enabled: bool = False
    signal_volatility_max_annualized: float = 0.65
    signal_leveraged_volatility_max_annualized: float = 1.25

    telegram_bot_token: str = ""
    telegram_allowed_user_ids: str = ""
    telegram_webhook_secret: str = ""

    llm_provider: LlmProvider = LlmProvider.OPENAI
    llm_model: str = "gpt-5-mini"
    llm_base_url: str = ""
    openai_api_key: str = Field(default="", repr=False)
    openrouter_api_key: str = Field(default="", repr=False)

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def telegram_allowed_user_id_list(self) -> list[int]:
        ids: list[int] = []
        for raw_id in self.telegram_allowed_user_ids.split(","):
            raw_id = raw_id.strip()
            if raw_id:
                ids.append(int(raw_id))
        return ids

    @property
    def market_default_symbol_list(self) -> list[str]:
        return [
            symbol.strip().upper()
            for symbol in self.market_data_default_symbols.split(",")
            if symbol.strip()
        ]

    @property
    def market_extra_closed_date_list(self) -> list[str]:
        return [
            date_value.strip()
            for date_value in self.market_extra_closed_dates.split(",")
            if date_value.strip()
        ]

    @property
    def market_extra_early_close_date_list(self) -> list[str]:
        return [
            date_value.strip()
            for date_value in self.market_extra_early_close_dates.split(",")
            if date_value.strip()
        ]

    @property
    def universe_seed_symbol_list(self) -> list[str]:
        return [
            symbol.strip().upper()
            for symbol in self.universe_seed_symbols.split(",")
            if symbol.strip()
        ]

    @property
    def universe_leveraged_inverse_whitelist_set(self) -> set[str]:
        return {
            symbol.strip().upper()
            for symbol in self.universe_leveraged_inverse_whitelist.split(",")
            if symbol.strip()
        }

    @property
    def kis_effective_base_url(self) -> str:
        if self.kis_base_url:
            return self.kis_base_url.rstrip("/")
        if self.kis_mode == KisMode.LIVE:
            return self.kis_live_base_url.rstrip("/")
        return self.kis_paper_base_url.rstrip("/")

    @property
    def kis_cano(self) -> str:
        account_no = self.kis_account_no.replace("-", "").strip()
        return account_no[:8]

    @property
    def kis_product_code(self) -> str:
        if self.kis_account_product_code:
            return self.kis_account_product_code.strip()
        account_no = self.kis_account_no.replace("-", "").strip()
        if len(account_no) >= 10:
            return account_no[8:10]
        return ""


@lru_cache
def get_settings() -> Settings:
    return Settings()
