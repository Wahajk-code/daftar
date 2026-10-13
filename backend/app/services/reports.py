"""Reports and their CSV exports. Read only, except that an export is rate limited and audited (with its filter and row
count) in its own transaction, before any byte is sent."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import Row, select
from sqlalchemy.orm import Session

from app.config import Settings
from app.core.clock import Clock
from app.core.csv_export import amount_cell, text_cell
from app.core.enums import DocumentStatus, ExpenseType, VoucherType
from app.core.errors import FieldError, ValidationFailedError
from app.core.money import ZERO
from app.core.principal import Principal
from app.core.rate_limit import RateLimiter
from app.core.visibility import drafts_hidden_from
from app.models.documents import Expense
from app.models.master import CostCenter, Project
from app.repositories import documents as document_repository
from app.repositories import reports as report_repository
from app.schemas.reports import (
    ActivityReport,
    ActivityRow,
    ExpenseReport,
    ExpenseReportRow,
    ExpenseReportTotals,
    Overview,
    OverviewMonth,
    PurchaseReport,
    PurchaseReportRow,
    PurchaseReportTotals,
    ReportScope,
    StatusCount,
    VoucherRegisterRow,
)
from app.services.audit import AuditService

S = DocumentStatus
# Money that has been decided: an approved expense is committed spend even before its voucher is posted.
DEFAULT_SPEND_STATUSES = (S.APPROVED, S.POSTED)
# The most documents one export holds; a filter that matches more is narrowed by the person, never cut silently.
EXPORT_ROW_LIMIT = 10_000
# The register is the books: numbered vouchers, a void one stays on it beside its reversal.
DEFAULT_REGISTER_STATUSES = (S.POSTED, S.VOID)


@dataclass(frozen=True)
class CsvFile:
    filename: str
    header: list[str]
    rows: list[list[str]]


class ReportService:
    def __init__(self, session: Session, clock: Clock, settings: Settings, limiter: RateLimiter) -> None:
        self._session = session
        self._clock = clock
        self._settings = settings
        self._limiter = limiter
        self._audit = AuditService(session, clock)

    # Reports ---------------------------------------------------------------------------------------------------------

    def expenses(
        self,
        statuses: Sequence[S] | None,
        date_from: date | None,
        date_to: date | None,
        actor: Principal | None = None,
    ) -> ExpenseReport:
        scope = self._scope(self._statuses(actor, statuses, DEFAULT_SPEND_STATUSES), date_from, date_to)
        rows = report_repository.expenses_by_type_and_cost_centre(self._session, scope.statuses, date_from, date_to)
        count, amount, tax = report_repository.expense_totals(self._session, scope.statuses, date_from, date_to)
        return ExpenseReport(
            scope=scope,
            rows=[ExpenseReportRow.model_validate(row) for row in rows],
            totals=ExpenseReportTotals(expenses=count, amount=amount, tax_amount=tax),
        )

    def purchases(
        self,
        statuses: Sequence[S] | None,
        date_from: date | None,
        date_to: date | None,
        registered: bool | None,
        actor: Principal | None = None,
    ) -> PurchaseReport:
        scope = self._scope(self._statuses(actor, statuses, DEFAULT_SPEND_STATUSES), date_from, date_to)
        found = report_repository.purchases_by_vendor(self._session, scope.statuses, date_from, date_to, registered)
        rows = [PurchaseReportRow.model_validate(row) for row in found]
        return PurchaseReport(
            scope=scope,
            rows=rows,
            registered=self._totals([r for r in rows if r.registered]),
            unregistered=self._totals([r for r in rows if not r.registered]),
            totals=self._totals(rows),
        )

    def register(
        self,
        statuses: Sequence[S] | None,
        date_from: date | None,
        date_to: date | None,
        voucher_type: VoucherType | None,
        *,
        limit: int,
        offset: int,
        actor: Principal | None = None,
    ) -> tuple[list[VoucherRegisterRow], int]:
        scope = self._scope(self._statuses(actor, statuses, DEFAULT_REGISTER_STATUSES), date_from, date_to)
        rows, total = report_repository.voucher_register(
            self._session, scope.statuses, date_from, date_to, voucher_type, limit=limit, offset=offset
        )
        return [VoucherRegisterRow.model_validate(row) for row in rows], total

    def activity(self, date_from: date | None, date_to: date | None) -> ActivityReport:
        """Who did what in the period, for a manager keeping an eye on how the work is going."""
        self._scope(DEFAULT_SPEND_STATUSES, date_from, date_to)  # only to check the range
        zone = ZoneInfo(self._settings.display_timezone)
        start = None if date_from is None else datetime.combine(date_from, time.min, tzinfo=zone)
        end = None if date_to is None else datetime.combine(date_to + timedelta(days=1), time.min, tzinfo=zone)
        done = report_repository.actions_by_person(self._session, start, end)
        rejected = report_repository.rejections_received(self._session, start, end)

        def count(person: int, action: str, kind: str | None = None) -> int:
            if kind is not None:
                return done.get((person, action, kind), 0)
            return sum(n for (who, what, _kind), n in done.items() if who == person and what == action)

        rows = [
            ActivityRow(
                user_id=person.id,
                full_name=person.full_name,
                role=person.role,
                expenses_created=count(person.id, "created", "expense"),
                purchases_created=count(person.id, "created", "purchase"),
                vouchers_created=count(person.id, "created", "voucher"),
                submitted=count(person.id, "submitted"),
                rejected_received=rejected.get(person.id, 0),
                approved=count(person.id, "approved"),
                rejected_given=count(person.id, "rejected"),
                posted=count(person.id, "posted", "voucher"),
                voided=count(person.id, "voided", "voucher"),
            )
            for person in report_repository.people(self._session)
        ]
        return ActivityReport(date_from=date_from, date_to=date_to, rows=rows)

    def overview(self, months: int, actor: Principal | None = None) -> Overview:
        """A run of months ending with the current one (in the display zone), and the spread over statuses."""
        today = self._clock.today(ZoneInfo(self._settings.display_timezone))
        year, month = today.year, today.month
        labels: list[tuple[int, int]] = []
        for _ in range(months):  # walk back one month at a time from the current one, then put the oldest first
            labels.append((year, month))
            year, month = (year - 1, 12) if month == 1 else (year, month - 1)
        labels.reverse()
        first_year, first_month = labels[0]
        expenses, purchases = report_repository.monthly_totals(
            self._session, DEFAULT_SPEND_STATUSES, date(first_year, first_month, 1)
        )
        counted = report_repository.status_counts(self._session)

        def spread(kind: str) -> list[StatusCount]:
            hidden = actor is not None and drafts_hidden_from(actor)
            return [
                StatusCount(status=status, count=0 if hidden and status is S.DRAFT else counted[kind].get(status, 0))
                for status in DocumentStatus
            ]

        series = []
        for label_year, label_month in labels:
            key = (label_year, label_month)
            expense_count, expense_total = expenses.get(key, (0, ZERO))
            purchase_count, purchase_total = purchases.get(key, (0, ZERO))
            series.append(
                OverviewMonth(
                    month=f"{label_year:04d}-{label_month:02d}",
                    expenses=expense_total,
                    purchases=purchase_total,
                    expense_count=expense_count,
                    purchase_count=purchase_count,
                )
            )
        return Overview(
            months=series,
            expense_statuses=spread("expenses"),
            purchase_statuses=spread("purchases"),
            voucher_statuses=spread("vouchers"),
        )

    # CSV -------------------------------------------------------------------------------------------------------------

    def expenses_csv(
        self, actor: Principal, statuses: Sequence[S] | None, date_from: date | None, date_to: date | None
    ) -> CsvFile:
        scope = self._scope(self._statuses(actor, statuses, DEFAULT_SPEND_STATUSES), date_from, date_to)
        self._limiter.hit(("export_user", str(actor.id)))
        report = self.expenses(statuses, date_from, date_to, actor)
        rows = [
            [
                row.expense_type.value,
                text_cell(row.cost_center_code),
                text_cell(row.cost_center_name),
                str(row.expenses),
                amount_cell(row.amount),
            ]
            for row in report.rows
        ]
        return self._export(
            actor, "expenses", scope, ["Type", "Cost centre code", "Cost centre", "Expenses", "Amount"], rows
        )

    def purchases_csv(
        self,
        actor: Principal,
        statuses: Sequence[S] | None,
        date_from: date | None,
        date_to: date | None,
        registered: bool | None,
    ) -> CsvFile:
        scope = self._scope(self._statuses(actor, statuses, DEFAULT_SPEND_STATUSES), date_from, date_to)
        self._limiter.hit(("export_user", str(actor.id)))
        report = self.purchases(statuses, date_from, date_to, registered, actor)
        rows = [
            [
                text_cell(row.vendor_name),
                "registered" if row.registered else "unregistered",
                str(row.purchases),
                *(
                    amount_cell(value)
                    for value in (
                        row.subtotal,
                        row.sales_tax,
                        row.gross,
                        row.sales_tax_withheld,
                        row.income_tax_withheld,
                        row.payable,
                    )
                ),
            ]
            for row in report.rows
        ]
        header = [
            "Vendor",
            "Registration",
            "Purchases",
            "Subtotal",
            "Sales tax",
            "Gross",
            "Sales tax withheld",
            "Income tax withheld",
            "Payable",
        ]
        return self._export(actor, "purchases", scope, header, rows)

    def expense_list_csv(
        self,
        actor: Principal,
        *,
        status: S | None,
        expense_type: ExpenseType | None,
        category_id: int | None,
        date_from: date | None,
        date_to: date | None,
        amount_min: Decimal | None,
        amount_max: Decimal | None,
        q: str | None,
    ) -> CsvFile:
        """Every expense the list filters match, one row each, for a spreadsheet."""
        scope = self._scope([status] if status else [], date_from, date_to)
        self._limiter.hit(("export_user", str(actor.id)))
        found, total = document_repository.list_expenses(
            self._session,
            only_created_by=None,
            status=status,
            expense_type=expense_type,
            category_id=category_id,
            date_from=date_from,
            date_to=date_to,
            amount_min=amount_min,
            amount_max=amount_max,
            q=q,
            sort="document_date",
            limit=EXPORT_ROW_LIMIT,
            offset=0,
            hide_drafts=drafts_hidden_from(actor),
        )
        self._too_many(total)
        centres = {row.id: row.code for row in self._session.scalars(select(CostCenter))}
        projects = {row.id: row.code for row in self._session.scalars(select(Project))}

        def centre(expense: Expense) -> str:
            if expense.expense_type is ExpenseType.INDIRECT:
                return "Shared: " + ", ".join(row.cost_center.code for row in expense.allocations)
            return centres.get(expense.cost_center_id, "") if expense.cost_center_id else ""

        rows = [
            [
                str(e.id),
                e.document_date.isoformat(),
                text_cell(e.description),
                text_cell(e.category_name),
                e.expense_type.value,
                text_cell(centre(e)),
                text_cell(projects.get(e.project_id, "") if e.project_id else ""),
                amount_cell(e.amount),
                amount_cell(e.tax_amount),
                e.currency,
                e.payment_method.value,
                e.status.value,
                text_cell(e.created_by_name),
                e.created_at.isoformat(),
                text_cell(e.voucher.number if e.voucher else ""),
            ]
            for e in found
        ]
        header = [
            "ID",
            "Date",
            "Description",
            "Category",
            "Type",
            "Cost centre",
            "Project",
            "Amount",
            "Tax",
            "Currency",
            "Payment method",
            "Status",
            "Created by",
            "Created at (UTC)",
            "Voucher",
        ]
        return self._export(actor, "expense-list", scope, header, rows)

    def purchase_list_csv(
        self,
        actor: Principal,
        *,
        status: S | None,
        vendor_id: int | None,
        registered: bool | None,
        date_from: date | None,
        date_to: date | None,
        amount_min: Decimal | None,
        amount_max: Decimal | None,
        q: str | None,
    ) -> CsvFile:
        """Every purchase the list filters match, one row each, with the tax figures, for a spreadsheet."""
        scope = self._scope([status] if status else [], date_from, date_to)
        self._limiter.hit(("export_user", str(actor.id)))
        found, total = document_repository.list_purchases(
            self._session,
            only_created_by=None,
            status=status,
            vendor_id=vendor_id,
            registered=registered,
            date_from=date_from,
            date_to=date_to,
            amount_min=amount_min,
            amount_max=amount_max,
            q=q,
            sort="document_date",
            limit=EXPORT_ROW_LIMIT,
            offset=0,
            hide_drafts=drafts_hidden_from(actor),
        )
        self._too_many(total)
        rows = [
            [
                str(p.id),
                p.document_date.isoformat(),
                text_cell(p.vendor_name),
                text_cell(p.invoice_number),
                p.document_kind.value,
                text_cell(p.description),
                amount_cell(p.subtotal),
                amount_cell(p.sales_tax_total),
                amount_cell(p.gross_total),
                amount_cell(p.sales_tax_withheld),
                amount_cell(p.income_tax_withheld),
                amount_cell(p.payable),
                p.currency,
                p.status.value,
                text_cell(p.created_by_name),
                p.created_at.isoformat(),
                text_cell(p.voucher.number if p.voucher else ""),
            ]
            for p in found
        ]
        header = [
            "ID",
            "Date",
            "Vendor",
            "Invoice number",
            "Kind",
            "Description",
            "Subtotal",
            "Sales tax",
            "Gross",
            "Sales tax withheld",
            "Income tax withheld",
            "Payable",
            "Currency",
            "Status",
            "Created by",
            "Created at (UTC)",
            "Voucher",
        ]
        return self._export(actor, "purchase-list", scope, header, rows)

    @staticmethod
    def _statuses(actor: Principal | None, requested: Sequence[S] | None, default: Sequence[S]) -> list[S]:
        """The statuses a report covers: those asked for (or the default), less drafts for who may not see them."""
        chosen = list(default if requested is None else requested)
        if actor is not None and drafts_hidden_from(actor):
            chosen = [status for status in chosen if status is not S.DRAFT]
        return chosen

    @staticmethod
    def _too_many(total: int) -> None:
        if total > EXPORT_ROW_LIMIT:
            raise ValidationFailedError(
                f"That is {total} rows, more than one file holds ({EXPORT_ROW_LIMIT}). Narrow the dates or filters.",
                errors=[FieldError("date_from", "Narrow the filters to export fewer rows.", "too_many_rows")],
            )

    def activity_csv(self, actor: Principal, date_from: date | None, date_to: date | None) -> CsvFile:
        scope = self._scope(DEFAULT_SPEND_STATUSES, date_from, date_to)
        self._limiter.hit(("export_user", str(actor.id)))
        report = self.activity(date_from, date_to)
        rows = [
            [
                text_cell(row.full_name),
                row.role.value,
                *(
                    str(value)
                    for value in (
                        row.expenses_created,
                        row.purchases_created,
                        row.vouchers_created,
                        row.submitted,
                        row.rejected_received,
                        row.approved,
                        row.rejected_given,
                        row.posted,
                        row.voided,
                    )
                ),
            ]
            for row in report.rows
        ]
        header = [
            "Person",
            "Role",
            "Expenses created",
            "Purchases created",
            "Vouchers created",
            "Submitted",
            "Rejected on them",
            "Approved",
            "Rejected by them",
            "Posted",
            "Voided",
        ]
        return self._export(actor, "activity", scope, header, rows)

    def register_csv(
        self,
        actor: Principal,
        statuses: Sequence[S] | None,
        date_from: date | None,
        date_to: date | None,
        voucher_type: VoucherType | None,
    ) -> CsvFile:
        scope = self._scope(self._statuses(actor, statuses, DEFAULT_REGISTER_STATUSES), date_from, date_to)
        self._limiter.hit(("export_user", str(actor.id)))
        found = report_repository.voucher_register_all(self._session, scope.statuses, date_from, date_to, voucher_type)
        rows = [self._register_cells(row) for row in found]
        header = ["Number", "Type", "Date", "Status", "Narration", "Total", "Expense", "Purchase", "Reverses"]
        return self._export(actor, "voucher-register", scope, header, rows)

    # -----------------------------------------------------------------------------------------------------------------

    @staticmethod
    def _register_cells(row: Row[Any]) -> list[str]:
        return [
            text_cell(row.number),
            row.voucher_type.value,
            row.document_date.isoformat(),
            row.status.value,
            text_cell(row.description),
            amount_cell(Decimal(row.total)),
            "" if row.expense_id is None else str(row.expense_id),
            "" if row.purchase_id is None else str(row.purchase_id),
            text_cell(row.reversal_of_number),
        ]

    def _export(
        self, actor: Principal, name: str, scope: ReportScope, header: list[str], rows: list[list[str]]
    ) -> CsvFile:
        """Record the export, with its filter and row count, and commit, before anything is sent."""
        self._audit.record(
            actor_id=actor.id,
            action="report.exported",
            entity_type="report",
            after={
                "report": name,
                "date_from": scope.date_from.isoformat() if scope.date_from else None,
                "date_to": scope.date_to.isoformat() if scope.date_to else None,
                "statuses": [status.value for status in scope.statuses],
                "rows": len(rows),
            },
        )
        self._session.commit()
        today = self._clock.today(ZoneInfo(self._settings.display_timezone))
        return CsvFile(f"daftar-{name}-{today.isoformat()}.csv", header, rows)

    @staticmethod
    def _scope(statuses: Sequence[S], date_from: date | None, date_to: date | None) -> ReportScope:
        if date_from is not None and date_to is not None and date_from > date_to:
            raise ValidationFailedError(
                "The start date is after the end date.",
                errors=[FieldError("date_from", "Start on or before the end date.", "invalid_range")],
            )
        return ReportScope(date_from=date_from, date_to=date_to, statuses=sorted(set(statuses), key=lambda s: s.value))

    @staticmethod
    def _totals(rows: Sequence[PurchaseReportRow]) -> PurchaseReportTotals:
        def total(field: str) -> Decimal:
            return sum((getattr(row, field) for row in rows), ZERO)

        return PurchaseReportTotals(
            purchases=sum(row.purchases for row in rows),
            subtotal=total("subtotal"),
            sales_tax=total("sales_tax"),
            gross=total("gross"),
            sales_tax_withheld=total("sales_tax_withheld"),
            income_tax_withheld=total("income_tax_withheld"),
            payable=total("payable"),
        )
