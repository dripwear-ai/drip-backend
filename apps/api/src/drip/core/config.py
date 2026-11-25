import os
from pathlib import Path
from typing import Literal, Self
from urllib.parse import unquote, urlsplit

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[5]
DEFAULT_ENV_FILE = REPO_ROOT / ".env" if (REPO_ROOT / "pnpm-workspace.yaml").is_file() else None


class Settings(BaseSettings):
    """Application settings with environment validation and fail-closed security."""

    model_config = SettingsConfigDict(
        env_file=os.environ.get("DRIP_ENV_FILE", DEFAULT_ENV_FILE) or None,
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
        hide_input_in_errors=True,
    )

    # Environment
    ENVIRONMENT: Literal["development", "test", "staging", "production"] = Field(
        default="development", description="Environment: development, test, staging, production"
    )
    DEBUG: bool = Field(default=False, description="Debug mode")
    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO", description="Logging level"
    )
    VERSION: str = Field(default="0.1.0", description="API Version")

    # Authoritative Database (PostgreSQL)
    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://drip_user:drip_password@localhost:5435/drip_db",
        description="Async PostgreSQL connection string",
    )
    DB_POOL_SIZE: int = Field(default=10, description="Database connection pool size")
    DB_MAX_OVERFLOW: int = Field(default=20, description="Database connection pool max overflow")
    DB_POOL_TIMEOUT: int = Field(
        default=30, description="Database connection pool timeout in seconds"
    )

    # Catalog publication is fail-closed until the owner-approved D2/D5 policies are configured.
    CATALOG_PRICE_FRESHNESS_HOURS: int | None = Field(default=None, ge=1, le=720)
    CATALOG_MAX_PRICE_MINOR: int | None = Field(default=None, ge=1)
    CATALOG_ALLOWED_CATEGORIES: str = ""
    CATALOG_PUBLIC_RATE_PER_MINUTE: int | None = Field(default=None, ge=1, le=6000)
    CATALOG_PUBLIC_RATE_BURST: int | None = Field(default=None, ge=1, le=1000)

    # Ephemeral Cache (Redis)
    REDIS_URL: str = Field(
        default="redis://localhost:6381/0",
        description="Redis connection URL for ephemeral state, locks and rate limits",
    )
    REDIS_SOCKET_TIMEOUT: float = Field(default=5.0, description="Redis socket timeout in seconds")

    # Security & Tokens
    SECRET_KEY: str = Field(
        default="dev_secret_key_change_me_in_production_minimum_32_characters_long",
        description="Secret key for JWT and HMAC operations (min 32 chars)",
    )
    JWT_ALGORITHM: str = Field(default="HS256", description="JWT signing algorithm")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(
        default=30, description="Access token expiration in minutes"
    )
    REFRESH_TOKEN_EXPIRE_DAYS: int = Field(
        default=14, description="Refresh token expiration in days"
    )

    # CORS Configuration
    CORS_ORIGINS: str = Field(
        default="http://localhost:3000,http://localhost:3001,http://localhost:3002,http://localhost:8081,http://localhost:8083,exp://localhost:8081",
        description="Allowed CORS origins as comma-separated values",
    )

    @field_validator("ENVIRONMENT", mode="before")
    @classmethod
    def normalize_environment(cls, value: object) -> object:
        return value.strip().lower() if isinstance(value, str) else value

    @field_validator("LOG_LEVEL", mode="before")
    @classmethod
    def normalize_log_level(cls, value: object) -> object:
        return value.strip().upper() if isinstance(value, str) else value

    @field_validator("SECRET_KEY")
    @classmethod
    def validate_secret_key(cls, v: str, info: object) -> str:
        if len(v) < 32:
            raise ValueError("SECRET_KEY must be at least 32 characters long.")
        return v

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT.lower() == "production"

    @property
    def is_development(self) -> bool:
        return self.ENVIRONMENT.lower() == "development"

    def validate_production_security(self) -> None:
        """Fail closed in production if using default secrets."""
        if self.is_production:
            if "dev_secret_key" in self.SECRET_KEY.lower():
                raise ValueError(
                    "Production environment cannot run with default development SECRET_KEY!"
                )
            if self.DEBUG or self.LOG_LEVEL == "DEBUG":
                raise ValueError("Production must disable DEBUG and SQL query logging.")
            for name, value in (("DATABASE_URL", self.DATABASE_URL), ("REDIS_URL", self.REDIS_URL)):
                password = unquote(urlsplit(value).password or "")
                if not password or password.lower() in {
                    "drip_password",
                    "password",
                    "redis",
                    "changeme",
                    "change_me",
                }:
                    raise ValueError(f"Production {name} requires non-development credentials.")

    @model_validator(mode="after")
    def enforce_security(self) -> Self:
        self.validate_production_security()
        if (self.CATALOG_PUBLIC_RATE_PER_MINUTE is None) != (self.CATALOG_PUBLIC_RATE_BURST is None):
            raise ValueError("Catalog public rate and burst limits must be configured together.")
        return self


# Singleton settings instance
settings = Settings()
settings.validate_production_security()
