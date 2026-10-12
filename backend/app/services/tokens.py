"""Shared by the services that hand out single-use links (invites and password resets)."""

from datetime import datetime, timedelta
from urllib.parse import quote
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.config import Settings
from app.core.clock import format_display_instant
from app.core.enums import AuthPurpose, Role
from app.core.errors import ErrorCode, GuardFailedError
from app.core.security import hash_token, new_secret_token
from app.models.auth import AuthToken
from app.repositories import tokens as token_repository


def link(settings: Settings, path: str, token: str) -> str:
    return f"{settings.web_base_url.rstrip('/')}/{path}?token={quote(token, safe='')}"


def expiry_text(settings: Settings, expires_at: datetime) -> str:
    return format_display_instant(expires_at, ZoneInfo(settings.display_timezone))


def issue_reset(session: Session, settings: Settings, *, user_id: int, now: datetime) -> tuple[AuthToken, str]:
    """A fresh password-reset token. Any earlier unused one is revoked. Returns the row and the plain token."""
    token_repository.revoke_user_resets(session, user_id, now)
    plain = new_secret_token()
    row = AuthToken(
        purpose=AuthPurpose.PASSWORD_RESET,
        token_hash=hash_token(plain),
        user_id=user_id,
        created_at=now,
        expires_at=now + timedelta(minutes=settings.reset_ttl_minutes),
    )
    return token_repository.add_auth_token(session, row), plain


def issue_invite(
    session: Session, settings: Settings, *, email: str, role: Role, created_by: int, now: datetime
) -> tuple[AuthToken, str]:
    plain = new_secret_token()
    row = AuthToken(
        purpose=AuthPurpose.INVITE,
        token_hash=hash_token(plain),
        email=email,
        role=role,
        created_by=created_by,
        created_at=now,
        expires_at=now + timedelta(days=settings.invite_ttl_days),
    )
    return token_repository.add_auth_token(session, row), plain


def usable_or_error(row: AuthToken | None, purpose: AuthPurpose, now: datetime) -> AuthToken:
    """The token row if it can be used now; otherwise the error that tells the person why, in plain words."""
    if row is None or row.purpose != purpose:
        raise GuardFailedError("This link is not valid. Ask for a new one.", code=ErrorCode.TOKEN_INVALID)
    if row.revoked_at is not None:
        raise GuardFailedError("This link was cancelled. Ask for a new one.", code=ErrorCode.TOKEN_REVOKED)
    if row.used_at is not None:
        raise GuardFailedError("This link has already been used.", code=ErrorCode.TOKEN_INVALID)
    if row.expires_at <= now:
        raise GuardFailedError("This link has expired. Ask for a new one.", code=ErrorCode.TOKEN_EXPIRED)
    return row
