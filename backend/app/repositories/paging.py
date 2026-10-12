from typing import Any

from sqlalchemy import ColumnElement, Select, func, select
from sqlalchemy.orm import InstrumentedAttribute, Session

from app.core.errors import FieldError, ValidationFailedError


def order_clauses(
    sort: str | None,
    allowed: dict[str, InstrumentedAttribute[Any]],
    default: str,
    tiebreaker: InstrumentedAttribute[Any],
) -> list[ColumnElement[Any]]:
    """ORDER BY from a whitelisted field name, with `-` for descending. Anything else is a 422, never passed to SQL."""
    requested = sort or default
    descending = requested.startswith("-")
    name = requested.removeprefix("-")
    column = allowed.get(name)
    if column is None:
        raise ValidationFailedError(
            "That sort field is not available.",
            errors=[FieldError("sort", f"Sort by one of: {', '.join(sorted(allowed))}.", "invalid_sort")],
        )
    return [column.desc() if descending else column.asc(), tiebreaker.asc()]


def paginate[T](
    session: Session, statement: Select[T], order: list[ColumnElement[Any]], *, limit: int, offset: int
) -> tuple[list[T], int]:
    """One page and the total across all pages."""
    total = session.scalar(select(func.count()).select_from(statement.order_by(None).subquery())) or 0
    rows = list(session.scalars(statement.order_by(*order).limit(limit).offset(offset)))
    return rows, total
