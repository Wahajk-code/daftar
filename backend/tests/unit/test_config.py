from typing import Any

import pytest
from pydantic import ValidationError

from app.config import Settings
from app.main import create_app

STRONG_KEY = "f3a9c1d27b8e4a60915d2c7e8b3f4a1d6e0c95b7a2d8f13e"
URL = "postgresql+psycopg://u:p@localhost:5432/db"
CLOUDINARY = "cloudinary://key:secret@demo-cloud"


def make(**overrides: Any) -> Settings:
    values: dict[str, Any] = {
        "secret_key": STRONG_KEY,
        "database_url": URL,
        "environment": "production",
        "storage_backend": "cloudinary",
        "cloudinary_url": CLOUDINARY,
    }
    return Settings(**{**values, **overrides})


def test_a_strong_production_configuration_starts() -> None:
    assert make().environment == "production"


def test_production_refuses_debug() -> None:
    with pytest.raises(ValidationError, match="DEBUG"):
        make(debug=True)


@pytest.mark.parametrize(
    "key",
    [
        "short",
        "a" * 40,
        "dev-only-key-do-not-use-outside-local-development",
        "please-change-me-" + "x9Qz" * 8,
    ],
    ids=["too short", "one repeated character", "development placeholder", "marker word"],
)
def test_production_refuses_a_weak_key(key: str) -> None:
    with pytest.raises(ValidationError, match="SECRET_KEY"):
        make(secret_key=key)


def test_the_process_refuses_to_start_with_an_unsafe_production_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """What the real start-up reads: the environment. Settings are built when the app module is imported."""
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("DEBUG", "true")
    monkeypatch.setenv("SECRET_KEY", STRONG_KEY)
    monkeypatch.setenv("DATABASE_URL", URL)
    monkeypatch.setenv("STORAGE_BACKEND", "cloudinary")
    monkeypatch.setenv("CLOUDINARY_URL", CLOUDINARY)
    with pytest.raises(ValidationError, match="DEBUG"):
        Settings()
    monkeypatch.setenv("DEBUG", "false")
    monkeypatch.setenv("SECRET_KEY", "short")
    with pytest.raises(ValidationError, match="SECRET_KEY"):
        Settings()
    monkeypatch.setenv("SECRET_KEY", STRONG_KEY)
    assert create_app(Settings()).title == "Daftar API"


def test_development_may_use_debug_and_a_placeholder_key() -> None:
    settings = make(
        environment="development", debug=True, secret_key="dev-only-key-do-not-use-outside-local-development"
    )
    assert settings.debug


def test_the_display_timezone_must_be_a_real_zone() -> None:
    with pytest.raises(ValidationError, match="IANA"):
        make(display_timezone="Mars/Olympus")
    assert make(display_timezone="UTC").display_timezone == "UTC"


def test_the_default_display_timezone_is_karachi() -> None:
    assert make().display_timezone == "Asia/Karachi"


def test_migrations_use_the_owner_url_when_given() -> None:
    assert make(migration_database_url=None).owner_database_url == URL
    assert make(migration_database_url="postgresql+psycopg://owner@h/db").owner_database_url.startswith(
        "postgresql+psycopg://owner"
    )
