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
    kis_base_url: str = "https://openapi.koreainvestment.com:9443"
    kis_mode: KisMode = KisMode.PAPER

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


@lru_cache
def get_settings() -> Settings:
    return Settings()
