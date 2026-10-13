"""Expenses: direct (attributed to a project, product or cost centre) and indirect (split across cost centres).

Staff create and see only their own; everyone else with access sees all. Only the author edits a draft. An approved
split is exact: percentages are basis points that total 10,000, and the amounts are worked out once by the
largest-remainder rule so they add up to the paisa."""

from datetime import date
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.config import Settings
from app.core.allocation import Share, allocate_by_percentage
from app.core.clock import Clock
from app.core.duplicates import DuplicateWarning
from app.core.enums import AllocationMethod, DocumentStatus, DocumentType, ExpenseType, Role
from app.core.errors import (
    ErrorCode,
    FieldError,
    ForbiddenError,
    GuardFailedError,
    NotFoundError,
    ValidationFailedError,
    VersionConflictError,
)
from app.core.mail import Outbox
from app.core.money import ZERO, percent_of
from app.core.principal import Principal
from app.models.base import JsonDict
from app.models.documents import DocumentEvent, Expense, ExpenseAllocation
from app.models.master import Category, CostCenter, Project
from app.repositories import documents as document_repository
from app.services.audit import AuditService
from app.services.duplicates import DuplicateFinder
from app.services.master import changed, snapshot
from app.services.notifications import MoveNotifier, summary_line
from app.services.workflow import Workflow, available_actions

FIELDS = (
    "expense_type",
    "document_date",
    "category_id",
    "amount",
    "tax_amount",
    "payment_method",
    "description",
    "project_id",
    "cost_center_id",
    "allocation_method",
)
EDITABLE = {"expense_type", "document_date", "category_id", "amount", "tax_amount", "payment_method", "description"}


def mismatch(message: str) -> GuardFailedError:
    return GuardFailedError(
        message, code=ErrorCode.ALLOCATION_MISMATCH, errors=[FieldError("allocation", message, "allocation_mismatch")]
    )


class ExpenseService:
    def __init__(self, session: Session, clock: Clock, settings: Settings, outbox: Outbox) -> None:
        self._session = session
        self._clock = clock
        self._settings = settings
        self._workflow = Workflow(session, clock)
        self._notifier = MoveNotifier(session, settings, outbox)
        self._audit = AuditService(session, clock)

    # Reading ---------------------------------------------------------------------------------------------------------

    def get(self, actor: Principal, expense_id: int) -> Expense:
        expense = document_repository.get_expense(self._session, expense_id)
        return self._visible(actor, expense)

    def list_expenses(
        self,
        actor: Principal,
        *,
        mine: bool,
        status: DocumentStatus | None,
        expense_type: ExpenseType | None,
        category_id: int | None,
        date_from: date | None,
        date_to: date | None,
        amount_min: Decimal | None,
        amount_max: Decimal | None,
        q: str | None,
        sort: str | None,
        limit: int,
        offset: int,
    ) -> tuple[list[Expense], int]:
        # Staff see only their own, whatever they ask for.
        only = actor.id if (mine or actor.role is Role.STAFF) else None
        return document_repository.list_expenses(
            self._session,
            only_created_by=only,
            status=status,
            expense_type=expense_type,
            category_id=category_id,
            date_from=date_from,
            date_to=date_to,
            amount_min=amount_min,
            amount_max=amount_max,
            q=q,
            sort=sort,
            limit=limit,
            offset=offset,
        )

    def duplicates(self, actor: Principal, expense_id: int) -> list[DuplicateWarning]:
        """Other expenses that look like this one. Staff are shown only their own."""
        expense = self.get(actor, expense_id)
        only_author = actor.id if actor.role is Role.STAFF else None
        return DuplicateFinder(self._session).for_expense(expense, only_author=only_author)

    def history(self, actor: Principal, expense_id: int) -> list[DocumentEvent]:
        self.get(actor, expense_id)
        return document_repository.events_of(self._session, DocumentType.EXPENSE, expense_id)

    def actions(self, actor: Principal, expense: Expense) -> list[str]:
        return available_actions(DocumentType.EXPENSE, expense.status, expense.created_by, actor)

    def preview(self, amount: Decimal, allocation: dict[str, Any]) -> dict[str, Any]:
        """What a split comes to as typed. It reports a shortfall rather than failing."""
        method: AllocationMethod = allocation["method"]
        lines = allocation["lines"]
        if method is AllocationMethod.PERCENTAGE:
            given = sum(line["basis_points"] for line in lines)
            if given == 10_000:
                shares = allocate_by_percentage(amount, [(ln["cost_center_id"], ln["basis_points"]) for ln in lines])
                amounts = {share.bucket_id: share.amount for share in shares}
            else:
                amounts = {ln["cost_center_id"]: percent_of(amount, ln["basis_points"]) for ln in lines}
            rows = [
                {
                    "cost_center_id": ln["cost_center_id"],
                    "basis_points": ln["basis_points"],
                    "amount": amounts[ln["cost_center_id"]],
                }
                for ln in lines
            ]
            remaining_bp: int | None = 10_000 - given
        else:
            rows = [
                {"cost_center_id": ln["cost_center_id"], "basis_points": None, "amount": ln["amount"]} for ln in lines
            ]
            remaining_bp = None
        allocated = sum((row["amount"] for row in rows), ZERO)
        centres = {c.id: c.code for c in self._cost_centres([row["cost_center_id"] for row in rows])}
        for row in rows:
            row["cost_center_code"] = centres.get(row["cost_center_id"], "")
        remaining = amount - allocated
        return {
            "complete": remaining == 0 and (remaining_bp in (None, 0)),
            "lines": rows,
            "allocated": allocated,
            "remaining": remaining,
            "remaining_basis_points": remaining_bp,
        }

    # Writing ---------------------------------------------------------------------------------------------------------

    def create(self, actor: Principal, data: dict[str, Any]) -> Expense:
        allocation = data.pop("allocation", None)
        document_date = data.pop("document_date", None) or self._today()
        expense_type: ExpenseType = data["expense_type"]
        self._require_category(data["category_id"])
        self._require_tax_within_amount(data["amount"], data["tax_amount"])
        if expense_type is ExpenseType.DIRECT:
            self._require_attribution(data.get("project_id"), data.get("cost_center_id"))
            if allocation is not None:
                raise ValidationFailedError(
                    "A direct expense is not split.",
                    errors=[FieldError("allocation", "Only an indirect expense has an allocation.", "not_indirect")],
                )
        elif data.get("project_id") is not None or data.get("cost_center_id") is not None:
            raise ValidationFailedError(
                "An indirect expense is split across cost centres, not attributed.",
                errors=[FieldError("cost_center_id", "Remove this and use the allocation instead.", "indirect")],
            )
        expense = Expense(created_by=actor.id, document_date=document_date, allocations=[], **data)
        document_repository.add_expense(self._session, expense)
        if allocation is not None:
            method, rows = self._build_allocation(expense.amount, allocation)
            expense.allocation_method = method
            self._set_allocations(expense, rows)
        self._workflow.record_creation(expense, DocumentType.EXPENSE, actor)
        self._audit.record(
            actor_id=actor.id,
            action="expense.created",
            entity_type="expense",
            entity_id=expense.id,
            after=self._snapshot(expense),
        )
        self._session.commit()
        return self._reload(expense.id)

    def update(self, actor: Principal, expense_id: int, expected_version: int, changes: dict[str, Any]) -> Expense:
        expense = self._locked(actor, expense_id)
        self._require_editable(actor, expense, expected_version)
        before = self._snapshot(expense)
        expense.updated_at = self._clock.now()  # written together with the changes below
        allocation = changes.pop("allocation", None)
        explicit_attribution = {k for k in ("project_id", "cost_center_id") if k in changes}
        old_amount = expense.amount
        new_amount = changes.get("amount", old_amount)
        new_tax = changes.get("tax_amount", expense.tax_amount)
        if "category_id" in changes:
            self._require_category(changes["category_id"])
        self._require_tax_within_amount(new_amount, new_tax)

        new_type = changes.get("expense_type", expense.expense_type)
        switching = new_type is not expense.expense_type
        for name in EDITABLE & changes.keys():
            setattr(expense, name, changes[name])

        if new_type is ExpenseType.DIRECT:
            project = changes.get("project_id", None if switching else expense.project_id)
            centre = changes.get("cost_center_id", None if switching else expense.cost_center_id)
            self._require_attribution(project, centre)
            if allocation is not None:
                raise ValidationFailedError(
                    "A direct expense is not split.",
                    errors=[FieldError("allocation", "Only an indirect expense has an allocation.", "not_indirect")],
                )
            expense.project_id, expense.cost_center_id = project, centre
            if expense.allocations or expense.allocation_method:
                expense.allocation_method = None  # first: a direct expense may not keep a method while rows are removed
                self._set_allocations(expense, [])  # and it carries no split
        else:
            if any(changes.get(k) is not None for k in explicit_attribution):
                raise ValidationFailedError(
                    "An indirect expense is split across cost centres, not attributed.",
                    errors=[FieldError("cost_center_id", "Remove this and use the allocation instead.", "indirect")],
                )
            expense.project_id = expense.cost_center_id = None
            if allocation is not None:
                method, rows = self._build_allocation(new_amount, allocation)
                expense.allocation_method = method
                self._set_allocations(expense, rows)
            elif expense.allocations and new_amount != old_amount:
                self._reprice_allocations(expense, new_amount)
        self._session.flush()
        old, new = changed(before, self._snapshot(expense))
        self._audit.record(
            actor_id=actor.id,
            action="expense.updated",
            entity_type="expense",
            entity_id=expense.id,
            before=old,
            after=new,
        )
        self._session.commit()
        return self._reload(expense.id)

    # Moves -----------------------------------------------------------------------------------------------------------

    def submit(self, actor: Principal, expense_id: int, expected_version: int) -> Expense:
        expense = self._locked(actor, expense_id)
        if expense.created_by != actor.id:
            raise ForbiddenError("Only the author can submit this expense.")
        return self._move(actor, expense, DocumentStatus.SUBMITTED, expected_version, problems=self._problems(expense))

    def approve(self, actor: Principal, expense_id: int, expected_version: int, comment: str | None) -> Expense:
        return self._move(actor, self._locked(actor, expense_id), DocumentStatus.APPROVED, expected_version, comment)

    def reject(self, actor: Principal, expense_id: int, expected_version: int, comment: str | None) -> Expense:
        return self._move(actor, self._locked(actor, expense_id), DocumentStatus.REJECTED, expected_version, comment)

    def reopen(self, actor: Principal, expense_id: int, expected_version: int) -> Expense:
        return self._move(actor, self._locked(actor, expense_id), DocumentStatus.DRAFT, expected_version)

    # -----------------------------------------------------------------------------------------------------------------

    def _move(
        self,
        actor: Principal,
        expense: Expense,
        target: DocumentStatus,
        expected_version: int,
        comment: str | None = None,
        problems: list[FieldError] | None = None,
    ) -> Expense:
        audience = self._notifier.audience(target, expense.created_by)
        expense.updated_at = self._clock.now()
        self._workflow.move(
            expense,
            DocumentType.EXPENSE,
            actor,
            target,
            expected_version=expected_version,
            comment=comment,
            problems=problems or [],
        )
        self._notifier.announce(
            audience,
            document_type=DocumentType.EXPENSE,
            document_id=expense.id,
            summary=summary_line(expense.amount, expense.description),
            actor=actor,
            target=target,
            comment=comment,
            when=expense.updated_at,
        )
        self._session.commit()
        return self._reload(expense.id)

    def _problems(self, expense: Expense) -> list[FieldError]:
        problems: list[FieldError] = []
        if not expense.description.strip():
            problems.append(FieldError("description", "Say what this was for.", "required"))
        if expense.expense_type is ExpenseType.INDIRECT and (
            not expense.allocations or expense.allocation_method is None
        ):
            problems.append(FieldError("allocation", "Split this expense across cost centres.", "required"))
        return problems

    def _visible(self, actor: Principal, expense: Expense | None) -> Expense:
        """Staff asking for someone else's expense are told it does not exist, so its existence is not leaked."""
        if expense is None or (actor.role is Role.STAFF and expense.created_by != actor.id):
            raise NotFoundError("There is no such expense.")
        return expense

    def _locked(self, actor: Principal, expense_id: int) -> Expense:
        return self._visible(actor, document_repository.get_expense(self._session, expense_id, for_update=True))

    def _reload(self, expense_id: int) -> Expense:
        """The expense as the screen needs it: parents and split loaded, nothing stale."""
        expense = document_repository.get_expense(self._session, expense_id, refresh=True)
        assert expense is not None
        return expense

    def _require_editable(self, actor: Principal, expense: Expense, expected_version: int) -> None:
        if expense.created_by != actor.id:
            raise ForbiddenError("Only the author can change this expense.")
        if expense.status is not DocumentStatus.DRAFT:
            raise GuardFailedError("Only a draft can be changed.", code=ErrorCode.DOCUMENT_LOCKED)
        if expense.version != expected_version:
            raise VersionConflictError("Someone else changed this record. Reload it and try again.")

    def _today(self) -> date:
        return self._clock.today(ZoneInfo(self._settings.display_timezone))

    def _snapshot(self, expense: Expense) -> JsonDict:
        values = snapshot(expense, FIELDS)
        values["amount"] = str(expense.amount)
        values["tax_amount"] = str(expense.tax_amount)
        values["allocations"] = [
            {"cost_center_id": row.cost_center_id, "basis_points": row.basis_points, "amount": str(row.amount)}
            for row in expense.allocations
        ]
        return values

    def _require_category(self, category_id: int) -> None:
        category = self._session.get(Category, category_id)
        if category is None or not category.is_active:
            raise ValidationFailedError(
                "Choose an active category.",
                errors=[FieldError("category_id", "That category is not available.", "inactive_reference")],
            )

    @staticmethod
    def _require_tax_within_amount(amount: Decimal, tax: Decimal) -> None:
        if tax < 0 or tax > amount:
            raise ValidationFailedError(
                "The tax cannot be more than the amount.",
                errors=[FieldError("tax_amount", "Tax is part of the amount, so it cannot exceed it.", "too_large")],
            )

    def _require_attribution(self, project_id: int | None, cost_center_id: int | None) -> None:
        if project_id is None and cost_center_id is None:
            raise ValidationFailedError(
                "A direct expense needs a project, product or cost centre.",
                errors=[FieldError("project_id", "Choose where this spending went.", "required")],
            )
        if project_id is not None:
            project = self._session.get(Project, project_id)
            if project is None or not project.is_active:
                raise ValidationFailedError(
                    "Choose an active project or product.",
                    errors=[
                        FieldError("project_id", "That project or product is not available.", "inactive_reference")
                    ],
                )
        if cost_center_id is not None:
            self._require_cost_centres([cost_center_id])

    def _cost_centres(self, ids: list[int]) -> list[CostCenter]:
        return [c for c in (self._session.get(CostCenter, i) for i in ids) if c is not None]

    def _require_cost_centres(self, ids: list[int], *, prefix: str | None = None) -> None:
        """Every id must be an active cost centre. The error names the offending line of a split, or the field."""
        found = {c.id: c for c in self._cost_centres(ids)}
        for index, cost_center_id in enumerate(ids):
            centre = found.get(cost_center_id)
            if centre is None or not centre.is_active:
                field = "cost_center_id" if prefix is None else f"{prefix}.{index}.cost_center_id"
                raise ValidationFailedError(
                    "Choose active cost centres.",
                    errors=[FieldError(field, "That cost centre is not available.", "inactive_reference")],
                )

    def _build_allocation(
        self, amount: Decimal, allocation: dict[str, Any]
    ) -> tuple[AllocationMethod, list[tuple[int, int | None, Decimal]]]:
        """The rows of a split: (cost centre, basis points or None, exact amount). A split that does not add up is
        refused, not rounded into shape."""
        method: AllocationMethod = allocation["method"]
        lines = allocation["lines"]
        self._require_cost_centres([ln["cost_center_id"] for ln in lines], prefix="allocation.lines")
        if method is AllocationMethod.PERCENTAGE:
            given = sum(ln["basis_points"] for ln in lines)
            if given != 10_000:
                raise mismatch(f"The percentages total {given} of 10,000 basis points; they must total exactly 10,000.")
            shares: list[Share] = allocate_by_percentage(
                amount, [(ln["cost_center_id"], ln["basis_points"]) for ln in lines]
            )
            by_centre = {share.bucket_id: share.amount for share in shares}
            return method, [(ln["cost_center_id"], ln["basis_points"], by_centre[ln["cost_center_id"]]) for ln in lines]
        total = sum((ln["amount"] for ln in lines), ZERO)
        if total != amount:
            raise mismatch(f"The amounts total {total} but the expense is {amount}; they must match exactly.")
        return method, [(ln["cost_center_id"], None, ln["amount"]) for ln in lines]

    def _set_allocations(self, expense: Expense, rows: list[tuple[int, int | None, Decimal]]) -> None:
        expense.allocations.clear()
        self._session.flush()  # remove the old rows first, so a cost centre kept in the new split cannot clash
        for cost_center_id, basis_points, amount in rows:
            expense.allocations.append(
                ExpenseAllocation(cost_center_id=cost_center_id, basis_points=basis_points, amount=amount)
            )
        self._session.flush()

    def _reprice_allocations(self, expense: Expense, new_amount: Decimal) -> None:
        """The amount changed on an existing split. A percentage split is worked out again from its basis points;
        a fixed split cannot be, so the caller must send new amounts."""
        if expense.allocation_method is AllocationMethod.PERCENTAGE:
            shares = allocate_by_percentage(
                new_amount, [(row.cost_center_id, row.basis_points or 0) for row in expense.allocations]
            )
            by_centre = {share.bucket_id: share.amount for share in shares}
            for row in expense.allocations:
                row.amount = by_centre[row.cost_center_id]
            self._session.flush()
            return
        raise mismatch("The amount changed, so send the fixed amounts again; they must total the new amount.")
