from email.utils import formataddr
from functools import lru_cache
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import AliasChoices, Field, SecretStr, field_validator, model_validator
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
    # The commit this build came from, shown by /version. Render supplies RENDER_GIT_COMMIT on its own.
    git_sha: str = Field("unknown", validation_alias=AliasChoices("GIT_SHA", "RENDER_GIT_COMMIT"))
    # A production database is never seeded unless this is set on purpose: it is how a demonstration site gets its
    # sample people and documents. Leave it off for real data.
    allow_demo_seed: bool = False
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
    storage_folder: str = "daftar"
    max_upload_megabytes: int = 10
    max_image_pixels: int = 40_000_000
    max_attachments_per_document: int = 10

    # Email goes out over SMTP (Gmail when deployed, Mailpit locally), or to the log with "console" (development only).
    # MAIL_BACKEND may be left out: it is smtp when SMTP_USER is set, and console otherwise.
    mail_backend: Literal["console", "smtp"] | None = None
    smtp_from_email: str = "no-reply@daftar.pk"
    smtp_from_name: str = "Daftar"
    smtp_host: str = "mailpit"
    smtp_port: int = 1025
    smtp_user: str | None = None
    smtp_pass: SecretStr | None = None
    # false: connect plainly and, with a login, upgrade with STARTTLS (port 587). true: TLS from the first byte (465).
    smtp_secure: bool = False
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

    @field_validator("cloudinary_url", "smtp_user", "smtp_pass", "mail_backend", mode="before")
    @classmethod
    def _empty_means_unset(cls, value: object) -> object:
        return None if isinstance(value, str) and not value.strip() else value

    @field_validator("mail_backend", mode="before")
    @classmethod
    def _retired_backend_means_automatic(cls, value: object) -> object:
        """Email once also went through a mail API, chosen with MAIL_BACKEND=resend. That value is retired, and an old
        setting must not stop the API starting, so it means "choose by SMTP_USER", like an empty one."""
        return None if isinstance(value, str) and value.strip().lower() == "resend" else value

    @field_validator("mail_backend", mode="before")
    @classmethod
    def _provider_names_mean_smtp(cls, value: object) -> object:
        """MAIL_BACKEND=google (or gmail) is how the owner names it: both are SMTP."""
        return "smtp" if isinstance(value, str) and value.strip().lower() in {"google", "gmail"} else value

    @field_validator("smtp_from_name")
    @classmethod
    def _name_without_quotes(cls, value: str) -> str:
        """A name typed with quotes in an env file (SMTP_FROM_NAME='"Équipe Vision PME"') keeps them; drop them."""
        name = value.strip()
        while len(name) >= 2 and name[0] == name[-1] and name[0] in "\"'":
            name = name[1:-1].strip()
        return name or "Daftar"

    @field_validator("cloudinary_url")
    @classmethod
    def _cloudinary_url_has_its_scheme(cls, value: SecretStr | None) -> SecretStr | None:
        if value is not None and not value.get_secret_value().startswith("cloudinary://"):
            raise ValueError(
                "CLOUDINARY_URL must be the whole value from Cloudinary, which starts "
                "cloudinary://API_KEY:API_SECRET@CLOUD_NAME (without a leading CLOUDINARY_URL=)"
            )
        return value

    @model_validator(mode="after")
    def _storage_is_configured(self) -> "Settings":
        if self.storage_backend == "cloudinary" and self.cloudinary_url is None:
            raise ValueError("CLOUDINARY_URL is required when STORAGE_BACKEND is cloudinary")
        return self

    @model_validator(mode="after")
    def _mail_is_configured(self) -> "Settings":
        if self.smtp_user is not None and self.smtp_pass is None:
            raise ValueError("SMTP_PASS is required when SMTP_USER is set")
        if "@" not in self.smtp_from_email:
            raise ValueError("SMTP_FROM_EMAIL must be an email address")
        return self

    @model_validator(mode="after")
    def _refuse_unsafe_production(self) -> "Settings":
        if self.environment != "production":
            return self
        if self.storage_backend != "cloudinary":
            raise ValueError("receipts must be stored in Cloudinary in production")
        if self.mail_transport == "console":
            raise ValueError("email must go through SMTP in production, not the console (set SMTP_USER and SMTP_PASS)")
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
    def mail_transport(self) -> Literal["console", "smtp"]:
        if self.mail_backend is not None:
            return self.mail_backend
        return "smtp" if self.smtp_user is not None else "console"

    @property
    def mail_from(self) -> str:
        """The From header: name and address, with a name that is not plain ASCII encoded the way mail programs read."""
        return formataddr((self.smtp_from_name, self.smtp_from_email))

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
