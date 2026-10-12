"""Migrations on a scratch database: they apply to nothing, re-run cleanly, reverse, and match the models."""

from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url

from app.config import Settings
from app.models import Base
from tests.support.database import migrate, scratch_database

EXPECTED_TABLES = {
    "alembic_version",
    "accounts",
    "audit_events",
    "auth_tokens",
    "categories",
    "closed_periods",
    "cost_centers",
    "posting_accounts",
    "projects",
    "refresh_tokens",
    "tax_rules",
    "users",
    "vendors",
}
ENUM_TYPES = (
    "user_role",
    "document_status",
    "auth_purpose",
    "account_type",
    "project_kind",
    "tax_type",
    "tax_category",
    "posting_key",
)


def table_names(url: str) -> set[str]:
    engine = create_engine(url)
    try:
        return set(inspect(engine).get_table_names())
    finally:
        engine.dispose()


def test_migrations_apply_to_an_empty_database_and_rerun_cleanly(settings: Settings) -> None:
    with scratch_database(settings, migrated=False) as db:
        assert table_names(db.owner_url) == set()
        migrate(db.owner_url)
        assert table_names(db.owner_url) == EXPECTED_TABLES
        migrate(db.owner_url)  # a second run changes nothing and does not fail
        assert table_names(db.owner_url) == EXPECTED_TABLES


def test_migrations_reverse_to_nothing_and_apply_again(settings: Settings) -> None:
    with scratch_database(settings) as db:
        migrate(db.owner_url, "base", downgrade=True)
        engine = create_engine(db.owner_url)
        with engine.connect() as connection:
            types = connection.execute(
                text("SELECT typname FROM pg_type WHERE typname = ANY(:names)"), {"names": list(ENUM_TYPES)}
            ).all()
        engine.dispose()
        assert table_names(db.owner_url) == {"alembic_version"}
        assert types == []
        migrate(db.owner_url)
        assert table_names(db.owner_url) == EXPECTED_TABLES


def test_the_models_and_the_migrations_agree(settings: Settings) -> None:
    with scratch_database(settings) as db:
        engine = create_engine(db.owner_url)
        with engine.connect() as connection:
            context = MigrationContext.configure(connection, opts={"compare_type": True})
            assert compare_metadata(context, Base.metadata) == []
        engine.dispose()


def test_the_scratch_database_is_removed_afterwards(settings: Settings) -> None:
    with scratch_database(settings, migrated=False) as db:
        name = db.name
    admin = create_engine(
        make_url(settings.owner_database_url).set(database="postgres").render_as_string(hide_password=False),
        isolation_level="AUTOCOMMIT",
    )
    with admin.connect() as connection:
        found = connection.execute(text("SELECT 1 FROM pg_database WHERE datname = :n"), {"n": name}).first()
    admin.dispose()
    assert found is None
