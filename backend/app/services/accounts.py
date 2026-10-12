"""The chart of accounts. Parents are not postable; accounts deactivate, they are never deleted."""

from typing import Any

from sqlalchemy.orm import Session

from app.core.clock import Clock
from app.core.enums import AccountType
from app.core.errors import ConflictError, ErrorCode, FieldError, GuardFailedError, NotFoundError, ValidationFailedError
from app.core.principal import Principal
from app.models.base import JsonDict
from app.models.master import Account
from app.repositories import master as master_repository
from app.services.audit import AuditService
from app.services.master import changed, check_version, snapshot

FIELDS = ("code", "name", "type", "parent_id", "is_postable", "is_active")


class AccountService:
    def __init__(self, session: Session, clock: Clock) -> None:
        self._session = session
        self._clock = clock
        self._audit = AuditService(session, clock)

    def list_accounts(
        self,
        *,
        q: str | None,
        type_: AccountType | None,
        parent_id: int | None,
        is_active: bool | None,
        is_postable: bool | None,
        sort: str | None,
        limit: int,
        offset: int,
    ) -> tuple[list[Account], int]:
        return master_repository.list_accounts(
            self._session,
            q=q,
            type_=type_,
            parent_id=parent_id,
            is_active=is_active,
            is_postable=is_postable,
            sort=sort,
            limit=limit,
            offset=offset,
        )

    def get(self, account_id: int) -> Account:
        account = master_repository.get_account(self._session, account_id)
        if account is None:
            raise NotFoundError("There is no such account.")
        return account

    def create(self, actor: Principal, data: dict[str, Any]) -> Account:
        parent: Account | None = None
        if data.get("parent_id") is not None:
            parent = master_repository.get_account(self._session, data["parent_id"], for_update=True)
            if parent is None or not parent.is_active:
                raise ValidationFailedError(
                    "Choose an active parent account.",
                    errors=[FieldError("parent_id", "There is no active account with that id.", "invalid_parent")],
                )
            if parent.type != data["type"]:
                raise ValidationFailedError(
                    "A sub-account has the same type as its parent.",
                    errors=[FieldError("type", f"The parent is a {parent.type.value} account.", "type_mismatch")],
                )
        account = Account(**data)
        master_repository.add(self._session, account)
        if parent is not None and parent.is_postable:
            # Becoming a parent. (Pass 4 refuses this when the account already has postings.)
            parent.is_postable = False
            parent.updated_at = self._clock.now()
        self._audit.record(
            actor_id=actor.id,
            action="account.created",
            entity_type="account",
            entity_id=account.id,
            after=snapshot(account, FIELDS),
        )
        self._session.commit()
        return account

    def update(self, actor: Principal, account_id: int, expected_version: int, changes: dict[str, Any]) -> Account:
        account = self._locked(account_id)
        check_version(account, expected_version)
        if changes.get("is_postable") is True and master_repository.has_children(self._session, account.id):
            raise GuardFailedError(
                "An account with sub-accounts cannot be posted to.", code=ErrorCode.ACCOUNT_NOT_POSTABLE
            )
        before = snapshot(account, FIELDS)
        for name, value in changes.items():
            setattr(account, name, value)
        account.updated_at = self._clock.now()
        self._session.flush()
        self._finish(actor, account, "account.updated", before)
        return account

    def set_active(self, actor: Principal, account_id: int, *, active: bool) -> Account:
        account = self._locked(account_id)
        if account.is_active is active:
            return account
        if not active and master_repository.has_children(self._session, account.id, active_only=True):
            raise ConflictError("Deactivate its sub-accounts first.", code=ErrorCode.CONFLICT)
        before = snapshot(account, FIELDS)
        account.is_active = active
        account.updated_at = self._clock.now()
        self._session.flush()
        self._finish(actor, account, "account.activated" if active else "account.deactivated", before)
        return account

    def _locked(self, account_id: int) -> Account:
        account = master_repository.get_account(self._session, account_id, for_update=True)
        if account is None:
            raise NotFoundError("There is no such account.")
        return account

    def _finish(self, actor: Principal, account: Account, action: str, before: JsonDict) -> None:
        old, new = changed(before, snapshot(account, FIELDS))
        self._audit.record(
            actor_id=actor.id, action=action, entity_type="account", entity_id=account.id, before=old, after=new
        )
        self._session.commit()
