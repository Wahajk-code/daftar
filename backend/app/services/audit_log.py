"""Reading the audit log. Read only: nothing here writes, and the log can only be appended to (see AuditService)."""

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.config import Settings
from app.core.errors import FieldError, ValidationFailedError
from app.models.audit import AuditEvent
from app.repositories import audit as audit_repository


class AuditLogService:
    def __init__(self, session: Session, settings: Settings) -> None:
        self._session = session
        self._zone = ZoneInfo(settings.display_timezone)

    def search(
        self,
        *,
        actor_id: int | None,
        entity_type: str | None,
        entity_id: int | None,
        action: str | None,
        date_from: date | None,
        date_to: date | None,
        limit: int,
        offset: int,
    ) -> tuple[list[tuple[AuditEvent, str | None]], int]:
        """A page of the log, newest first. The dates are calendar days in the display zone, both included."""
        if date_from is not None and date_to is not None and date_from > date_to:
            raise ValidationFailedError(
                "The start date is after the end date.",
                errors=[FieldError("date_from", "Start on or before the end date.", "invalid_range")],
            )
        start = None if date_from is None else datetime.combine(date_from, time.min, tzinfo=self._zone)
        end = None if date_to is None else datetime.combine(date_to + timedelta(days=1), time.min, tzinfo=self._zone)
        return audit_repository.search(
            self._session,
            actor_id=actor_id,
            entity_type=entity_type,
            entity_id=entity_id,
            action=action.strip() if action else None,
            start=start,
            end=end,
            limit=limit,
            offset=offset,
        )
