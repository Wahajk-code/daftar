from datetime import datetime, timedelta

from app.core.clock import Clock, require_utc


class FakeClock(Clock):
    """A clock that only moves when the test says so."""

    def __init__(self, start: datetime) -> None:
        self._now = require_utc(start)

    def now(self) -> datetime:
        return self._now

    def set(self, value: datetime) -> None:
        self._now = require_utc(value)

    def advance(self, **kwargs: float) -> None:
        self._now += timedelta(**kwargs)
