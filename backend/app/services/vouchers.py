"""Vouchers: the ledger.

A voucher is a set of lines, each an account and one side, that must balance to the paisa. It goes through the same
workflow as an expense or a purchase. Posting gives it its number, from the counter row, in the same transaction that
changes its status, and posts the expense or purchase it was generated from. Voiding never edits it: it creates a linked
reversing voucher with the sides swapped, both in one transaction.

Idempotency: post and void each take a client key. A repeated request with the same key returns the first result
instead of doing the work twice; the key is stored on the voucher under a unique index, so even two requests at the
same instant cannot both succeed."""

from collections.abc import Sequence
from datetime import date
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.config import Settings
from app.core.clock import Clock
from app.core.enums import (
    AllocationMethod,
    DocumentStatus,
    DocumentType,
    ExpenseType,
    PaymentMethod,
    PostingKey,
    VoucherType,
)
from app.core.errors import (
    ConflictError,
    ErrorCode,
    FieldError,
    ForbiddenError,
    GuardFailedError,
    NotFoundError,
    ValidationFailedError,
    VersionConflictError,
)
from app.core.ledger import (
    LedgerError,
    LineSpec,
    balance,
    expense_lines,
    offsetting_line,
    purchase_lines,
    reverse,
)
from app.core.mail import Outbox
from app.core.money import ZERO, to_paisa
from app.core.numbering import format_number, voucher_year
from app.core.principal import Principal
from app.core.transitions import start_posted
from app.models.base import JsonDict
from app.models.documents import DocumentEvent, Expense, Purchase
from app.models.master import Account, Category, CostCenter, Project
from app.models.vouchers import Voucher, VoucherLine
from app.repositories import documents as document_repository
from app.repositories import master as master_repository
from app.repositories import vouchers as voucher_repository
from app.services.audit import AuditService
from app.services.master import changed, snapshot
from app.services.notifications import MoveNotifier, summary_line
from app.services.workflow import Workflow, available_actions

FIELDS = ("voucher_type", "document_date", "description", "number", "status", "expense_id", "purchase_id")


class VoucherService:
    def __init__(self, session: Session, clock: Clock, settings: Settings, outbox: Outbox) -> None:
        self._session = session
        self._clock = clock
        self._settings = settings
        self._workflow = Workflow(session, clock)
        self._notifier = MoveNotifier(session, settings, outbox)
        self._audit = AuditService(session, clock)

    # Reading ---------------------------------------------------------------------------------------------------------

    def get(self, voucher_id: int) -> Voucher:
        voucher = voucher_repository.get_voucher(self._session, voucher_id)
        if voucher is None:
            raise NotFoundError("There is no such voucher.")
        return voucher

    def list_vouchers(
        self,
        *,
        voucher_type: VoucherType | None,
        status: DocumentStatus | None,
        date_from: date | None,
        date_to: date | None,
        q: str | None,
        sort: str | None,
        limit: int,
        offset: int,
    ) -> tuple[list[Voucher], int]:
        return voucher_repository.list_vouchers(
            self._session,
            voucher_type=voucher_type,
            status=status,
            date_from=date_from,
            date_to=date_to,
            q=q,
            sort=sort,
            limit=limit,
            offset=offset,
        )

    def history(self, voucher_id: int) -> list[DocumentEvent]:
        self.get(voucher_id)
        return document_repository.events_of(self._session, DocumentType.VOUCHER, voucher_id)

    def actions(self, actor: Principal, voucher: Voucher) -> list[str]:
        return available_actions(DocumentType.VOUCHER, voucher.status, voucher.created_by, actor)

    def check_balance(self, lines: list[dict[str, Any]]) -> tuple[Any, Any]:
        """Where lines stand and the one line that would balance them. Nothing is saved."""
        specs = [self._spec(line) for line in lines]
        return balance(specs), offsetting_line(specs)

    # Writing ---------------------------------------------------------------------------------------------------------

    def create(self, actor: Principal, data: dict[str, Any]) -> Voucher:
        specs = self._checked_lines(data["lines"])
        voucher = Voucher(
            voucher_type=data["voucher_type"],
            created_by=actor.id,
            document_date=data.get("document_date") or self._today(),
            description=data.get("description", ""),
            lines=[],
        )
        return self._save_new(actor, voucher, specs)

    def update(self, actor: Principal, voucher_id: int, expected_version: int, changes: dict[str, Any]) -> Voucher:
        voucher = self._locked(voucher_id)
        if voucher.created_by != actor.id:
            raise ForbiddenError("Only the author can change this voucher.")
        if voucher.status is not DocumentStatus.DRAFT:
            raise GuardFailedError("Only a draft can be changed.", code=ErrorCode.DOCUMENT_LOCKED)
        if voucher.version != expected_version:
            raise VersionConflictError("Someone else changed this record. Reload it and try again.")
        before = self._snapshot(voucher)
        voucher.updated_at = self._clock.now()
        for name in ("document_date", "description"):
            if changes.get(name) is not None:
                setattr(voucher, name, changes[name])
        if changes.get("lines") is not None:
            specs = self._checked_lines(changes["lines"])
            voucher.lines.clear()
            self._session.flush()
            self._add_lines(voucher, specs)
        self._session.flush()
        old, new = changed(before, self._snapshot(voucher))
        self._audit.record(
            actor_id=actor.id,
            action="voucher.updated",
            entity_type="voucher",
            entity_id=voucher.id,
            before=old,
            after=new,
        )
        self._session.commit()
        return self._reload(voucher.id)

    # The shared moves ------------------------------------------------------------------------------------------------

    def submit(self, actor: Principal, voucher_id: int, expected_version: int) -> Voucher:
        voucher = self._locked(voucher_id)
        if voucher.created_by != actor.id:
            raise ForbiddenError("Only the author can submit this voucher.")
        return self._move(actor, voucher, DocumentStatus.SUBMITTED, expected_version, problems=self._problems(voucher))

    def approve(self, actor: Principal, voucher_id: int, expected_version: int, comment: str | None) -> Voucher:
        return self._move(actor, self._locked(voucher_id), DocumentStatus.APPROVED, expected_version, comment)

    def reject(self, actor: Principal, voucher_id: int, expected_version: int, comment: str | None) -> Voucher:
        return self._move(actor, self._locked(voucher_id), DocumentStatus.REJECTED, expected_version, comment)

    def reopen(self, actor: Principal, voucher_id: int, expected_version: int) -> Voucher:
        return self._move(actor, self._locked(voucher_id), DocumentStatus.DRAFT, expected_version)

    # Post ------------------------------------------------------------------------------------------------------------

    def post(self, actor: Principal, voucher_id: int, expected_version: int, key: str) -> Voucher:
        """Number the voucher and post it, and post its source, in one transaction.

        A repeat of a request that already succeeded (same key, same voucher) returns the voucher as it is. The row is
        locked first; a request that arrives second waits, then re-reads what the first committed
        (`populate_existing`) and recognises its own key."""
        voucher = self._locked(voucher_id)
        if voucher.post_key == key and voucher.status in {DocumentStatus.POSTED, DocumentStatus.VOID}:
            return voucher
        other = voucher_repository.get_by_post_key(self._session, key)
        if other is not None and other.id != voucher.id:
            raise ConflictError(
                "That Idempotency-Key was used to post a different voucher.", code=ErrorCode.IDEMPOTENCY_KEY_REUSED
            )
        if voucher.status is not DocumentStatus.APPROVED:
            # Let the transition table give the right error (409 for a wrong status, 403 for a wrong role).
            return self._move(actor, voucher, DocumentStatus.POSTED, expected_version)
        year = voucher_year(voucher.document_date, self._year_start())
        closed = master_repository.closed_period_containing(self._session, voucher.document_date)
        balanced = balance(self._specs(voucher)).balanced
        source = self._lock_source(voucher)
        sequence = voucher_repository.next_sequence(self._session, voucher.voucher_type, year)
        # Everything that changes on the voucher is set before the first flush, so the database sees one UPDATE: status,
        # number, year, sequence and key together (it refuses a number without Posted, and Posted without a number).
        voucher.number = format_number(voucher.voucher_type, year, sequence)
        voucher.year, voucher.seq, voucher.post_key = year, sequence, key
        voucher.updated_at = self._clock.now()
        self._workflow.move(
            voucher,
            DocumentType.VOUCHER,
            actor,
            DocumentStatus.POSTED,
            expected_version=expected_version,
            balanced=balanced,
            period_open=closed is None,
        )
        if source is not None:
            document_type, document = source
            document.updated_at = self._clock.now()
            self._workflow.move(
                document, document_type, actor, DocumentStatus.POSTED, expected_version=document.version
            )
        self._session.commit()
        return self._reload(voucher.id)

    # Void ------------------------------------------------------------------------------------------------------------

    def void(
        self, actor: Principal, voucher_id: int, expected_version: int, reason: str, key: str
    ) -> tuple[Voucher, Voucher]:
        """Cancel a posted voucher by posting its mirror image, in one transaction. Returns (original, reversal).

        The original is never edited beyond its status and the void details. The reversal is dated today in the display
        zone, numbered from the same counter, born Posted, and linked to the original; the database allows one per
        voucher and never lets a reversal itself be voided. The source expense or purchase is not reopened."""
        voucher = self._locked(voucher_id)
        if voucher.void_key == key and voucher.status is DocumentStatus.VOID:
            return voucher, self._reversal_of(voucher)
        other = voucher_repository.get_by_void_key(self._session, key)
        if other is not None and other.id != voucher.id:
            raise ConflictError(
                "That Idempotency-Key was used to void a different voucher.", code=ErrorCode.IDEMPOTENCY_KEY_REUSED
            )
        today = self._today()
        closed = master_repository.closed_period_containing(self._session, today)
        year = voucher_year(today, self._year_start())
        original_specs = self._specs(voucher)
        mirror = reverse(original_specs, note=f"Reversal of {voucher.number}")
        number_given = voucher_repository.next_sequence(self._session, voucher.voucher_type, year)
        now = self._clock.now()
        voucher.void_reason, voucher.void_key = reason.strip(), key
        voucher.voided_at, voucher.voided_by, voucher.updated_at = now, actor.id, now
        self._workflow.move(
            voucher,
            DocumentType.VOUCHER,
            actor,
            DocumentStatus.VOID,
            expected_version=expected_version,
            reason=reason,
            period_open=closed is None,
            is_reversal=voucher.is_reversal,
        )
        reversal = Voucher(
            voucher_type=voucher.voucher_type,
            created_by=actor.id,
            document_date=today,
            description=f"Reversal of {voucher.number}: {reason.strip()}"[:1000],
            reversal_of_id=voucher.id,
            lines=[],
        )
        voucher_repository.add_voucher(self._session, reversal)
        self._add_lines(reversal, mirror)
        start_posted(reversal)
        reversal.number = format_number(reversal.voucher_type, year, number_given)
        reversal.year, reversal.seq = year, number_given
        self._session.flush()
        self._session.add(
            DocumentEvent(
                document_type=DocumentType.VOUCHER,
                document_id=reversal.id,
                action="reversed",
                from_status=None,
                to_status=DocumentStatus.POSTED,
                actor_id=actor.id,
                comment=f"Reversal of {voucher.number}",
                created_at=now,
            )
        )
        self._audit.record(
            actor_id=actor.id,
            action="voucher.reversal_created",
            entity_type="voucher",
            entity_id=reversal.id,
            after={"reversal_of": voucher.id, "number": reversal.number},
        )
        self._session.commit()
        return self._reload(voucher.id), self._reload(reversal.id)

    # Generation ------------------------------------------------------------------------------------------------------

    def generate_from_expense(self, actor: Principal, expense_id: int) -> Voucher:
        expense = document_repository.get_expense(self._session, expense_id, for_update=True)
        if expense is None:
            raise NotFoundError("There is no such expense.")
        self._require_ready_source(expense.status, voucher_repository.get_by_expense(self._session, expense.id))
        category = self._active_category(expense.category_id)
        accounts = self._posting_accounts()
        payment_key = PostingKey.CASH if expense.payment_method is PaymentMethod.CASH else PostingKey.BANK
        split: list[tuple[int, int]] | None = None
        if expense.expense_type is ExpenseType.INDIRECT:
            by_percentage = expense.allocation_method is AllocationMethod.PERCENTAGE
            # The weights that reproduce the approved split: basis points, or the fixed amounts in paisa.
            split = [
                (row.cost_center_id, (row.basis_points or 0) if by_percentage else to_paisa(row.amount))
                for row in expense.allocations
            ]
        try:
            specs = expense_lines(
                amount=expense.amount,
                tax_amount=expense.tax_amount,
                expense_account_id=category.account_id,
                input_tax_account_id=self._needed(accounts, PostingKey.INPUT_SALES_TAX, expense.tax_amount > 0),
                payment_account_id=self._needed(accounts, payment_key),
                project_id=expense.project_id,
                cost_center_id=expense.cost_center_id,
                split=split,
                description=expense.description or f"Expense {expense.id}",
            )
        except LedgerError as exc:
            raise ValidationFailedError(str(exc).capitalize() + ".") from exc
        voucher = Voucher(
            voucher_type=VoucherType.PAYMENT,
            created_by=actor.id,
            document_date=self._today(),
            description=(expense.description or f"Expense {expense.id}")[:1000],
            expense_id=expense.id,
            lines=[],
        )
        return self._save_new(actor, voucher, specs, action="voucher.generated")

    def generate_from_purchase(
        self, actor: Principal, purchase_id: int, category_id: int, payment_method: PaymentMethod
    ) -> Voucher:
        purchase = document_repository.get_purchase(self._session, purchase_id, for_update=True)
        if purchase is None:
            raise NotFoundError("There is no such purchase.")
        self._require_ready_source(purchase.status, voucher_repository.get_by_purchase(self._session, purchase.id))
        category = self._active_category(category_id)
        accounts = self._posting_accounts()
        payment_key = PostingKey.CASH if payment_method is PaymentMethod.CASH else PostingKey.BANK
        label = f"Purchase {purchase.invoice_number or purchase.id} from {purchase.vendor.name}"
        specs = purchase_lines(
            subtotal=purchase.subtotal,
            sales_tax=purchase.sales_tax_total,
            payable=purchase.payable,
            sales_tax_withheld=purchase.sales_tax_withheld,
            income_tax_withheld=purchase.income_tax_withheld,
            expense_account_id=category.account_id,
            input_tax_account_id=self._needed(accounts, PostingKey.INPUT_SALES_TAX, purchase.sales_tax_total > 0),
            payment_account_id=self._needed(accounts, payment_key, purchase.payable > 0),
            sales_tax_withheld_account_id=self._needed(
                accounts, PostingKey.SALES_TAX_WITHHELD, purchase.sales_tax_withheld > 0
            ),
            income_tax_withheld_account_id=self._needed(
                accounts, PostingKey.INCOME_TAX_WITHHELD, purchase.income_tax_withheld > 0
            ),
            description=label,
        )
        voucher = Voucher(
            voucher_type=VoucherType.PAYMENT,
            created_by=actor.id,
            document_date=self._today(),
            description=label[:1000],
            purchase_id=purchase.id,
            lines=[],
        )
        return self._save_new(actor, voucher, specs, action="voucher.generated")

    # -----------------------------------------------------------------------------------------------------------------

    def _move(
        self,
        actor: Principal,
        voucher: Voucher,
        target: DocumentStatus,
        expected_version: int,
        comment: str | None = None,
        problems: Sequence[FieldError] = (),
    ) -> Voucher:
        # Look things up first: a query after the next assignment would flush it early and step the version, and the
        # engine would then see a version the client never held.
        closed = master_repository.closed_period_containing(self._session, voucher.document_date)
        balanced = balance(self._specs(voucher)).balanced
        audience = self._notifier.audience(target, voucher.created_by)
        voucher.updated_at = self._clock.now()
        self._workflow.move(
            voucher,
            DocumentType.VOUCHER,
            actor,
            target,
            expected_version=expected_version,
            comment=comment,
            problems=problems,
            balanced=balanced,
            period_open=closed is None,
            is_reversal=voucher.is_reversal,
        )
        self._notifier.announce(
            audience,
            document_type=DocumentType.VOUCHER,
            document_id=voucher.id,
            summary=summary_line(sum((line.debit for line in voucher.lines), ZERO), voucher.description),
            actor=actor,
            target=target,
            comment=comment,
            when=voucher.updated_at,
        )
        self._session.commit()
        return self._reload(voucher.id)

    def _problems(self, voucher: Voucher) -> list[FieldError]:
        problems: list[FieldError] = []
        if len(voucher.lines) < 2:
            problems.append(FieldError("lines", "A voucher needs at least two lines.", "required"))
        if not voucher.description.strip():
            problems.append(FieldError("description", "Add a narration saying what this voucher is for.", "required"))
        return problems

    def _year_start(self) -> int:
        """The month the numbering year starts in, as the Accountant set it."""
        return master_repository.get_accounting_settings(self._session).fiscal_year_start_month

    def _locked(self, voucher_id: int) -> Voucher:
        voucher = voucher_repository.get_voucher(self._session, voucher_id, for_update=True)
        if voucher is None:
            raise NotFoundError("There is no such voucher.")
        return voucher

    def _reload(self, voucher_id: int) -> Voucher:
        voucher = voucher_repository.get_voucher(self._session, voucher_id, refresh=True)
        assert voucher is not None
        return voucher

    def _reversal_of(self, voucher: Voucher) -> Voucher:
        reversal = voucher_repository.get_reversal_of(self._session, voucher.id)
        assert reversal is not None
        return self._reload(reversal.id)

    def _today(self) -> date:
        return self._clock.today(ZoneInfo(self._settings.display_timezone))

    @staticmethod
    def _spec(line: dict[str, Any]) -> LineSpec:
        return LineSpec(
            account_id=line["account_id"],
            debit=line.get("debit", ZERO),  # absent when a PATCH leaves the default: an update dumps only what was sent
            credit=line.get("credit", ZERO),
            description=line.get("description"),
            cost_center_id=line.get("cost_center_id"),
            project_id=line.get("project_id"),
        )

    @staticmethod
    def _specs(voucher: Voucher) -> list[LineSpec]:
        return [
            LineSpec(
                account_id=line.account_id,
                debit=line.debit,
                credit=line.credit,
                description=line.description,
                cost_center_id=line.cost_center_id,
                project_id=line.project_id,
            )
            for line in voucher.lines
        ]

    def _checked_lines(self, lines: list[dict[str, Any]]) -> list[LineSpec]:
        """Lines for a draft: every account postable and active, every cost centre and project active, and balanced.
        A draft cannot be saved unbalanced (the database refuses it at commit); the editor keeps unsaved lines
        itself."""
        errors: list[FieldError] = []
        for index, line in enumerate(lines):
            account = self._session.get(Account, line["account_id"])
            if account is None or not account.is_active:
                errors.append(
                    FieldError(f"lines.{index}.account_id", "Choose an active account.", "inactive_reference")
                )
            elif not account.is_postable:
                errors.append(
                    FieldError(
                        f"lines.{index}.account_id", "This is a parent account; choose a sub-account.", "not_postable"
                    )
                )
            if line.get("cost_center_id") is not None:
                centre = self._session.get(CostCenter, line["cost_center_id"])
                if centre is None or not centre.is_active:
                    errors.append(
                        FieldError(
                            f"lines.{index}.cost_center_id", "Choose an active cost centre.", "inactive_reference"
                        )
                    )
            if line.get("project_id") is not None:
                project = self._session.get(Project, line["project_id"])
                if project is None or not project.is_active:
                    errors.append(
                        FieldError(f"lines.{index}.project_id", "Choose an active project.", "inactive_reference")
                    )
        if errors:
            raise ValidationFailedError("Some lines cannot be used.", errors=errors)
        specs = [self._spec(line) for line in lines]
        totals = balance(specs)
        if not totals.balanced:
            fix = offsetting_line(specs)
            assert fix is not None
            raise GuardFailedError(
                f"Debits {totals.debit} and credits {totals.credit} differ by {abs(totals.difference)}. "
                f"A {fix[0]} of {fix[1]} would balance them.",
                code=ErrorCode.VOUCHER_UNBALANCED,
                errors=[FieldError("lines", f"Add a {fix[0]} of {fix[1]}.", "unbalanced")],
            )
        return specs

    def _add_lines(self, voucher: Voucher, specs: Sequence[LineSpec]) -> None:
        for number, spec in enumerate(specs, start=1):
            voucher.lines.append(
                VoucherLine(
                    line_no=number,
                    account_id=spec.account_id,
                    debit=spec.debit,
                    credit=spec.credit,
                    description=spec.description,
                    cost_center_id=spec.cost_center_id,
                    project_id=spec.project_id,
                )
            )
        self._session.flush()

    def _save_new(
        self, actor: Principal, voucher: Voucher, specs: Sequence[LineSpec], action: str = "voucher.created"
    ) -> Voucher:
        voucher_repository.add_voucher(self._session, voucher)
        self._add_lines(voucher, specs)
        self._workflow.record_creation(voucher, DocumentType.VOUCHER, actor)
        self._audit.record(
            actor_id=actor.id,
            action=action,
            entity_type="voucher",
            entity_id=voucher.id,
            after=self._snapshot(voucher),
        )
        self._session.commit()
        return self._reload(voucher.id)

    def _snapshot(self, voucher: Voucher) -> JsonDict:
        values = snapshot(voucher, FIELDS)
        values["lines"] = [
            {"account_id": ln.account_id, "debit": str(ln.debit), "credit": str(ln.credit)} for ln in voucher.lines
        ]
        return values

    def _lock_source(self, voucher: Voucher) -> tuple[DocumentType, Expense | Purchase] | None:
        """The expense or purchase this voucher was generated from, locked, so it can be posted with the voucher."""
        if voucher.expense_id is not None:
            expense = document_repository.get_expense(self._session, voucher.expense_id, for_update=True)
            assert expense is not None
            return DocumentType.EXPENSE, expense
        if voucher.purchase_id is not None:
            purchase = document_repository.get_purchase(self._session, voucher.purchase_id, for_update=True)
            assert purchase is not None
            return DocumentType.PURCHASE, purchase
        return None

    @staticmethod
    def _require_ready_source(status: DocumentStatus, existing: Voucher | None) -> None:
        if status is not DocumentStatus.APPROVED:
            raise GuardFailedError(
                "Only an approved document can be turned into a voucher.", code=ErrorCode.SOURCE_NOT_APPROVED
            )
        if existing is not None:
            raise GuardFailedError(
                f"A voucher was already generated from this document (id {existing.id}).",
                code=ErrorCode.ALREADY_GENERATED,
            )

    def _active_category(self, category_id: int) -> Category:
        category = self._session.get(Category, category_id)
        if category is None or not category.is_active:
            raise ValidationFailedError(
                "Choose an active category.",
                errors=[FieldError("category_id", "That category is not available.", "inactive_reference")],
            )
        return category

    def _posting_accounts(self) -> dict[PostingKey, int]:
        return {row.key: row.account_id for row in master_repository.list_posting_accounts(self._session)}

    @staticmethod
    def _needed(accounts: dict[PostingKey, int], key: PostingKey, required: bool = True) -> int:
        """The account for a posting key. Where the line will not exist (no tax), a missing key is not an error."""
        if key in accounts:
            return accounts[key]
        if not required:
            return 0
        raise GuardFailedError(
            f"The posting account '{key.value}' is not set. An Admin sets it under posting accounts.",
            code=ErrorCode.POSTING_ACCOUNT_MISSING,
        )
