from functools import lru_cache
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.enums import YearMode

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

    web_base_url: str = "http://localhost:3001"
    # The BFF proves it is the BFF with this secret; only then is the client address it forwards trusted.
    bff_shared_secret: SecretStr | None = None

    access_token_ttl_seconds: int = 15 * 60
    refresh_token_ttl_days: int = 7
    invite_ttl_days: int = 7
    reset_ttl_minutes: int = 30
    argon2_time_cost: int = 3
    argon2_memory_kib: int = 65_536
    argon2_parallelism: int = 4

    # Rate-limit overrides as "limit/window_seconds", for example {"login_strict": "5/900"}. See core/rate_limit.py.
    rate_limit_overrides: dict[str, str] = {}
    rate_limit_max_keys: int = 50_000

    # Receipts and other attachments. "memory" keeps them in the process (development and tests); production requires
    # Cloudinary. Nothing here is a secret except the URL, which carries the API secret.
    storage_backend: Literal["cloudinary", "memory"] = "memory"
    cloudinary_url: SecretStr | None = None
    voucher_year_mode: YearMode = YearMode.CALENDAR
    storage_folder: str = "daftar"
    max_upload_megabytes: int = 10
    max_image_pixels: int = 40_000_000
    max_attachments_per_document: int = 10

    # Email: "console" logs the message (development only), "smtp" talks to Mailpit, "resend" calls Resend's API.
    mail_backend: Literal["console", "smtp", "resend"] = "console"
    mail_from: str = "Daftar <no-reply@daftar.pk>"
    smtp_host: str = "mailpit"
    smtp_port: int = 1025
    resend_api_key: SecretStr | None = None
    mail_timeout_seconds: int = 10

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

    @field_validator("cloudinary_url", "resend_api_key", mode="before")
    @classmethod
    def _empty_means_unset(cls, value: object) -> object:
        return None if isinstance(value, str) and not value.strip() else value

    @model_validator(mode="after")
    def _storage_is_configured(self) -> "Settings":
        if self.storage_backend == "cloudinary" and self.cloudinary_url is None:
            raise ValueError("CLOUDINARY_URL is required when STORAGE_BACKEND is cloudinary")
        return self

    @model_validator(mode="after")
    def _mail_is_configured(self) -> "Settings":
        if self.mail_backend == "resend" and self.resend_api_key is None:
            raise ValueError("RESEND_API_KEY is required when MAIL_BACKEND is resend")
        return self

    @model_validator(mode="after")
    def _refuse_unsafe_production(self) -> "Settings":
        if self.environment != "production":
            return self
        if self.storage_backend != "cloudinary":
            raise ValueError("receipts must be stored in Cloudinary in production")
        if self.mail_backend == "console":
            raise ValueError("email must go through SMTP or Resend in production, not the console")
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
    def max_upload_bytes(self) -> int:
        return self.max_upload_megabytes * 1024 * 1024

    @property
    def owner_database_url(self) -> str:
        """The connection used by migrations: the owner role when given, otherwise the application URL."""
        return self.migration_database_url or self.database_url


@lru_cache
def get_settings() -> Settings:
    return Settings()  # required fields come from the environment
