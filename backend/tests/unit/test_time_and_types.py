from datetime import UTC, date, datetime, timedelta, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest
from pydantic import TypeAdapter, ValidationError

from app.core.clock import Clock, format_instant, require_utc
from app.schemas.base import Money, RequestModel, UtcInstant
from tests.support.clock import FakeClock

KARACHI = ZoneInfo("Asia/Karachi")


def test_a_naive_datetime_is_refused() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        require_utc(datetime(2026, 10, 12, 14, 5))  # noqa: DTZ001 - the point of the test


def test_an_aware_datetime_is_converted_to_utc() -> None:
    plus_five = datetime(2026, 10, 12, 19, 5, tzinfo=timezone(timedelta(hours=5)))
    assert require_utc(plus_five) == datetime(2026, 10, 12, 14, 5, tzinfo=UTC)
    assert require_utc(plus_five).tzinfo is UTC


def test_instants_are_formatted_with_a_trailing_z() -> None:
    assert format_instant(datetime(2026, 10, 12, 14, 5, tzinfo=UTC)) == "2026-10-12T14:05:00Z"
    assert format_instant(datetime(2026, 10, 12, 19, 5, 7, 999, tzinfo=KARACHI)) == "2026-10-12T14:05:07Z"


def test_the_instant_type_refuses_a_naive_value_and_writes_z() -> None:
    adapter = TypeAdapter(UtcInstant)
    with pytest.raises(ValidationError):
        adapter.validate_python(datetime(2026, 10, 12, 14, 5))  # noqa: DTZ001
    with pytest.raises(ValidationError):
        adapter.validate_json('"2026-10-12T14:05:00"')
    value = adapter.validate_json('"2026-10-12T19:05:00+05:00"')
    assert adapter.dump_json(value) == b'"2026-10-12T14:05:00Z"'


def test_the_money_type_takes_strings_and_refuses_floats() -> None:
    adapter = TypeAdapter(Money)
    assert adapter.validate_python("1250.5") == Decimal("1250.50")
    assert adapter.dump_json(adapter.validate_python("1250")) == b'"1250.00"'
    for bad in (1250.5, "1.005", "-1.00", "abc"):
        with pytest.raises(ValidationError):
            adapter.validate_python(bad)
    with pytest.raises(ValidationError):
        adapter.validate_json("1250.5")


def test_request_models_reject_unknown_fields_and_trim_text() -> None:
    class Example(RequestModel):
        name: str

    assert Example(name="  Ayesha  ").name == "Ayesha"
    with pytest.raises(ValidationError, match="extra_forbidden"):
        Example.model_validate({"name": "x", "role": "admin"})


def test_today_is_the_date_in_the_display_zone() -> None:
    # 19:30 UTC on 12 October is 00:30 on 13 October in Karachi (UTC+5, no daylight saving).
    clock = FakeClock(datetime(2026, 10, 12, 19, 30, tzinfo=UTC))
    assert clock.today(KARACHI) == date(2026, 10, 13)
    assert clock.today(ZoneInfo("UTC")) == date(2026, 10, 12)
    clock.advance(hours=-1)  # 18:30 UTC is 23:30 in Karachi, still the 12th
    assert clock.today(KARACHI) == date(2026, 10, 12)


def test_the_system_clock_is_aware_utc() -> None:
    now = Clock().now()
    assert now.tzinfo is UTC
    assert abs(now - datetime.now(UTC)) < timedelta(seconds=5)
