"""
Centralized application configuration.

All runtime configuration is sourced from environment variables (or a `.env`
file in local development) via pydantic-settings. Nothing here is hardcoded
so the service can be dropped into any environment (dev/staging/prod) with
only a change of environment variables — no code changes required.
"""
from functools import lru_cache
from typing import List, Literal

from pydantic import AnyHttpUrl, Field, PostgresDsn, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # --- General -----------------------------------------------------
    PROJECT_NAME: str = "Auth Service"
    ENVIRONMENT: Literal["development", "staging", "production", "test"] = "development"
    API_V1_PREFIX: str = "/api/v1"
    DEBUG: bool = False

    # --- Database ------------------------------------------------------
    # Async DSN, e.g. postgresql+asyncpg://user:pass@host:5432/dbname
    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/auth_db"
    )
    DATABASE_ECHO: bool = False
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20
    DB_POOL_TIMEOUT: int = 30

    # --- Security / JWT -------------------------------------------------
    # Generate with: openssl rand -hex 32
    SECRET_KEY: str = Field(..., description="Secret key used to sign JWTs")
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30
    # Rotate refresh tokens on every use (recommended, mitigates token replay)
    REFRESH_TOKEN_ROTATE: bool = True

    # --- Password policy --------------------------------------------------
    PASSWORD_MIN_LENGTH: int = 8
    PASSWORD_REQUIRE_UPPERCASE: bool = True
    PASSWORD_REQUIRE_LOWERCASE: bool = True
    PASSWORD_REQUIRE_DIGIT: bool = True
    PASSWORD_REQUIRE_SPECIAL: bool = True

    # --- Account lockout / brute-force protection ------------------------
    MAX_FAILED_LOGIN_ATTEMPTS: int = 5
    ACCOUNT_LOCKOUT_MINUTES: int = 15

    # --- Rate limiting -----------------------------------------------
    RATE_LIMIT_LOGIN: str = "5/minute"
    RATE_LIMIT_REGISTER: str = "3/minute"
    RATE_LIMIT_DEFAULT: str = "100/minute"

    # --- CORS -----------------------------------------------------------
    BACKEND_CORS_ORIGINS: List[str] = []

    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v):
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",") if i.strip()]
        return v

    # --- Superuser bootstrap (optional, for initial setup) ---------------
    FIRST_SUPERUSER_EMAIL: str | None = None
    FIRST_SUPERUSER_PASSWORD: str | None = None

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"


@lru_cache
def get_settings() -> Settings:
    """Cached settings accessor — avoids re-parsing env on every import."""
    return Settings()


settings = get_settings()
