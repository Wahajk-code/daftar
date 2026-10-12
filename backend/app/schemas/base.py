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

# An instant on the wire is ISO 8601 UTC with a trailing Z. A naive datetime is refused.
UtcInstant = Annotated[
    datetime,
    AfterValidator(require_utc),
    PlainSerializer(format_instant, return_type=str, when_used="json"),
]
