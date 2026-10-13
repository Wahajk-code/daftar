"""What the reports return. Money is a string with two places, as everywhere else."""

from datetime import date

from app.core.enums import DocumentStatus, ExpenseType, Role, VoucherType
from app.schemas.base import Money, ResponseModel


class ReportScope(ResponseModel):
    """The filter a report was run with, echoed back so a printed or exported copy says what it covers."""

    date_from: date | None
    date_to: date | None
    statuses: list[DocumentStatus]


class ExpenseReportRow(ResponseModel):
    expense_type: ExpenseType
    cost_center_code: str | None  # empty for a direct expense against a project or product only
    cost_center_name: str | None
    expenses: int
    amount: Money


class ExpenseReportTotals(ResponseModel):
    """Each expense counted once, so these are not the sum of the rows: an indirect expense shows under every cost
    centre it was split across."""

    expenses: int
    amount: Money
    tax_amount: Money


class ExpenseReport(ResponseModel):
    scope: ReportScope
    rows: list[ExpenseReportRow]
    totals: ExpenseReportTotals


class PurchaseReportRow(ResponseModel):
    vendor_id: int
    vendor_name: str
    registered: bool
    purchases: int
    subtotal: Money
    sales_tax: Money
    gross: Money
    sales_tax_withheld: Money
    income_tax_withheld: Money
    payable: Money


class PurchaseReportTotals(ResponseModel):
    purchases: int
    subtotal: Money
    sales_tax: Money
    gross: Money
    sales_tax_withheld: Money
    income_tax_withheld: Money
    payable: Money


class PurchaseReport(ResponseModel):
    scope: ReportScope
    rows: list[PurchaseReportRow]
    registered: PurchaseReportTotals
    unregistered: PurchaseReportTotals
    totals: PurchaseReportTotals


class VoucherRegisterRow(ResponseModel):
    number: str | None
    voucher_type: VoucherType
    document_date: date
    status: DocumentStatus
    description: str
    total: Money
    expense_id: int | None
    purchase_id: int | None
    reversal_of_number: str | None


class ActivityRow(ResponseModel):
    """What one person did in the period, counted from the approval history."""

    user_id: int
    full_name: str
    role: Role
    expenses_created: int
    purchases_created: int
    vouchers_created: int
    submitted: int  # documents they sent for approval
    rejected_received: int  # times a reviewer sent back something they wrote
    approved: int  # decisions they made as a reviewer
    rejected_given: int
    posted: int  # vouchers they posted
    voided: int  # vouchers they voided


class ActivityReport(ResponseModel):
    date_from: date | None
    date_to: date | None
    rows: list[ActivityRow]


class OverviewMonth(ResponseModel):
    """What was decided in one calendar month: approved and posted documents by their document date."""

    month: str  # YYYY-MM
    expenses: Money
    purchases: Money  # gross, tax included
    expense_count: int
    purchase_count: int


class StatusCount(ResponseModel):
    status: DocumentStatus
    count: int


class Overview(ResponseModel):
    """The figures behind the home screen's charts: a run of months, and how documents are spread over statuses."""

    months: list[OverviewMonth]  # oldest first, a month with nothing in it still appears
    expense_statuses: list[StatusCount]
    purchase_statuses: list[StatusCount]
    voucher_statuses: list[StatusCount]
