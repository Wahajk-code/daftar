from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, Identity, Index, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.enums import AuthPurpose, Role
from app.models.base import Base, UtcDateTime, pg_enum


class RefreshToken(Base):
    """A rotating refresh token, stored hashed. Using a consumed or revoked token is reuse and revokes them all."""

    __tablename__ = "refresh_tokens"
    __table_args__ = (Index("ix_refresh_tokens_user_id", "user_id"),)

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime)
    expires_at: Mapped[datetime] = mapped_column(UtcDateTime)
    consumed_at: Mapped[datetime | None] = mapped_column(UtcDateTime, default=None)
    revoked_at: Mapped[datetime | None] = mapped_column(UtcDateTime, default=None)


class AuthToken(Base):
    """One table for invites and password resets: hashed, single use, expiring."""

    __tablename__ = "auth_tokens"
    __table_args__ = (
        CheckConstraint(
            "(purpose = 'invite' AND email IS NOT NULL AND role IS NOT NULL AND user_id IS NULL)"
            " OR (purpose = 'password_reset' AND user_id IS NOT NULL AND email IS NULL AND role IS NULL)",
            name="shape_matches_purpose",
        ),
        # At most one invitation waiting per email; a resend revokes the old row first.
        Index(
            "uq_auth_tokens_pending_invite_email",
            "email",
            unique=True,
            postgresql_where=text("purpose = 'invite' AND used_at IS NULL AND revoked_at IS NULL"),
        ),
        Index("ix_auth_tokens_user_id", "user_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    purpose: Mapped[AuthPurpose] = mapped_column(pg_enum(AuthPurpose, "auth_purpose"))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    email: Mapped[str | None] = mapped_column(String(254), default=None)
    role: Mapped[Role | None] = mapped_column(pg_enum(Role, "user_role", create_type=False), default=None)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), default=None)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), default=None)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime)
    expires_at: Mapped[datetime] = mapped_column(UtcDateTime)
    used_at: Mapped[datetime | None] = mapped_column(UtcDateTime, default=None)
    revoked_at: Mapped[datetime | None] = mapped_column(UtcDateTime, default=None)
