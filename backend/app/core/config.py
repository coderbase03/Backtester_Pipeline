"""
Application configuration via Pydantic Settings.

Reads from environment variables or .env file.
"""

from pathlib import Path
import json
from pydantic_settings import BaseSettings
from pydantic import Field, AliasChoices, field_validator
from typing import Optional

PROJECT_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    app_name: str = "Opus Backtrader API"
    debug: bool = Field(
        default=False,
        validation_alias=AliasChoices("OPUS_DEBUG", "APP_DEBUG"),
    )
    api_prefix: str = "/api"

    # Database
    database_url: str = Field(
        default="postgresql+asyncpg://opus:opus@localhost:5432/opus_backtrader",
        validation_alias=AliasChoices("OPUS_DATABASE_URL", "DATABASE_URL"),
        description="PostgreSQL connection string",
    )
    database_url_sync: str = Field(
        default="postgresql://opus:opus@localhost:5432/opus_backtrader",
        validation_alias=AliasChoices("OPUS_DATABASE_URL_SYNC", "DATABASE_URL_SYNC"),
        description="Sync connection string for Alembic",
    )

    # Redis
    redis_url: str = Field(
        default="redis://localhost:6379/0",
        validation_alias=AliasChoices("OPUS_REDIS_URL", "REDIS_URL"),
    )

    # CORS
    cors_origins: list[str] = ["http://localhost:3000", "http://localhost:8501"]

    # API Keys
    openai_api_key: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("OPUS_OPENAI_API_KEY", "OPENAI_API_KEY"),
    )
    glm_api_key: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("OPUS_GLM_API_KEY", "GLM_API_KEY"),
    )
    github_token: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("OPUS_GITHUB_TOKEN", "GITHUB_TOKEN"),
    )

    # Reddit
    reddit_client_id: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("OPUS_REDDIT_CLIENT_ID", "REDDIT_CLIENT_ID"),
    )
    reddit_client_secret: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("OPUS_REDDIT_CLIENT_SECRET", "REDDIT_CLIENT_SECRET"),
    )
    reddit_user_agent: str = Field(
        default="OpusBacktrader/2.0",
        validation_alias=AliasChoices("OPUS_REDDIT_USER_AGENT", "REDDIT_USER_AGENT"),
    )

    # TradingView
    tv_username: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("OPUS_TV_USERNAME", "TV_USERNAME"),
    )
    tv_password: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("OPUS_TV_PASSWORD", "TV_PASSWORD"),
    )

    # Backtest defaults
    default_cash: float = 100_000.0
    default_commission: float = 0.001

    model_config = {
        "env_file": str(PROJECT_ROOT / ".env"),
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
        "extra": "ignore",
        "env_prefix": "OPUS_",
    }

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value):
        if isinstance(value, str):
            raw = value.strip()
            if not raw:
                return []
            if raw.startswith("["):
                try:
                    parsed = json.loads(raw)
                    if isinstance(parsed, list):
                        return parsed
                except json.JSONDecodeError:
                    pass
            return [item.strip() for item in raw.split(",") if item.strip()]
        return value


settings = Settings()
