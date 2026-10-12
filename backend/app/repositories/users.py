from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.enums import Role
from app.models.user import User
from app.repositories.paging import order_clauses, paginate

SORTABLE = {"name": User.full_name, "email": User.email, "role": User.role, "created_at": User.created_at}


def get(session: Session, user_id: int, *, for_update: bool = False) -> User | None:
    statement = select(User).where(User.id == user_id)
    if for_update:
        statement = statement.with_for_update().execution_options(populate_existing=True)
    return session.scalars(statement).one_or_none()


def get_by_email(session: Session, email: str) -> User | None:
    return session.scalars(select(User).where(User.email == email)).one_or_none()


def add(session: Session, user: User) -> User:
    session.add(user)
    session.flush()
    return user


def lock_active_admins(session: Session) -> list[User]:
    """Lock every active Admin row, in id order. Anything that could remove an Admin takes this lock first, so two
    Admins cannot remove each other at the same moment. `populate_existing` because a lost race leaves stale rows."""
    statement = (
        select(User)
        .where(User.role == Role.ADMIN, User.is_active.is_(True))
        .order_by(User.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    return list(session.scalars(statement))


def list_users(
    session: Session,
    *,
    q: str | None,
    role: Role | None,
    is_active: bool | None,
    sort: str | None,
    limit: int,
    offset: int,
) -> tuple[list[User], int]:
    statement = select(User)
    if q:
        pattern = f"%{q.lower()}%"
        statement = statement.where(or_(func.lower(User.full_name).like(pattern), User.email.like(pattern)))
    if role is not None:
        statement = statement.where(User.role == role)
    if is_active is not None:
        statement = statement.where(User.is_active.is_(is_active))
    order = order_clauses(sort, SORTABLE, "name", User.id)
    return paginate(session, statement, order, limit=limit, offset=offset)


def active_by_role(session: Session, role: Role) -> list[User]:
    return list(session.scalars(select(User).where(User.role == role, User.is_active.is_(True)).order_by(User.id)))
