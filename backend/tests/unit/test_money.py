from decimal import Decimal

import pytest
from hypothesis import given
from hypothesis import strategies as st

from app.core import money
from app.core.money import MAX_AMOUNT, MoneyError

cents = st.integers(min_value=-99_999_999_999_999, max_value=99_999_999_999_999)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("1250.00", "1250.00"),
        ("1250.5", "1250.50"),
        (1250, "1250.00"),
        (" 7 ", "7.00"),
        (Decimal("0.10"), "0.10"),
    ],
)
def test_parse_accepts_exact_amounts(raw: object, expected: str) -> None:
    assert money.parse_money(raw) == Decimal(expected)


@pytest.mark.parametrize("raw", [0.1, 1250.0, True, None, [], "abc", "", "NaN", "Infinity", "1.005", "1e2x"])
def test_parse_refuses_floats_and_junk(raw: object) -> None:
    with pytest.raises(MoneyError):
        money.parse_money(raw)


def test_parse_refuses_negative_unless_allowed() -> None:
    with pytest.raises(MoneyError):
        money.parse_money("-1.00")
    assert money.parse_money("-1.00", allow_negative=True) == Decimal("-1.00")


def test_parse_enforces_the_maximum() -> None:
    assert money.parse_money("999999999999.99") == MAX_AMOUNT
    with pytest.raises(MoneyError):
        money.parse_money("1000000000000.00")


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("0.005", "0.01"), ("0.015", "0.02"), ("2.675", "2.68"), ("2.674", "2.67"), ("-0.005", "-0.01")],
)
def test_round_money_is_half_up(raw: str, expected: str) -> None:
    assert money.round_money(Decimal(raw)) == Decimal(expected)


def test_percent_of_rounds_once() -> None:
    assert money.percent_of(Decimal("1000.00"), 1500) == Decimal("150.00")
    assert money.percent_of(Decimal("100.01"), 3333) == Decimal("33.33")
    assert money.percent_of(Decimal("0.01"), 5000) == Decimal("0.01")  # half a paisa rounds up


def test_percent_of_refuses_a_non_integer_rate() -> None:
    with pytest.raises(MoneyError):
        money.percent_of(Decimal("10.00"), 15.5)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("amount", "shown"),
    [
        ("1234567", "1,234,567.00"),
        ("0.5", "0.50"),
        ("-1234", "-1,234.00"),
        ("999999999999.99", "999,999,999,999.99"),
    ],
)
def test_format_money_uses_one_convention(amount: str, shown: str) -> None:
    assert money.format_money(Decimal(amount)) == shown


def test_wire_form_is_a_plain_two_place_string() -> None:
    assert money.to_json(Decimal("1250")) == "1250.00"
    assert money.to_json(Decimal("1234567.5")) == "1234567.50"


@given(cents)
def test_paisa_round_trip(paisa: int) -> None:
    assert money.to_paisa(money.from_paisa(paisa)) == paisa


@given(cents)
def test_parse_of_the_wire_form_is_the_identity(paisa: int) -> None:
    amount = money.from_paisa(paisa)
    assert money.parse_money(money.to_json(amount), allow_negative=True) == amount


@given(st.decimals(min_value=Decimal(-10) ** 9, max_value=Decimal(10) ** 9, allow_nan=False, places=6))
def test_rounding_is_idempotent_and_within_half_a_paisa(value: Decimal) -> None:
    rounded = money.round_money(value)
    assert money.round_money(rounded) == rounded
    assert abs(rounded - value) <= Decimal("0.005")


def test_to_paisa_refuses_a_third_decimal_place() -> None:
    with pytest.raises(MoneyError):
        money.to_paisa(Decimal("1.001"))
