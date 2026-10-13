from collections.abc import Callable, Sequence
from typing import Any

from sqlalchemy import ColumnElement, Select, and_, func, or_, select
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


MAX_SEARCH_TOKENS = 8


def search_clause(
    columns: Sequence[Any], q: str | None, *related: Callable[[str], ColumnElement[bool]]
) -> ColumnElement[bool] | None:
    """A search by tokens: the text is split into words, and a row matches when every word is found somewhere (in any
    of the columns, or in a related record through `related`), in any order and as part of a longer word. Each added
    word narrows the result, so a person keeps typing until the list is as short as they want. Words are literal text:
    a percent sign or underscore matches itself. Returns None when there is nothing to search for."""
    words = (q or "").lower().split()[:MAX_SEARCH_TOKENS]
    if not words:
        return None
    per_word: list[ColumnElement[bool]] = []
    for word in words:
        escaped = word.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        pattern = f"%{escaped}%"
        terms: list[ColumnElement[bool]] = [func.lower(column).like(pattern, escape="\\") for column in columns]
        terms.extend(make(pattern) for make in related)
        per_word.append(or_(*terms))
    return and_(*per_word)
