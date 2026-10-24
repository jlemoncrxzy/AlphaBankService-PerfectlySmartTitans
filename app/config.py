"""Конфигурация через pydantic-settings — читается из .env / окружения."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Alfa Insight MVP"
    database_url: str = "sqlite:///./data/app.db"

    jwt_secret: str = "dev-secret-change-me"
    jwt_alg: str = "HS256"
    jwt_expire_minutes: int = 480

    # По ТЗ разрешена только DeepSeek-V4.1-Flash.
    # provider=mock — детерминированный heuristic-фоллбэк для офлайн-демо.
    llm_provider: str = "mock"
    llm_model: str = "DeepSeek-V4.1-Flash"
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com/v1"

    max_events_per_run: int = 5
    max_retries: int = 1
    tool_timeout_seconds: int = 10


settings = Settings()