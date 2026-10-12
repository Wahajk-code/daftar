from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models.vendor import Vendor
from app.repositories.paging import order_clauses, paginate

SORTABLE = {"name": func.lower(Vendor.name), "created_at": Vendor.created_at, "updated_at": Vendor.updated_at}


def get(session: Session, vendor_id: int, *, for_update: bool = False) -> Vendor | None:
    statement = select(Vendor).where(Vendor.id == vendor_id)
    if for_update:
        statement = statement.with_for_update().execution_options(populate_existing=True)
    return session.scalars(statement).one_or_none()


def add(session: Session, vendor: Vendor) -> Vendor:
    session.add(vendor)
    session.flush()
    return vendor


def list_vendors(
    session: Session,
    *,
    q: str | None,
    is_active: bool | None,
    registered: bool | None,
    filer: bool | None,
    sort: str | None,
    limit: int,
    offset: int,
) -> tuple[list[Vendor], int]:
    statement = select(Vendor)
    if q:
        pattern = f"%{q.lower()}%"
        statement = statement.where(or_(func.lower(Vendor.name).like(pattern), func.lower(Vendor.ntn).like(pattern)))
    if is_active is not None:
        statement = statement.where(Vendor.is_active.is_(is_active))
    if registered is not None:
        statement = statement.where(Vendor.is_sales_tax_registered.is_(registered))
    if filer is not None:
        statement = statement.where(Vendor.is_filer.is_(filer))
    order = order_clauses(sort, SORTABLE, "name", Vendor.id)  # type: ignore[arg-type]
    return paginate(session, statement, order, limit=limit, offset=offset)
