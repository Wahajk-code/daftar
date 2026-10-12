"""Money. One rounding rule, applied once, here. Division happens only in this module and in allocation.py."""

from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

CENT = Decimal("0.01")
ZERO = Decimal("0.00")
MAX_AMOUNT = Decimal("999999999999.99")
BASIS_POINTS_TOTAL = 10_000
PAISA_PER_RUPEE = 100


class MoneyError(ValueError):
    """A value that cannot be money."""


def parse_money(value: object, *, allow_negative: bool = False) -> Decimal:
    """Turn a client value into an exact two-place amount.

    Accepts a string, an int or a Decimal. A float is refused: 0.10 cannot be held in binary. More than two decimal
    places is refused rather than rounded, so a client never loses a digit silently.
    """
    if isinstance(value, bool | float):
        raise MoneyError("money must be a string or an integer, not a float or a boolean")
    if isinstance(value, Decimal):
        amount = value
    elif isinstance(value, int):
        amount = Decimal(value)
    elif isinstance(value, str):
        try:
            amount = Decimal(value.strip())
        except InvalidOperation as exc:
            raise MoneyError("not a number") from exc
    else:
        raise MoneyError("money must be a string or an integer")
    if not amount.is_finite():
        raise MoneyError("not a finite number")
    if amount != amount.quantize(CENT):
        raise MoneyError("at most two decimal places are allowed")
    amount = amount.quantize(CENT)
    if amount < 0 and not allow_negative:
        raise MoneyError("must not be negative")
    if abs(amount) > MAX_AMOUNT:
        raise MoneyError(f"must not exceed {format_money(MAX_AMOUNT)}")
    return amount


def round_money(value: Decimal) -> Decimal:
    """The one rounding rule: two places, half up. For computed values such as tax, never for client input."""
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def percent_of(amount: Decimal, basis_points: int) -> Decimal:
    """``amount`` times ``basis_points`` / 10,000, rounded once."""
    if isinstance(basis_points, bool) or not isinstance(basis_points, int):
        raise MoneyError("basis points must be an integer")
    return round_money(amount * basis_points / BASIS_POINTS_TOTAL)


def to_paisa(amount: Decimal) -> int:
    """Exact integer paisa. The amount must already have at most two places."""
    if amount != amount.quantize(CENT):
        raise MoneyError("at most two decimal places are allowed")
    return int(amount.quantize(CENT) * PAISA_PER_RUPEE)


def from_paisa(paisa: int) -> Decimal:
    return (Decimal(paisa) / PAISA_PER_RUPEE).quantize(CENT)


def to_json(amount: Decimal) -> str:
    """The wire form: a plain decimal string with two places and no separators, ``"1250.00"``."""
    return format(amount.quantize(CENT), "f")


def format_money(amount: Decimal) -> str:
    """The display form everywhere: ``1,234,567.00``. A negative amount has a leading minus: ``-1,234.00``."""
    return f"{amount.quantize(CENT):,.2f}"


MILLI = Decimal("0.001")


def parse_quantity(value: object) -> Decimal:
    """A positive quantity with at most three decimal places, from a string or an integer. Never a float."""
    if isinstance(value, bool | float):
        raise MoneyError("a quantity must be a string or an integer, not a float or a boolean")
    if isinstance(value, Decimal):
        quantity = value
    elif isinstance(value, int):
        quantity = Decimal(value)
    elif isinstance(value, str):
        try:
            quantity = Decimal(value.strip())
        except InvalidOperation as exc:
            raise MoneyError("not a number") from exc
    else:
        raise MoneyError("a quantity must be a string or an integer")
    if not quantity.is_finite() or quantity <= 0:
        raise MoneyError("must be greater than zero")
    if quantity != quantity.quantize(MILLI):
        raise MoneyError("at most three decimal places are allowed")
    if quantity > Decimal("99999999999.999"):
        raise MoneyError("is too large")
    return quantity.quantize(MILLI)


def quantity_to_json(quantity: Decimal) -> str:
    return format(quantity.quantize(MILLI), "f")
