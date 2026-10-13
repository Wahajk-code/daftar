"""Aggregate queries for the reports. Read only; sums are done by the database and never divided."""

from collections.abc import Sequence
from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import Row, func, select
from sqlalchemy.orm import Session, aliased

from app.core.enums import DocumentStatus, ExpenseType
from app.models.documents import Expense, ExpenseAllocation, Purchase
from app.models.master import CostCenter
from app.models.vendor import Vendor
from app.models.vouchers import Voucher, VoucherLine


def _within(
    statement: Any,
    column: Any,
    date_column: Any,
    statuses: Sequence[DocumentStatus],
    start: date | None,
    end: date | None,
) -> Any:
    statement = statement.where(column.in_(list(statuses)))
    if start is not None:
        statement = statement.where(date_column >= start)
    if end is not None:
        statement = statement.where(date_column <= end)
    return statement


def expenses_by_type_and_cost_centre(
    session: Session, statuses: Sequence[DocumentStatus], start: date | None, end: date | None
) -> list[Row[Any]]:
    """Direct expenses count under their own cost centre; an indirect expense under each cost centre it was split
    across, for the amount it was allocated there."""
    direct = _within(
        select(
            Expense.expense_type.label("expense_type"),
            CostCenter.code.label("cost_center_code"),
            CostCenter.name.label("cost_center_name"),
            func.count(Expense.id).label("expenses"),
            func.sum(Expense.amount).label("amount"),
        )
        .select_from(Expense)
        .outerjoin(CostCenter, CostCenter.id == Expense.cost_center_id)
        .where(Expense.expense_type == ExpenseType.DIRECT)
        .group_by(Expense.expense_type, CostCenter.id),
        Expense.status,
        Expense.document_date,
        statuses,
        start,
        end,
    )
    indirect = _within(
        select(
            Expense.expense_type.label("expense_type"),
            CostCenter.code.label("cost_center_code"),
            CostCenter.name.label("cost_center_name"),
            func.count(func.distinct(Expense.id)).label("expenses"),
            func.sum(ExpenseAllocation.amount).label("amount"),
        )
        .select_from(ExpenseAllocation)
        .join(Expense, Expense.id == ExpenseAllocation.expense_id)
        .join(CostCenter, CostCenter.id == ExpenseAllocation.cost_center_id)
        .where(Expense.expense_type == ExpenseType.INDIRECT)
        .group_by(Expense.expense_type, CostCenter.id),
        Expense.status,
        Expense.document_date,
        statuses,
        start,
        end,
    )
    rows = [*session.execute(direct).all(), *session.execute(indirect).all()]
    return sorted(rows, key=lambda r: (r.expense_type.value, r.cost_center_code is None, r.cost_center_code or ""))


def expense_totals(
    session: Session, statuses: Sequence[DocumentStatus], start: date | None, end: date | None
) -> tuple[int, Decimal, Decimal]:
    """How many expenses and what they come to, each counted once (the split rows above count a shared expense under
    every cost centre, so they cannot be added up to this)."""
    statement = _within(
        select(
            func.count(Expense.id),
            func.coalesce(func.sum(Expense.amount), 0),
            func.coalesce(func.sum(Expense.tax_amount), 0),
        ),
        Expense.status,
        Expense.document_date,
        statuses,
        start,
        end,
    )
    count, amount, tax = session.execute(statement).one()
    return int(count), Decimal(amount), Decimal(tax)


def purchases_by_vendor(
    session: Session,
    statuses: Sequence[DocumentStatus],
    start: date | None,
    end: date | None,
    registered: bool | None,
) -> list[Row[Any]]:
    """One row per vendor and registration status at the time of the purchase (the flag is copied onto each
    purchase, so a vendor who registered mid-year appears in both)."""
    statement = (
        select(
            Vendor.id.label("vendor_id"),
            Vendor.name.label("vendor_name"),
            Purchase.vendor_registered.label("registered"),
            func.count(Purchase.id).label("purchases"),
            func.sum(Purchase.subtotal).label("subtotal"),
            func.sum(Purchase.sales_tax_total).label("sales_tax"),
            func.sum(Purchase.gross_total).label("gross"),
            func.sum(Purchase.sales_tax_withheld).label("sales_tax_withheld"),
            func.sum(Purchase.income_tax_withheld).label("income_tax_withheld"),
            func.sum(Purchase.payable).label("payable"),
        )
        .select_from(Purchase)
        .join(Vendor, Vendor.id == Purchase.vendor_id)
        .group_by(Vendor.id, Vendor.name, Purchase.vendor_registered)
        .order_by(Purchase.vendor_registered.desc(), Vendor.name, Vendor.id)
    )
    statement = _within(statement, Purchase.status, Purchase.document_date, statuses, start, end)
    if registered is not None:
        statement = statement.where(Purchase.vendor_registered.is_(registered))
    return list(session.execute(statement).all())


def _voucher_register_query(
    statuses: Sequence[DocumentStatus], start: date | None, end: date | None, voucher_type: Any
) -> Any:
    original = aliased(Voucher)
    total = (
        select(func.coalesce(func.sum(VoucherLine.debit), 0))
        .where(VoucherLine.voucher_id == Voucher.id)
        .scalar_subquery()
    )
    statement = (
        select(
            Voucher.number,
            Voucher.voucher_type,
            Voucher.document_date,
            Voucher.status,
            Voucher.description,
            total.label("total"),
            Voucher.expense_id,
            Voucher.purchase_id,
            original.number.label("reversal_of_number"),
        )
        .select_from(Voucher)
        .outerjoin(original, original.id == Voucher.reversal_of_id)
    )
    statement = _within(statement, Voucher.status, Voucher.document_date, statuses, start, end)
    if voucher_type is not None:
        statement = statement.where(Voucher.voucher_type == voucher_type)
    return statement


_REGISTER_ORDER = (Voucher.voucher_type, Voucher.year, Voucher.seq.nulls_last(), Voucher.id)


def voucher_register(
    session: Session,
    statuses: Sequence[DocumentStatus],
    start: date | None,
    end: date | None,
    voucher_type: Any,
    *,
    limit: int,
    offset: int,
) -> tuple[list[Row[Any]], int]:
    statement = _voucher_register_query(statuses, start, end, voucher_type)
    total = session.scalar(select(func.count()).select_from(statement.subquery())) or 0
    rows = list(session.execute(statement.order_by(*_REGISTER_ORDER).limit(limit).offset(offset)).all())
    return rows, total


def voucher_register_all(
    session: Session, statuses: Sequence[DocumentStatus], start: date | None, end: date | None, voucher_type: Any
) -> list[Row[Any]]:
    statement = _voucher_register_query(statuses, start, end, voucher_type).order_by(*_REGISTER_ORDER)
    return list(session.execute(statement).all())
