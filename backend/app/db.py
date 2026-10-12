"""Engine and session. A bounded pool, UTC sessions, and timeouts so a stuck transaction cannot block everyone.

Services own the transaction and commit it. The session dependency never commits: whatever was not committed is rolled
back when the session closes.
"""

from collections.abc import Iterator
from functools import lru_cache

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import Settings, get_settings


def connection_options(settings: Settings) -> str:
    return " ".join(
        (
            "-c timezone=UTC",
            f"-c statement_timeout={settings.db_statement_timeout_ms}",
            f"-c lock_timeout={settings.db_lock_timeout_ms}",
            f"-c idle_in_transaction_session_timeout={settings.db_idle_in_transaction_timeout_ms}",
        )
    )


def build_engine(url: str, settings: Settings) -> Engine:
    return create_engine(
        url,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        pool_timeout=settings.db_pool_timeout_seconds,
        pool_recycle=1800,
        pool_pre_ping=True,
        connect_args={"options": connection_options(settings), "application_name": "daftar-api"},
    )


@lru_cache
def get_engine() -> Engine:
    settings = get_settings()
    return build_engine(settings.database_url, settings)


@lru_cache
def get_session_factory() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), expire_on_commit=False)


def get_session() -> Iterator[Session]:
    with get_session_factory()() as session:
        yield session
