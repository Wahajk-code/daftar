"""Reports and their CSV downloads. HTTP only: the rules are in ReportService."""

from collections.abc import Iterator
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse

from app.core import csv_export
from app.core.enums import DocumentStatus, Role, VoucherType
from app.deps import PrincipalDep, ReportServiceDep, roles
from app.schemas.page import Page, PageParamsDep
from app.schemas.reports import ExpenseReport, PurchaseReport, VoucherRegisterRow
from app.services.reports import CsvFile

router = APIRouter(prefix="/reports", tags=["reports"])

# Staff see no reports (decision 4): they see only their own expenses.
OFFICE = roles(Role.ADMIN, Role.ACCOUNTANT, Role.APPROVER)

Statuses = Annotated[
    list[DocumentStatus] | None,
    Query(
        description=(
            "Statuses to include. Expenses and purchases default to approved and posted;"
            " the register to posted and void."
        )
    ),
]
DateFrom = Annotated[date | None, Query(description="First document date, inclusive (YYYY-MM-DD).")]
DateTo = Annotated[date | None, Query(description="Last document date, inclusive (YYYY-MM-DD).")]


def _download(file: CsvFile) -> StreamingResponse:
    chunks: Iterator[bytes] = csv_export.render(file.header, file.rows)
    return StreamingResponse(
        chunks,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{file.filename}"', "Cache-Control": "no-store"},
    )


@router.get("/expenses", operation_id="report_expenses", **OFFICE)
def report_expenses(
    service: ReportServiceDep, statuses: Statuses = None, date_from: DateFrom = None, date_to: DateTo = None
) -> ExpenseReport:
    """Expenses by type and cost centre."""
    return service.expenses(statuses, date_from, date_to)


@router.get("/expenses/csv", operation_id="export_report_expenses", **OFFICE)
def export_expenses(
    actor: PrincipalDep,
    service: ReportServiceDep,
    statuses: Statuses = None,
    date_from: DateFrom = None,
    date_to: DateTo = None,
) -> StreamingResponse:
    """The same report as a CSV file. Limited per user and recorded in the audit log."""
    return _download(service.expenses_csv(actor, statuses, date_from, date_to))


@router.get("/purchases", operation_id="report_purchases", **OFFICE)
def report_purchases(
    service: ReportServiceDep,
    statuses: Statuses = None,
    date_from: DateFrom = None,
    date_to: DateTo = None,
    registered: Annotated[bool | None, Query(description="Only vendors registered (true) or not (false).")] = None,
) -> PurchaseReport:
    """Purchases by vendor, split into registered and unregistered vendors."""
    return service.purchases(statuses, date_from, date_to, registered)


@router.get("/purchases/csv", operation_id="export_report_purchases", **OFFICE)
def export_purchases(
    actor: PrincipalDep,
    service: ReportServiceDep,
    statuses: Statuses = None,
    date_from: DateFrom = None,
    date_to: DateTo = None,
    registered: bool | None = None,
) -> StreamingResponse:
    return _download(service.purchases_csv(actor, statuses, date_from, date_to, registered))


@router.get("/vouchers", operation_id="report_voucher_register", **OFFICE)
def voucher_register(
    service: ReportServiceDep,
    page: PageParamsDep,
    statuses: Statuses = None,
    date_from: DateFrom = None,
    date_to: DateTo = None,
    voucher_type: VoucherType | None = None,
) -> Page[VoucherRegisterRow]:
    """The voucher register in number order, one page at a time."""
    rows, total = service.register(statuses, date_from, date_to, voucher_type, limit=page.limit, offset=page.offset)
    return Page(items=rows, total=total, limit=page.limit, offset=page.offset)


@router.get("/vouchers/csv", operation_id="export_report_voucher_register", **OFFICE)
def export_voucher_register(
    actor: PrincipalDep,
    service: ReportServiceDep,
    statuses: Statuses = None,
    date_from: DateFrom = None,
    date_to: DateTo = None,
    voucher_type: VoucherType | None = None,
) -> StreamingResponse:
    return _download(service.register_csv(actor, statuses, date_from, date_to, voucher_type))
