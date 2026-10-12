from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import DateTime, Dialect, MetaData
from sqlalchemy import Enum as SqlEnum
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.types import TypeDecorator

from app.core.clock import require_utc

# Explicit constraint names keep migrations stable and let error handling recognise a constraint by name.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class UtcDateTime(TypeDecorator[datetime]):
    """TIMESTAMPTZ that refuses a naive datetime going in and always returns UTC coming out."""

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        return None if value is None else require_utc(value)

    def process_result_value(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        return None if value is None else require_utc(value)


def pg_enum[E: StrEnum](enum_class: type[E], name: str, *, create_type: bool = True) -> SqlEnum:
    """A native PostgreSQL enum that stores the lower-case values, not the member names. Pass create_type=False
    when a second table reuses a type another table (or a migration) already created."""
    return SqlEnum(
        enum_class,
        name=name,
        values_callable=lambda members: [member.value for member in members],
        validate_strings=True,
        create_type=create_type,
    )


JsonDict = dict[str, Any]
