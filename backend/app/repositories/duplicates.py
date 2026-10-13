"""Queries behind the duplicate warnings. A hit is only a hint, so these return light rows and never lock anything.

"Similar" is decided here, in SQL, by multiplication only: |a - b| * 100 <= a * percent, and a window of days on either
side of the document date."""

from collections.abc import Sequence
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.duplicates import AMOUNT_TOLERANCE_PERCENT, DATE_WINDOW_DAYS
from app.core.enums import DocumentStatus
from app.models.documents import Attachment, Expense, Purchase

S = DocumentStatus
# What another document must be to count: drafts and submitted ones are work in hand, approved and posted ones are
# money decided. A rejected document was sent back for a reason, so it does not make a new one a duplicate.
COUNTED = (S.DRAFT, S.SUBMITTED, S.APPROVED, S.POSTED)


def _counted(hide_drafts: bool) -> tuple[DocumentStatus, ...]:
    return tuple(s for s in COUNTED if not (hide_drafts and s is S.DRAFT))


def _close_in_value(column: Any, amount: Decimal) -> Any:
    return func.abs(column - amount) * 100 <= amount * AMOUNT_TOLERANCE_PERCENT


def _close_in_time(column: Any, day: date) -> Any:
    window = timedelta(days=DATE_WINDOW_DAYS)
    return column.between(day - window, day + window)


def purchases_with_invoice(session: Session, purchase: Purchase, *, hide_drafts: bool = False) -> Sequence[Any]:
    """The same vendor's invoice number, ignoring case and stray spaces."""
    if not purchase.invoice_number or not purchase.invoice_number.strip():
        return []
    statement = select(
        Purchase.id, Purchase.status, Purchase.document_date, Purchase.gross_total.label("amount")
    ).where(
        Purchase.id != purchase.id,
        Purchase.vendor_id == purchase.vendor_id,
        Purchase.status.in_(_counted(hide_drafts)),
        func.lower(func.btrim(Purchase.invoice_number)) == purchase.invoice_number.strip().lower(),
    )
    return session.execute(statement.order_by(Purchase.id)).all()


def similar_purchases(session: Session, purchase: Purchase, *, hide_drafts: bool = False) -> Sequence[Any]:
    """Same vendor, about the same gross value, within a week."""
    statement = select(
        Purchase.id, Purchase.status, Purchase.document_date, Purchase.gross_total.label("amount")
    ).where(
        Purchase.id != purchase.id,
        Purchase.vendor_id == purchase.vendor_id,
        Purchase.status.in_(_counted(hide_drafts)),
        _close_in_value(Purchase.gross_total, purchase.gross_total),
        _close_in_time(Purchase.document_date, purchase.document_date),
    )
    return session.execute(statement.order_by(Purchase.id)).all()


def similar_expenses(
    session: Session, expense: Expense, *, only_author: int | None, hide_drafts: bool = False
) -> Sequence[Any]:
    """Same author, same category, about the same amount, within a week. `only_author` limits who may be shown."""
    statement = select(Expense.id, Expense.status, Expense.document_date, Expense.amount).where(
        Expense.id != expense.id,
        Expense.created_by == expense.created_by,
        Expense.category_id == expense.category_id,
        Expense.status.in_(_counted(hide_drafts)),
        _close_in_value(Expense.amount, expense.amount),
        _close_in_time(Expense.document_date, expense.document_date),
    )
    if only_author is not None:
        statement = statement.where(Expense.created_by == only_author)
    return session.execute(statement.order_by(Expense.id)).all()


def _receipt_hashes(session: Session, *, expense_id: int | None, purchase_id: int | None) -> list[str]:
    statement = select(Attachment.sha256).where(Attachment.removed_at.is_(None))
    if expense_id is not None:
        statement = statement.where(Attachment.expense_id == expense_id)
    else:
        statement = statement.where(Attachment.purchase_id == purchase_id)
    return list(session.scalars(statement))


def expenses_sharing_a_receipt(
    session: Session,
    *,
    expense_id: int | None,
    purchase_id: int | None,
    only_author: int | None,
    hide_drafts: bool = False,
) -> Sequence[Any]:
    """Other expenses holding a receipt with the same SHA-256 as one on this document."""
    hashes = _receipt_hashes(session, expense_id=expense_id, purchase_id=purchase_id)
    if not hashes:
        return []
    statement = (
        select(Expense.id, Expense.status, Expense.document_date, Expense.amount)
        .select_from(Attachment)
        .join(Expense, Expense.id == Attachment.expense_id)
        .where(
            Attachment.removed_at.is_(None), Attachment.sha256.in_(hashes), Expense.status.in_(_counted(hide_drafts))
        )
        .distinct()
        .order_by(Expense.id)
    )
    if expense_id is not None:
        statement = statement.where(Expense.id != expense_id)
    if only_author is not None:
        statement = statement.where(Expense.created_by == only_author)
    return session.execute(statement).all()


def purchases_sharing_a_receipt(
    session: Session, *, expense_id: int | None, purchase_id: int | None, hide_drafts: bool = False
) -> Sequence[Any]:
    hashes = _receipt_hashes(session, expense_id=expense_id, purchase_id=purchase_id)
    if not hashes:
        return []
    statement = (
        select(Purchase.id, Purchase.status, Purchase.document_date, Purchase.gross_total.label("amount"))
        .select_from(Attachment)
        .join(Purchase, Purchase.id == Attachment.purchase_id)
        .where(
            Attachment.removed_at.is_(None), Attachment.sha256.in_(hashes), Purchase.status.in_(_counted(hide_drafts))
        )
        .distinct()
        .order_by(Purchase.id)
    )
    if purchase_id is not None:
        statement = statement.where(Purchase.id != purchase_id)
    return session.execute(statement).all()
