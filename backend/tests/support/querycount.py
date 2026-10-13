"""Count the SQL statements a block of code sends, to catch a list that asks the database once per row."""

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from sqlalchemy import Engine, event


@contextmanager
def count_statements(engine: Engine) -> Iterator[list[str]]:
    statements: list[str] = []

    def record(_connection: Any, _cursor: Any, statement: str, *_rest: Any) -> None:
        statements.append(statement)

    event.listen(engine, "before_cursor_execute", record)
    try:
        yield statements
    finally:
        event.remove(engine, "before_cursor_execute", record)
