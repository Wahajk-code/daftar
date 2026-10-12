"""The only source of "now". The server stamps every instant, so nothing else calls the system clock."""

from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo


def require_utc(value: datetime) -> datetime:
    """Reject a naive datetime and convert an aware one to UTC."""
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("a timezone-aware datetime is required")
    return value.astimezone(UTC)


def format_instant(value: datetime) -> str:
    """ISO 8601 UTC with a trailing Z, to the second: ``2026-10-12T14:05:00Z``."""
    return require_utc(value).strftime("%Y-%m-%dT%H:%M:%SZ")


class Clock:
    """The system clock. Tests substitute a subclass that holds a fixed instant."""

    def now(self) -> datetime:
        return datetime.now(UTC)

    def today(self, zone: ZoneInfo) -> date:
        """The current calendar date in the display zone: the default `document_date` and the date of a reversal."""
        return self.now().astimezone(zone).date()
