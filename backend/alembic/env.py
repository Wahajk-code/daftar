"""Alembic environment. Migrations run as the owner role; afterwards the application role's privileges are applied."""

from logging.config import fileConfig

from sqlalchemy import Connection, create_engine, pool, text

from alembic import context
from app.config import get_settings
from app.db import connection_options
from app.models import Base

config = context.config
if config.config_file_name is not None and config.attributes.get("configure_logging", True):
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = Base.metadata

APP_ROLE = "daftar_app"
# Tables the application may only append to and read.
APPEND_ONLY_TABLES = ("audit_events",)


def apply_app_privileges(connection: Connection) -> None:
    """Give the application role exactly what it needs. Idempotent, so every migration run leaves the same grants.

    The role must exist (the Postgres init script creates it locally; the deploy steps create it on a host).
    Failing loudly here is deliberate: a silent skip would leave the audit log unprotected.
    """
    exists = connection.execute(text("SELECT 1 FROM pg_roles WHERE rolname = :name"), {"name": APP_ROLE}).first()
    if exists is None:
        raise RuntimeError(f"database role {APP_ROLE!r} does not exist; create it before migrating")
    connection.execute(text(f"GRANT USAGE ON SCHEMA public TO {APP_ROLE}"))
    connection.execute(text(f"GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {APP_ROLE}"))
    connection.execute(text(f"GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {APP_ROLE}"))
    for table in APPEND_ONLY_TABLES:
        # After a downgrade the table may be gone; there is nothing to protect then.
        if connection.execute(text("SELECT to_regclass(:name)"), {"name": f"public.{table}"}).scalar_one() is None:
            continue
        connection.execute(text(f"REVOKE ALL ON {table} FROM {APP_ROLE}"))
        connection.execute(text(f"GRANT SELECT, INSERT ON {table} TO {APP_ROLE}"))


def run_migrations_online() -> None:
    settings = get_settings()
    # Tests pass a URL for a scratch database through `attributes`; otherwise the owner URL from the environment.
    url = config.attributes.get("url") or settings.owner_database_url
    engine = create_engine(
        url,
        poolclass=pool.NullPool,
        connect_args={"options": connection_options(settings)},
    )
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()
            apply_app_privileges(connection)
    engine.dispose()


if context.is_offline_mode():
    raise RuntimeError("offline migrations are not supported: the privilege step needs a live connection")

run_migrations_online()
