"""Categories, cost centres and projects (and products). The same small rules for each: create, rename, deactivate.
Inactive records stay readable, so old documents still show them."""

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.clock import Clock
from app.core.enums import AccountType, ProjectKind
from app.core.errors import ErrorCode, FieldError, GuardFailedError, NotFoundError, ValidationFailedError
from app.core.principal import Principal
from app.models.base import JsonDict
from app.models.master import Category, CostCenter, Project
from app.repositories import master as master_repository
from app.services.audit import AuditService
from app.services.master import changed, check_version, snapshot


class _MasterService:
    model: type[Any]
    entity: str
    label: str
    fields: tuple[str, ...]

    def __init__(self, session: Session, clock: Clock) -> None:
        self._session = session
        self._clock = clock
        self._audit = AuditService(session, clock)

    def get(self, row_id: int) -> Any:
        row = self._session.get(self.model, row_id)
        if row is None:
            raise NotFoundError(f"There is no such {self.label}.")
        return row

    def update(self, actor: Principal, row_id: int, expected_version: int, changes: dict[str, Any]) -> Any:
        row = self._locked(row_id)
        check_version(row, expected_version)
        self._check_changes(changes)
        before = snapshot(row, self.fields)
        for name, value in changes.items():
            setattr(row, name, value)
        row.updated_at = self._clock.now()
        self._session.flush()
        self._finish(actor, row, f"{self.entity}.updated", before)
        return row

    def set_active(self, actor: Principal, row_id: int, *, active: bool) -> Any:
        row = self._locked(row_id)
        if row.is_active is active:
            return row
        before = snapshot(row, self.fields)
        row.is_active = active
        row.updated_at = self._clock.now()
        self._session.flush()
        self._finish(actor, row, f"{self.entity}.{'activated' if active else 'deactivated'}", before)
        return row

    def _create(self, actor: Principal, row: Any) -> Any:
        master_repository.add(self._session, row)
        self._audit.record(
            actor_id=actor.id,
            action=f"{self.entity}.created",
            entity_type=self.entity,
            entity_id=row.id,
            after=snapshot(row, self.fields),
        )
        self._session.commit()
        return row

    def _check_changes(self, changes: dict[str, Any]) -> None:
        """Hook for rules a subclass adds to an update."""

    def _locked(self, row_id: int) -> Any:
        row = self._session.scalars(
            select(self.model)
            .where(self.model.id == row_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        ).one_or_none()
        if row is None:
            raise NotFoundError(f"There is no such {self.label}.")
        return row

    def _finish(self, actor: Principal, row: Any, action: str, before: JsonDict) -> None:
        old, new = changed(before, snapshot(row, self.fields))
        self._audit.record(
            actor_id=actor.id, action=action, entity_type=self.entity, entity_id=row.id, before=old, after=new
        )
        self._session.commit()


class CategoryService(_MasterService):
    model = Category
    entity = "category"
    label = "category"
    fields = ("name", "account_id", "is_active")

    def list_categories(
        self, *, q: str | None, is_active: bool | None, sort: str | None, limit: int, offset: int
    ) -> tuple[list[Category], int]:
        return master_repository.list_categories(
            self._session, q=q, is_active=is_active, sort=sort, limit=limit, offset=offset
        )

    def create(self, actor: Principal, data: dict[str, Any]) -> Category:
        self._require_expense_account(data["account_id"])
        return self._create(actor, Category(**data))  # type: ignore[no-any-return]

    def _check_changes(self, changes: dict[str, Any]) -> None:
        if "account_id" in changes:
            self._require_expense_account(changes["account_id"])

    def _require_expense_account(self, account_id: int) -> None:
        account = master_repository.get_account(self._session, account_id)
        problem = None
        if account is None or not account.is_active:
            problem = "Choose an active account."
        elif account.type is not AccountType.EXPENSE:
            problem = "A category posts to an expense account."
        elif not account.is_postable:
            raise GuardFailedError(
                "That account has sub-accounts and cannot be posted to. Choose one of them.",
                code=ErrorCode.ACCOUNT_NOT_POSTABLE,
                errors=[FieldError("account_id", "This is a parent account.", "not_postable")],
            )
        if problem:
            raise ValidationFailedError(problem, errors=[FieldError("account_id", problem, "invalid_account")])


class CostCenterService(_MasterService):
    model = CostCenter
    entity = "cost_center"
    label = "cost centre"
    fields = ("code", "name", "is_active")

    def list_cost_centers(
        self, *, q: str | None, is_active: bool | None, sort: str | None, limit: int, offset: int
    ) -> tuple[list[CostCenter], int]:
        return master_repository.list_cost_centers(
            self._session, q=q, is_active=is_active, sort=sort, limit=limit, offset=offset
        )

    def create(self, actor: Principal, data: dict[str, Any]) -> CostCenter:
        return self._create(actor, CostCenter(**data))  # type: ignore[no-any-return]


class ProjectService(_MasterService):
    model = Project
    entity = "project"
    label = "project or product"
    fields = ("code", "name", "kind", "is_active")

    def list_projects(
        self,
        *,
        q: str | None,
        kind: ProjectKind | None,
        is_active: bool | None,
        sort: str | None,
        limit: int,
        offset: int,
    ) -> tuple[list[Project], int]:
        return master_repository.list_projects(
            self._session, q=q, kind=kind, is_active=is_active, sort=sort, limit=limit, offset=offset
        )

    def create(self, actor: Principal, data: dict[str, Any]) -> Project:
        return self._create(actor, Project(**data))  # type: ignore[no-any-return]
