from datetime import datetime

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.core.enums import AuthPurpose
from app.models.auth import AuthToken, RefreshToken
from app.repositories.paging import order_clauses, paginate

# Refresh tokens ---------------------------------------------------------------------------------------------------


def add_refresh(session: Session, token: RefreshToken) -> RefreshToken:
    session.add(token)
    session.flush()
    return token


def get_refresh_by_hash(session: Session, token_hash: str) -> RefreshToken | None:
    statement = select(RefreshToken).where(RefreshToken.token_hash == token_hash)
    return session.scalars(statement).one_or_none()


def claim_refresh(session: Session, token_id: int, now: datetime) -> bool:
    """Consume a refresh token exactly once. Of two parallel requests with the same token, one gets True."""
    statement = (
        update(RefreshToken)
        .where(RefreshToken.id == token_id, RefreshToken.consumed_at.is_(None), RefreshToken.revoked_at.is_(None))
        .values(consumed_at=now)
        .returning(RefreshToken.id)
    )
    return session.execute(statement).first() is not None


def revoke_refresh(session: Session, token_id: int, now: datetime) -> None:
    session.execute(
        update(RefreshToken)
        .where(RefreshToken.id == token_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=now)
    )


def revoke_all_refresh(session: Session, user_id: int, now: datetime) -> int:
    """Revoke every refresh token of the user that is still usable. Returns how many."""
    statement = (
        update(RefreshToken)
        .where(
            RefreshToken.user_id == user_id,
            RefreshToken.revoked_at.is_(None),
            RefreshToken.consumed_at.is_(None),
        )
        .values(revoked_at=now)
        .returning(RefreshToken.id)
    )
    return len(session.execute(statement).all())


def count_live_refresh(session: Session, user_id: int, now: datetime) -> int:
    statement = select(func.count()).where(
        RefreshToken.user_id == user_id,
        RefreshToken.revoked_at.is_(None),
        RefreshToken.consumed_at.is_(None),
        RefreshToken.expires_at > now,
    )
    return session.scalar(statement) or 0


# Invite and reset tokens ------------------------------------------------------------------------------------------


def add_auth_token(session: Session, token: AuthToken) -> AuthToken:
    session.add(token)
    session.flush()
    return token


def get_auth_token_by_hash(session: Session, token_hash: str) -> AuthToken | None:
    return session.scalars(select(AuthToken).where(AuthToken.token_hash == token_hash)).one_or_none()


def get_auth_token(session: Session, token_id: int, purpose: AuthPurpose) -> AuthToken | None:
    statement = select(AuthToken).where(AuthToken.id == token_id, AuthToken.purpose == purpose)
    return session.scalars(statement).one_or_none()


def claim_auth_token(session: Session, token_id: int, now: datetime) -> bool:
    """Use a token exactly once, and only while it is unused, unrevoked and unexpired."""
    statement = (
        update(AuthToken)
        .where(
            AuthToken.id == token_id,
            AuthToken.used_at.is_(None),
            AuthToken.revoked_at.is_(None),
            AuthToken.expires_at > now,
        )
        .values(used_at=now)
        .returning(AuthToken.id)
    )
    return session.execute(statement).first() is not None


def revoke_auth_token(session: Session, token_id: int, now: datetime) -> None:
    session.execute(
        update(AuthToken)
        .where(AuthToken.id == token_id, AuthToken.used_at.is_(None), AuthToken.revoked_at.is_(None))
        .values(revoked_at=now)
    )
    session.flush()


def revoke_user_resets(session: Session, user_id: int, now: datetime) -> None:
    """A new reset link replaces any earlier one that was never used."""
    session.execute(
        update(AuthToken)
        .where(
            AuthToken.user_id == user_id,
            AuthToken.purpose == AuthPurpose.PASSWORD_RESET,
            AuthToken.used_at.is_(None),
            AuthToken.revoked_at.is_(None),
        )
        .values(revoked_at=now)
    )
    session.flush()


def pending_invite_for_email(session: Session, email: str) -> AuthToken | None:
    statement = select(AuthToken).where(
        AuthToken.purpose == AuthPurpose.INVITE,
        AuthToken.email == email,
        AuthToken.used_at.is_(None),
        AuthToken.revoked_at.is_(None),
    )
    return session.scalars(statement).one_or_none()


def list_invites(session: Session, *, sort: str | None, limit: int, offset: int) -> tuple[list[AuthToken], int]:
    statement = select(AuthToken).where(AuthToken.purpose == AuthPurpose.INVITE)
    order = order_clauses(
        sort, {"created_at": AuthToken.created_at, "email": AuthToken.email}, "-created_at", AuthToken.id
    )
    return paginate(session, statement, order, limit=limit, offset=offset)
