from datetime import date

from sqlalchemy import case, or_, select
from sqlalchemy.orm import Session

from app.core.enums import TaxCategory, TaxType
from app.models.tax import TaxRule
from app.repositories.paging import order_clauses, paginate


def get(session: Session, rule_id: int, *, for_update: bool = False) -> TaxRule | None:
    statement = select(TaxRule).where(TaxRule.id == rule_id)
    if for_update:
        statement = statement.with_for_update().execution_options(populate_existing=True)
    return session.scalars(statement).one_or_none()


def add(session: Session, rule: TaxRule) -> TaxRule:
    session.add(rule)
    session.flush()
    return rule


def list_rules(
    session: Session,
    *,
    tax_type: TaxType | None,
    category: TaxCategory | None,
    active_on: date | None,
    sort: str | None,
    limit: int,
    offset: int,
) -> tuple[list[TaxRule], int]:
    statement = select(TaxRule)
    if tax_type is not None:
        statement = statement.where(TaxRule.tax_type == tax_type)
    if category is not None:
        statement = statement.where(TaxRule.category == category)
    if active_on is not None:
        statement = statement.where(
            TaxRule.effective_from <= active_on, or_(TaxRule.effective_to.is_(None), TaxRule.effective_to >= active_on)
        )
    order = order_clauses(
        sort,
        {"effective_from": TaxRule.effective_from, "rate_bp": TaxRule.rate_bp, "tax_type": TaxRule.tax_type},
        "-effective_from",
        TaxRule.id,
    )
    return paginate(session, statement, order, limit=limit, offset=offset)


def find(
    session: Session,
    *,
    tax_type: TaxType,
    supplier_registered: bool,
    supplier_filer: bool,
    category: TaxCategory,
    on: date,
) -> TaxRule | None:
    """The rule for this supplier and payment on this date. A rule for the exact category beats one for `any`."""
    statement = (
        select(TaxRule)
        .where(
            TaxRule.tax_type == tax_type,
            TaxRule.supplier_registered.is_(supplier_registered),
            TaxRule.supplier_filer.is_(supplier_filer),
            TaxRule.category.in_([category, TaxCategory.ANY]),
            TaxRule.effective_from <= on,
            or_(TaxRule.effective_to.is_(None), TaxRule.effective_to >= on),
        )
        .order_by(case((TaxRule.category == category, 0), else_=1))
        .limit(1)
    )
    return session.scalars(statement).first()
