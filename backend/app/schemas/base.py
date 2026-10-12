from datetime import datetime
from decimal import Decimal
from typing import Annotated, Any

from pydantic import AfterValidator, BaseModel, BeforeValidator, ConfigDict, PlainSerializer

from app.core import money
from app.core.clock import format_instant, require_utc


class RequestModel(BaseModel):
    """Base for every Create and Update schema: unknown fields are rejected, strings are trimmed."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class ResponseModel(BaseModel):
    """Base for every Read schema."""

    model_config = ConfigDict(from_attributes=True)


def _parse_amount(value: Any) -> Decimal:
    try:
        return money.parse_money(value)
    except money.MoneyError as exc:
        raise ValueError(str(exc)) from exc


# Money on the wire is a string with two places; a float or a third decimal place is refused at the boundary.
Money = Annotated[
    Decimal,
    BeforeValidator(_parse_amount),
    PlainSerializer(money.to_json, return_type=str, when_used="json"),
]


def _parse_signed_amount(value: Any) -> Decimal:
    try:
        return money.parse_money(value, allow_negative=True)
    except money.MoneyError as exc:
        raise ValueError(str(exc)) from exc


# A figure that may be negative, such as an amount still to allocate or an excess.
SignedMoney = Annotated[
    Decimal,
    BeforeValidator(_parse_signed_amount),
    PlainSerializer(money.to_json, return_type=str, when_used="json"),
]


def _must_be_positive(value: Decimal) -> Decimal:
    if value <= 0:
        raise ValueError("must be greater than zero")
    return value


# An amount that must be more than nothing: the amount of an expense, the price of a unit.
PositiveMoney = Annotated[Money, AfterValidator(_must_be_positive)]

# An instant on the wire is ISO 8601 UTC with a trailing Z. A naive datetime is refused.
UtcInstant = Annotated[
    datetime,
    AfterValidator(require_utc),
    PlainSerializer(format_instant, return_type=str, when_used="json"),
]


def blank_to_none(value: Any) -> Any:
    """An empty text box means "nothing", not an empty string."""
    return None if isinstance(value, str) and not value.strip() else value
