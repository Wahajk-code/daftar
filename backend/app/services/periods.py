"""Closing and reopening accounting periods, and the accounts a generated voucher posts to."""

from datetime import date

from sqlalchemy.orm import Session

from app.core.clock import Clock
from app.core.enums import AccountType, PostingKey
from app.core.errors import ConflictError, ErrorCode, FieldError, NotFoundError, ValidationFailedError
from app.core.principal import Principal
from app.models.master import ClosedPeriod, PostingAccount
from app.repositories import master as master_repository
from app.services.audit import AuditService

# What kind of account each posting key may point at.
KEY_TYPES: dict[PostingKey, AccountType] = {
    PostingKey.CASH: AccountType.ASSET,
    PostingKey.BANK: AccountType.ASSET,
    PostingKey.INPUT_SALES_TAX: AccountType.ASSET,
    PostingKey.SALES_TAX_WITHHELD: AccountType.LIABILITY,
    PostingKey.INCOME_TAX_WITHHELD: AccountType.LIABILITY,
}


class PeriodService:
    def __init__(self, session: Session, clock: Clock) -> None:
        self._session = session
        self._clock = clock
        self._audit = AuditService(session, clock)

    def list_periods(self, *, sort: str | None, limit: int, offset: int) -> tuple[list[ClosedPeriod], int]:
        return master_repository.list_periods(self._session, sort=sort, limit=limit, offset=offset)

    def close(self, actor: Principal, start: date, end: date) -> ClosedPeriod:
        """Close an inclusive range of dates to posting. A range that overlaps one already closed is refused by the
        database (`no_overlapping_closed_ranges`)."""
        period = ClosedPeriod(start_date=start, end_date=end, closed_by=actor.id, closed_at=self._clock.now())
        master_repository.add(self._session, period)
        self._audit.record(
            actor_id=actor.id,
            action="period.closed",
            entity_type="period",
            entity_id=period.id,
            after={"start_date": start.isoformat(), "end_date": end.isoformat()},
        )
        self._session.commit()
        return period

    def reopen(self, actor: Principal, period_id: int) -> ClosedPeriod:
        period = master_repository.get_period(self._session, period_id)
        if period is None:
            raise NotFoundError("There is no such period.")
        if period.reopened_at is not None:
            raise ConflictError("That period was already reopened.", code=ErrorCode.CONFLICT)
        period.reopened_by = actor.id
        period.reopened_at = self._clock.now()
        self._audit.record(
            actor_id=actor.id,
            action="period.reopened",
            entity_type="period",
            entity_id=period.id,
            before={"start_date": period.start_date.isoformat(), "end_date": period.end_date.isoformat()},
        )
        self._session.commit()
        return period


class PostingAccountService:
    def __init__(self, session: Session, clock: Clock) -> None:
        self._session = session
        self._clock = clock
        self._audit = AuditService(session, clock)

    def list_all(self) -> list[PostingAccount]:
        return master_repository.list_posting_accounts(self._session)

    def set(self, actor: Principal, key: PostingKey, account_id: int) -> PostingAccount:
        account = master_repository.get_account(self._session, account_id)
        wanted = KEY_TYPES[key]
        problem = None
        if account is None or not account.is_active:
            problem = "Choose an active account."
        elif not account.is_postable:
            problem = "Choose an account that can be posted to, not a parent account."
        elif account.type is not wanted:
            problem = f"This needs a {wanted.value} account."
        if problem:
            raise ValidationFailedError(problem, errors=[FieldError("account_id", problem, "invalid_account")])
        row = master_repository.get_posting_account(self._session, key)
        before = None if row is None else {"account_id": row.account_id}
        if row is None:
            row = PostingAccount(key=key, account_id=account_id)
            self._session.add(row)
        row.account_id = account_id
        row.updated_by = actor.id
        row.updated_at = self._clock.now()
        self._session.flush()
        self._audit.record(
            actor_id=actor.id,
            action="posting_account.set",
            entity_type="posting_account",
            before=before,
            after={"key": key.value, "account_id": account_id},
        )
        self._session.commit()
        return row
