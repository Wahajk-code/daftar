"""Queries for vouchers and the counter that numbers them."""

from datetime import date

from sqlalchemy import Select, func, or_, select, text
from sqlalchemy.orm import Session, joinedload, selectinload

from app.core.enums import DocumentStatus, VoucherType
from app.models.vouchers import Voucher, VoucherLine
from app.repositories.paging import order_clauses, paginate


def _voucher_query() -> Select[Voucher]:
    return select(Voucher).options(
        joinedload(Voucher.creator),
        selectinload(Voucher.lines).joinedload(VoucherLine.account),
    )


def get_voucher(
    session: Session, voucher_id: int, *, for_update: bool = False, refresh: bool = False
) -> Voucher | None:
    """One voucher with its lines. With `for_update` the row is locked first and then re-read with
    `populate_existing`, so a request that lost a race sees what the winner committed, not a stale copy."""
    if for_update:
        locked = select(Voucher.id).where(Voucher.id == voucher_id).with_for_update()
        if session.scalars(locked).first() is None:
            return None
        refresh = True
    statement = _voucher_query().where(Voucher.id == voucher_id)
    if refresh:
        statement = statement.execution_options(populate_existing=True)
    return session.scalars(statement).unique().one_or_none()


def add_voucher(session: Session, voucher: Voucher) -> Voucher:
    session.add(voucher)
    session.flush()
    return voucher


def get_by_post_key(session: Session, key: str) -> Voucher | None:
    return session.scalars(select(Voucher).where(Voucher.post_key == key)).one_or_none()


def get_by_void_key(session: Session, key: str) -> Voucher | None:
    return session.scalars(select(Voucher).where(Voucher.void_key == key)).one_or_none()


def get_reversal_of(session: Session, voucher_id: int) -> Voucher | None:
    return session.scalars(select(Voucher).where(Voucher.reversal_of_id == voucher_id)).one_or_none()


def get_by_expense(session: Session, expense_id: int) -> Voucher | None:
    return session.scalars(select(Voucher).where(Voucher.expense_id == expense_id)).one_or_none()


def get_by_purchase(session: Session, purchase_id: int) -> Voucher | None:
    return session.scalars(select(Voucher).where(Voucher.purchase_id == purchase_id)).one_or_none()


def next_sequence(session: Session, voucher_type: VoucherType, year: int) -> int:
    """The next number for a type and year, from the counter row, in this transaction.

    One statement creates the row on first use or increments it, and returns the new value. The row lock is held until
    commit, so posts for one type and year run one at a time; a rollback undoes the increment, so a failed post gives
    its number back and there is never a gap. A database sequence cannot do this: it is not rolled back."""
    value = session.execute(
        text(
            "INSERT INTO number_counters (voucher_type, year, last_seq) VALUES (CAST(:t AS voucher_type), :y, 1)"
            " ON CONFLICT (voucher_type, year) DO UPDATE SET last_seq = number_counters.last_seq + 1"
            " RETURNING last_seq"
        ),
        {"t": voucher_type.value, "y": year},
    ).scalar_one()
    return int(value)


def list_vouchers(
    session: Session,
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
    statement = _voucher_query()
    if voucher_type is not None:
        statement = statement.where(Voucher.voucher_type == voucher_type)
    if status is not None:
        statement = statement.where(Voucher.status == status)
    if date_from is not None:
        statement = statement.where(Voucher.document_date >= date_from)
    if date_to is not None:
        statement = statement.where(Voucher.document_date <= date_to)
    if q:
        pattern = f"%{q.lower()}%"
        statement = statement.where(
            or_(func.lower(Voucher.description).like(pattern), func.lower(Voucher.number).like(pattern))
        )
    order = order_clauses(
        sort,
        {
            "document_date": Voucher.document_date,
            "number": Voucher.number,
            "created_at": Voucher.created_at,
            "status": Voucher.status,
        },
        "-document_date",
        Voucher.id,
    )
    return paginate(session, statement, order, limit=limit, offset=offset)
