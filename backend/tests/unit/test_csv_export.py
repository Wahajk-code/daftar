"""CSV output rules (domain rules section 9)."""

import csv
import io
from decimal import Decimal

import pytest
from hypothesis import given
from hypothesis import strategies as st

from app.core.csv_export import BYTE_ORDER_MARK, FORMULA_STARTS, amount_cell, render, text_cell


@pytest.mark.parametrize("start", ["=", "+", "-", "@", "\t", "\r"])
def test_a_cell_that_could_be_a_formula_is_made_plain_text(start: str) -> None:
    assert text_cell(f"{start}SUM(A1:A9)") == f"'{start}SUM(A1:A9)"


@pytest.mark.parametrize("value", ["Ravi Stationers", "5100 Rent", "  =not first", "Zarai - Traders", "", None])
def test_ordinary_text_is_left_alone(value: str | None) -> None:
    assert text_cell(value) == (value or "")


@given(st.text())
def test_no_text_cell_ever_starts_like_a_formula(value: str) -> None:
    assert not text_cell(value).startswith(FORMULA_STARTS)


@pytest.mark.parametrize(
    ("value", "text"),
    [
        (Decimal("0"), "0.00"),
        (Decimal("1234567.5"), "1234567.50"),
        (Decimal("1000000.00"), "1000000.00"),
        (Decimal("0.05"), "0.05"),
    ],
)
def test_amounts_are_plain_decimals_with_no_thousands_separator(value: Decimal, text: str) -> None:
    assert amount_cell(value) == text


def test_the_file_starts_with_a_byte_order_mark_and_reads_back_urdu_text() -> None:
    body = b"".join(render(["Vendor", "Amount"], [["راوی اسٹیشنرز", "10.00"]]))
    assert body.startswith(BYTE_ORDER_MARK.encode("utf-8"))
    rows = list(csv.reader(io.StringIO(body.decode("utf-8-sig"))))
    assert rows == [["Vendor", "Amount"], ["راوی اسٹیشنرز", "10.00"]]


def test_commas_quotes_and_newlines_in_a_cell_survive_a_round_trip() -> None:
    nasty = 'He said "pay", then\nleft'
    body = b"".join(render(["Narration"], [[nasty]]))
    assert list(csv.reader(io.StringIO(body.decode("utf-8-sig"))))[1] == [nasty]


def test_the_file_is_produced_a_row_at_a_time() -> None:
    chunks = list(render(["A"], [["1"], ["2"], ["3"]]))
    assert len(chunks) == 4  # the header, then one per row
    assert chunks[0].startswith(BYTE_ORDER_MARK.encode("utf-8"))
