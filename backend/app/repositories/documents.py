"""Queries for expenses, purchases, attachments and the approval history. Reads load what the screens show in a fixed
number of queries (joined one-to-one parents, one extra query per collection), never one query per row."""

from datetime import date

from sqlalchemy import Select, func, or_, select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.core.enums import DocumentStatus, DocumentType, ExpenseType
from app.models.documents import (
    Attachment,
    DocumentEvent,
    Expense,
    ExpenseAllocation,
    Purchase,
)
from app.repositories.paging import order_clauses, paginate

# Expenses ------------------------------------------------------------------------------------------------------------


def _expense_query() -> Select[Expense]:
    return select(Expense).options(
        joinedload(Expense.creator),
        joinedload(Expense.category),
        selectinload(Expense.allocations).joinedload(ExpenseAllocation.cost_center),
    )


def get_expense(
    session: Session, expense_id: int, *, for_update: bool = False, refresh: bool = False
) -> Expense | None:
    if for_update:
        # Lock the bare row first (a lock cannot be taken through an outer join), then load what the screen needs.
        locked = select(Expense.id).where(Expense.id == expense_id).with_for_update()
        if session.scalars(locked).first() is None:
            return None
        return session.scalars(
            _expense_query().where(Expense.id == expense_id).execution_options(populate_existing=True)
        ).one()
    statement = _expense_query().where(Expense.id == expense_id)
    if refresh:
        statement = statement.execution_options(populate_existing=True)
    return session.scalars(statement).unique().one_or_none()


def add_expense(session: Session, expense: Expense) -> Expense:
    session.add(expense)
    session.flush()
    return expense


def list_expenses(
    session: Session,
    *,
    only_created_by: int | None,
    status: DocumentStatus | None,
    expense_type: ExpenseType | None,
    category_id: int | None,
    date_from: date | None,
    date_to: date | None,
    q: str | None,
    sort: str | None,
    limit: int,
    offset: int,
) -> tuple[list[Expense], int]:
    statement = _expense_query()
    if only_created_by is not None:
        statement = statement.where(Expense.created_by == only_created_by)
    if status is not None:
        statement = statement.where(Expense.status == status)
    if expense_type is not None:
        statement = statement.where(Expense.expense_type == expense_type)
    if category_id is not None:
        statement = statement.where(Expense.category_id == category_id)
    if date_from is not None:
        statement = statement.where(Expense.document_date >= date_from)
    if date_to is not None:
        statement = statement.where(Expense.document_date <= date_to)
    if q:
        statement = statement.where(func.lower(Expense.description).like(f"%{q.lower()}%"))
    order = order_clauses(
        sort,
        {
            "document_date": Expense.document_date,
            "amount": Expense.amount,
            "created_at": Expense.created_at,
            "status": Expense.status,
        },
        "-document_date",
        Expense.id,
    )
    return paginate(session, statement, order, limit=limit, offset=offset)


# Purchases -----------------------------------------------------------------------------------------------------------


def _purchase_query() -> Select[Purchase]:
    return select(Purchase).options(
        joinedload(Purchase.creator), joinedload(Purchase.vendor), selectinload(Purchase.lines)
    )


def get_purchase(
    session: Session, purchase_id: int, *, for_update: bool = False, refresh: bool = False
) -> Purchase | None:
    if for_update:
        locked = select(Purchase.id).where(Purchase.id == purchase_id).with_for_update()
        if session.scalars(locked).first() is None:
            return None
        return session.scalars(
            _purchase_query().where(Purchase.id == purchase_id).execution_options(populate_existing=True)
        ).one()
    statement = _purchase_query().where(Purchase.id == purchase_id)
    if refresh:
        statement = statement.execution_options(populate_existing=True)
    return session.scalars(statement).unique().one_or_none()


def add_purchase(session: Session, purchase: Purchase) -> Purchase:
    session.add(purchase)
    session.flush()
    return purchase


def list_purchases(
    session: Session,
    *,
    only_created_by: int | None,
    status: DocumentStatus | None,
    vendor_id: int | None,
    registered: bool | None,
    date_from: date | None,
    date_to: date | None,
    q: str | None,
    sort: str | None,
    limit: int,
    offset: int,
) -> tuple[list[Purchase], int]:
    statement = _purchase_query()
    if only_created_by is not None:
        statement = statement.where(Purchase.created_by == only_created_by)
    if status is not None:
        statement = statement.where(Purchase.status == status)
    if vendor_id is not None:
        statement = statement.where(Purchase.vendor_id == vendor_id)
    if registered is not None:
        statement = statement.where(Purchase.vendor_registered.is_(registered))
    if date_from is not None:
        statement = statement.where(Purchase.document_date >= date_from)
    if date_to is not None:
        statement = statement.where(Purchase.document_date <= date_to)
    if q:
        pattern = f"%{q.lower()}%"
        statement = statement.where(
            or_(func.lower(Purchase.description).like(pattern), func.lower(Purchase.invoice_number).like(pattern))
        )
    order = order_clauses(
        sort,
        {
            "document_date": Purchase.document_date,
            "gross_total": Purchase.gross_total,
            "payable": Purchase.payable,
            "created_at": Purchase.created_at,
            "status": Purchase.status,
        },
        "-document_date",
        Purchase.id,
    )
    return paginate(session, statement, order, limit=limit, offset=offset)


# Attachments ---------------------------------------------------------------------------------------------------------


def add_attachment(session: Session, attachment: Attachment) -> Attachment:
    session.add(attachment)
    session.flush()
    return attachment


def get_attachment(session: Session, attachment_id: int, *, for_update: bool = False) -> Attachment | None:
    statement = select(Attachment).where(Attachment.id == attachment_id)
    if for_update:
        statement = statement.with_for_update().execution_options(populate_existing=True)
    return session.scalars(statement).one_or_none()


def attachments_of(session: Session, *, expense_id: int | None, purchase_id: int | None) -> list[Attachment]:
    statement = select(Attachment).where(Attachment.removed_at.is_(None))
    if expense_id is not None:
        statement = statement.where(Attachment.expense_id == expense_id)
    if purchase_id is not None:
        statement = statement.where(Attachment.purchase_id == purchase_id)
    return list(session.scalars(statement.order_by(Attachment.id)))


# History -------------------------------------------------------------------------------------------------------------


def add_event(session: Session, event: DocumentEvent) -> DocumentEvent:
    session.add(event)
    session.flush()
    return event


def events_of(session: Session, document_type: DocumentType, document_id: int) -> list[DocumentEvent]:
    statement = (
        select(DocumentEvent)
        .where(DocumentEvent.document_type == document_type, DocumentEvent.document_id == document_id)
        .options(joinedload(DocumentEvent.actor))
        .order_by(DocumentEvent.id)
    )
    return list(session.scalars(statement))
