from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, Identity, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.enums import Role
from app.models.base import Base, UtcDateTime, pg_enum


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        # Emails are stored normalised. The service normalises; the database refuses anything that is not lower case.
        CheckConstraint("email = lower(email)", name="email_lower"),
        CheckConstraint("length(btrim(full_name)) > 0", name="full_name_not_blank"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    email: Mapped[str] = mapped_column(String(254), unique=True)
    full_name: Mapped[str] = mapped_column(String(200))
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[Role] = mapped_column(pg_enum(Role, "user_role"))
    is_active: Mapped[bool] = mapped_column(server_default=text("true"))
    tour_completed_at: Mapped[datetime | None] = mapped_column(UtcDateTime, default=None)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime, server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(UtcDateTime, server_default=text("now()"))
