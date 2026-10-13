"""Company-wide accounting choices, set by the Accountant in charge.

For now there is one: the month the voucher numbering year starts in. Month 1 is the calendar year; July (7) gives the
July to June year that is named by the year it ends in."""

from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.config import Settings
from app.core.clock import Clock
from app.core.numbering import voucher_year
from app.core.principal import Principal
from app.models.master import AccountingSettings
from app.repositories import master as master_repository
from app.services.audit import AuditService


class AccountingSettingsService:
    def __init__(self, session: Session, clock: Clock, settings: Settings) -> None:
        self._session = session
        self._clock = clock
        self._settings = settings
        self._audit = AuditService(session, clock)

    def get(self) -> AccountingSettings:
        return master_repository.get_accounting_settings(self._session)

    def year_today(self, row: AccountingSettings) -> int:
        """The year a voucher dated today would be numbered in, so the screen can show what the choice means."""
        today = self._clock.today(ZoneInfo(self._settings.display_timezone))
        return voucher_year(today, row.fiscal_year_start_month)

    def set_year_start(self, actor: Principal, month: int) -> AccountingSettings:
        """Choose the month the numbering year starts in. Numbers already given are never changed: the counter is kept
        per type and year, so a different choice only affects vouchers posted from now on."""
        row = master_repository.get_accounting_settings(self._session)
        before = {"fiscal_year_start_month": row.fiscal_year_start_month}
        if row.fiscal_year_start_month == month:
            return row
        row.fiscal_year_start_month = month
        row.updated_by = actor.id
        row.updated_at = self._clock.now()
        self._session.flush()
        self._audit.record(
            actor_id=actor.id,
            action="accounting_settings.updated",
            entity_type="accounting_settings",
            entity_id=row.id,
            before=before,
            after={"fiscal_year_start_month": month},
        )
        self._session.commit()
        return row
