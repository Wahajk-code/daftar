"""Helpers for the two database setups: the fast one (rolled back per test) and the committing scratch database."""

import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from alembic.config import Config
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from alembic import command
from app.config import Settings
from app.db import build_engine

ALEMBIC_INI = Path(__file__).resolve().parents[2] / "alembic.ini"
TEST_DATABASE = "daftar_test"


def render(url: str, database: str) -> str:
    return make_url(url).set(database=database).render_as_string(hide_password=False)


def require_test_database(settings: Settings) -> None:
    """Tests never touch development data: refuse to run unless the configured database is the test one."""
    for url in (settings.database_url, settings.owner_database_url):
        name = make_url(url).database
        if name != TEST_DATABASE:
            raise RuntimeError(f"tests must run against {TEST_DATABASE!r}, but the configured database is {name!r}")


def migrate(url: str, revision: str = "head", *, downgrade: bool = False) -> None:
    config = Config(str(ALEMBIC_INI))
    config.attributes["url"] = url
    config.attributes["configure_logging"] = False
    (command.downgrade if downgrade else command.upgrade)(config, revision)


def reset_schema(owner_url: str) -> None:
    engine = create_engine(owner_url, isolation_level="AUTOCOMMIT")
    with engine.connect() as connection:
        connection.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
        connection.execute(text("CREATE SCHEMA public"))
    engine.dispose()


def clear_starting_data(owner_url: str) -> None:
    """Empty the chart of accounts, categories and posting accounts that migration 0005 seeds, so tests build their own.
    The seed itself is tested on a fresh scratch database. Done as the owner; the tables are empty of references."""
    engine = create_engine(owner_url, isolation_level="AUTOCOMMIT")
    with engine.connect() as connection:
        connection.execute(text("TRUNCATE posting_accounts, categories, accounts CASCADE"))
    engine.dispose()


def settle_constraints(session: Session) -> None:
    """Fire every deferred constraint now. Tests never commit, so a deferred trigger would otherwise never run."""
    session.execute(text("SET CONSTRAINTS ALL IMMEDIATE"))


@dataclass(frozen=True)
class ScratchDatabase:
    name: str
    owner_url: str
    app_url: str


@contextmanager
def scratch_database(settings: Settings, *, migrated: bool = True) -> Iterator[ScratchDatabase]:
    """A throwaway database for tests that must really commit (races, migrations). Dropped afterwards."""
    require_test_database(settings)
    name = f"daftar_scratch_{uuid.uuid4().hex[:12]}"
    admin = create_engine(render(settings.owner_database_url, "postgres"), isolation_level="AUTOCOMMIT")
    scratch = ScratchDatabase(
        name=name,
        owner_url=render(settings.owner_database_url, name),
        app_url=render(settings.database_url, name),
    )
    with admin.connect() as connection:
        connection.execute(text(f'CREATE DATABASE "{name}"'))
    try:
        if migrated:
            migrate(scratch.owner_url)
        yield scratch
    finally:
        with admin.connect() as connection:
            connection.execute(text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
        admin.dispose()


def app_engine_for(url: str, settings: Settings) -> Engine:
    return build_engine(url, settings)
