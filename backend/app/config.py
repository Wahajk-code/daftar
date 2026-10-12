from functools import lru_cache
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

MIN_PRODUCTION_KEY_LENGTH = 32
MIN_PRODUCTION_KEY_DISTINCT_CHARACTERS = 10
WEAK_KEY_MARKERS = ("changeme", "change-me", "secret", "password", "dev-only", "test-only", "example")


class Settings(BaseSettings):
    """Process settings, read from the environment only. Docker Compose supplies them; no file is read here."""

    model_config = SettingsConfigDict(extra="ignore", frozen=True)

    environment: Literal["development", "test", "production"] = "development"
    debug: bool = False
    secret_key: SecretStr
    database_url: str
    migration_database_url: str | None = None
    display_timezone: str = "Asia/Karachi"
    git_sha: str = "unknown"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"

    db_pool_size: int = 5
    db_max_overflow: int = 5
    db_pool_timeout_seconds: int = 10
    db_statement_timeout_ms: int = 15_000
    db_lock_timeout_ms: int = 5_000
    db_idle_in_transaction_timeout_ms: int = 30_000

    @field_validator("display_timezone")
    @classmethod
    def _known_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError(f"{value!r} is not an IANA time zone") from exc
        return value

    @model_validator(mode="after")
    def _refuse_unsafe_production(self) -> "Settings":
        if self.environment != "production":
            return self
        if self.debug:
            raise ValueError("DEBUG must be off in production")
        key = self.secret_key.get_secret_value()
        lowered = key.lower()
        if (
            len(key) < MIN_PRODUCTION_KEY_LENGTH
            or len(set(key)) < MIN_PRODUCTION_KEY_DISTINCT_CHARACTERS
            or any(marker in lowered for marker in WEAK_KEY_MARKERS)
        ):
            raise ValueError("SECRET_KEY is too weak for production")
        return self

    @property
    def owner_database_url(self) -> str:
        """The connection used by migrations: the owner role when given, otherwise the application URL."""
        return self.migration_database_url or self.database_url


@lru_cache
def get_settings() -> Settings:
    return Settings()  # required fields come from the environment
