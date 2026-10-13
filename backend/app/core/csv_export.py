"""CSV output rules (domain rules section 9): UTF-8 with a byte-order mark so Excel reads Urdu text, amounts as plain
decimals, and any text cell that a spreadsheet could read as a formula is neutralised."""

import csv
import io
from collections.abc import Iterable, Iterator, Sequence
from decimal import Decimal

BYTE_ORDER_MARK = "﻿"
# A cell starting with one of these is a formula to Excel and Sheets. The tab and carriage return are the other starts
# that spreadsheets treat that way.
FORMULA_STARTS = ("=", "+", "-", "@", "\t", "\r")


def text_cell(value: str | None) -> str:
    """Text for a cell. A leading apostrophe makes a would-be formula plain text."""
    if not value:
        return ""
    return "'" + value if value.startswith(FORMULA_STARTS) else value


def amount_cell(value: Decimal) -> str:
    """A plain decimal with two places and no thousands separator, so it sorts and sums in any spreadsheet."""
    return f"{value:.2f}"


def render(header: Sequence[str], rows: Iterable[Sequence[str]]) -> Iterator[bytes]:
    """The file, one chunk per row, so a large export is never built in one piece. Rows are already cell text."""
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\r\n")
    writer.writerow(header)
    yield (BYTE_ORDER_MARK + buffer.getvalue()).encode("utf-8")
    for row in rows:
        buffer.seek(0)
        buffer.truncate()
        writer.writerow(row)
        yield buffer.getvalue().encode("utf-8")
