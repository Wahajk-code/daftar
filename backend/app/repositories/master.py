"""Queries for the chart of accounts, categories, cost centres, projects, periods and posting accounts."""

from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.enums import AccountType, PostingKey, ProjectKind
from app.models.master import (
    Account,
    AccountingSettings,
    Category,
    ClosedPeriod,
    CostCenter,
    PostingAccount,
    Project,
)
from app.repositories.paging import order_clauses, paginate, search_clause

# Accounts ------------------------------------------------------------------------------------------------------------


def get_account(session: Session, account_id: int, *, for_update: bool = False) -> Account | None:
    statement = select(Account).where(Account.id == account_id)
    if for_update:
        statement = statement.with_for_update().execution_options(populate_existing=True)
    return session.scalars(statement).one_or_none()


def add(session: Session, row: Account | Category | CostCenter | Project | ClosedPeriod) -> None:
    session.add(row)
    session.flush()


def has_children(session: Session, account_id: int, *, active_only: bool = False) -> bool:
    statement = select(Account.id).where(Account.parent_id == account_id)
    if active_only:
        statement = statement.where(Account.is_active.is_(True))
    return session.scalars(statement.limit(1)).first() is not None


def list_accounts(
    session: Session,
    *,
    q: str | None,
    type_: AccountType | None,
    parent_id: int | None,
    is_active: bool | None,
    is_postable: bool | None,
    sort: str | None,
    limit: int,
    offset: int,
) -> tuple[list[Account], int]:
    statement = select(Account)
    found = search_clause([Account.name, Account.code], q)
    if found is not None:
        statement = statement.where(found)
    if type_ is not None:
        statement = statement.where(Account.type == type_)
    if parent_id is not None:
        statement = statement.where(Account.parent_id == parent_id)
    if is_active is not None:
        statement = statement.where(Account.is_active.is_(is_active))
    if is_postable is not None:
        statement = statement.where(Account.is_postable.is_(is_postable))
    order = order_clauses(sort, {"code": Account.code, "name": Account.name, "type": Account.type}, "code", Account.id)
    return paginate(session, statement, order, limit=limit, offset=offset)


# Categories ----------------------------------------------------------------------------------------------------------


def list_categories(
    session: Session, *, q: str | None, is_active: bool | None, sort: str | None, limit: int, offset: int
) -> tuple[list[Category], int]:
    statement = select(Category)
    found = search_clause([Category.name], q)
    if found is not None:
        statement = statement.where(found)
    if is_active is not None:
        statement = statement.where(Category.is_active.is_(is_active))
    order = order_clauses(sort, {"name": func.lower(Category.name)}, "name", Category.id)  # type: ignore[dict-item]
    return paginate(session, statement, order, limit=limit, offset=offset)


# Cost centres and projects -------------------------------------------------------------------------------------------


def list_cost_centers(
    session: Session, *, q: str | None, is_active: bool | None, sort: str | None, limit: int, offset: int
) -> tuple[list[CostCenter], int]:
    statement = select(CostCenter)
    found = search_clause([CostCenter.name, CostCenter.code], q)
    if found is not None:
        statement = statement.where(found)
    if is_active is not None:
        statement = statement.where(CostCenter.is_active.is_(is_active))
    order = order_clauses(sort, {"code": CostCenter.code, "name": CostCenter.name}, "code", CostCenter.id)
    return paginate(session, statement, order, limit=limit, offset=offset)


def list_projects(
    session: Session,
    *,
    q: str | None,
    kind: ProjectKind | None,
    is_active: bool | None,
    sort: str | None,
    limit: int,
    offset: int,
) -> tuple[list[Project], int]:
    statement = select(Project)
    found = search_clause([Project.name, Project.code], q)
    if found is not None:
        statement = statement.where(found)
    if kind is not None:
        statement = statement.where(Project.kind == kind)
    if is_active is not None:
        statement = statement.where(Project.is_active.is_(is_active))
    order = order_clauses(sort, {"code": Project.code, "name": Project.name, "kind": Project.kind}, "code", Project.id)
    return paginate(session, statement, order, limit=limit, offset=offset)


# Periods -------------------------------------------------------------------------------------------------------------


def list_periods(session: Session, *, sort: str | None, limit: int, offset: int) -> tuple[list[ClosedPeriod], int]:
    order = order_clauses(
        sort,
        {"start_date": ClosedPeriod.start_date, "closed_at": ClosedPeriod.closed_at},
        "-start_date",
        ClosedPeriod.id,
    )
    return paginate(session, select(ClosedPeriod), order, limit=limit, offset=offset)


def get_period(session: Session, period_id: int) -> ClosedPeriod | None:
    return session.get(ClosedPeriod, period_id)


def closed_period_containing(session: Session, day: date) -> ClosedPeriod | None:
    """The period, if any, closed over this date. Posting into it is refused (domain-rules.md section 4)."""
    statement = select(ClosedPeriod).where(
        ClosedPeriod.reopened_at.is_(None), ClosedPeriod.start_date <= day, ClosedPeriod.end_date >= day
    )
    return session.scalars(statement).first()


# Posting accounts ----------------------------------------------------------------------------------------------------


def list_posting_accounts(session: Session) -> list[PostingAccount]:
    return list(session.scalars(select(PostingAccount).order_by(PostingAccount.key)))


def get_posting_account(session: Session, key: PostingKey) -> PostingAccount | None:
    return session.get(PostingAccount, key)


def get_accounting_settings(session: Session) -> AccountingSettings:
    """The one settings row. The migration creates it and the database allows no other, so it is always there."""
    return session.scalars(select(AccountingSettings)).one()
