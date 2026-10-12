from datetime import date, datetime

from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, Identity, Index, String, func, literal_column, text
from sqlalchemy.dialects.postgresql import ExcludeConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.enums import AccountType, PostingKey, ProjectKind
from app.models.base import Base, UtcDateTime, pg_enum


class Account(Base):
    """Chart of accounts. A parent is never postable (a deferred trigger in the database enforces it)."""

    __tablename__ = "accounts"
    __table_args__ = (
        CheckConstraint("code ~ '^[0-9A-Za-z.-]{1,20}$'", name="code_format"),
        CheckConstraint("parent_id IS NULL OR parent_id <> id", name="not_its_own_parent"),
        CheckConstraint("length(btrim(name)) > 0", name="name_not_blank"),
        Index("ix_accounts_parent_id", "parent_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    code: Mapped[str] = mapped_column(String(20), unique=True)
    name: Mapped[str] = mapped_column(String(200))
    type: Mapped[AccountType] = mapped_column(pg_enum(AccountType, "account_type"))
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("accounts.id"), default=None)
    is_postable: Mapped[bool] = mapped_column(server_default=text("true"))
    is_active: Mapped[bool] = mapped_column(server_default=text("true"))
    version: Mapped[int] = mapped_column(server_default=text("1"))
    __mapper_args__ = {"version_id_col": version}
    created_at: Mapped[datetime] = mapped_column(UtcDateTime, server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(UtcDateTime, server_default=text("now()"))


class Category(Base):
    """An expense category. Posting maps it to an account (Pass 4)."""

    __tablename__ = "categories"
    __table_args__ = (
        CheckConstraint("length(btrim(name)) > 0", name="name_not_blank"),
        Index("uq_categories_name_lower", func.lower(func.btrim(text("name"))), unique=True),
        Index("ix_categories_account_id", "account_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"))
    is_active: Mapped[bool] = mapped_column(server_default=text("true"))
    version: Mapped[int] = mapped_column(server_default=text("1"))
    __mapper_args__ = {"version_id_col": version}
    created_at: Mapped[datetime] = mapped_column(UtcDateTime, server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(UtcDateTime, server_default=text("now()"))


class CostCenter(Base):
    __tablename__ = "cost_centers"
    __table_args__ = (
        CheckConstraint("code ~ '^[0-9A-Za-z.-]{1,20}$'", name="code_format"),
        CheckConstraint("length(btrim(name)) > 0", name="name_not_blank"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    code: Mapped[str] = mapped_column(String(20), unique=True)
    name: Mapped[str] = mapped_column(String(120))
    is_active: Mapped[bool] = mapped_column(server_default=text("true"))
    version: Mapped[int] = mapped_column(server_default=text("1"))
    __mapper_args__ = {"version_id_col": version}
    created_at: Mapped[datetime] = mapped_column(UtcDateTime, server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(UtcDateTime, server_default=text("now()"))


class Project(Base):
    """Projects and products share one table, told apart by `kind`."""

    __tablename__ = "projects"
    __table_args__ = (
        CheckConstraint("code ~ '^[0-9A-Za-z.-]{1,20}$'", name="code_format"),
        CheckConstraint("length(btrim(name)) > 0", name="name_not_blank"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    code: Mapped[str] = mapped_column(String(20), unique=True)
    name: Mapped[str] = mapped_column(String(120))
    kind: Mapped[ProjectKind] = mapped_column(pg_enum(ProjectKind, "project_kind"))
    is_active: Mapped[bool] = mapped_column(server_default=text("true"))
    version: Mapped[int] = mapped_column(server_default=text("1"))
    __mapper_args__ = {"version_id_col": version}
    created_at: Mapped[datetime] = mapped_column(UtcDateTime, server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(UtcDateTime, server_default=text("now()"))


class ClosedPeriod(Base):
    """An inclusive date range closed to posting. Reopening stamps the row; it is never deleted."""

    __tablename__ = "closed_periods"
    __table_args__ = (
        CheckConstraint("start_date <= end_date", name="start_not_after_end"),
        ExcludeConstraint(
            (literal_column("daterange(start_date, end_date, '[]')"), "&&"),
            using="gist",
            where=text("reopened_at IS NULL"),
            name="no_overlapping_closed_ranges",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    start_date: Mapped[date]
    end_date: Mapped[date]
    closed_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    closed_at: Mapped[datetime] = mapped_column(UtcDateTime)
    reopened_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), default=None)
    reopened_at: Mapped[datetime | None] = mapped_column(UtcDateTime, default=None)

    @property
    def status(self) -> str:
        return "reopened" if self.reopened_at is not None else "closed"


class PostingAccount(Base):
    """Which account a generated voucher uses for cash, bank and each tax line. Seeded with defaults, Admin-editable."""

    __tablename__ = "posting_accounts"

    key: Mapped[PostingKey] = mapped_column(pg_enum(PostingKey, "posting_key"), primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"))
    updated_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), default=None)
    updated_at: Mapped[datetime] = mapped_column(UtcDateTime, server_default=text("now()"))
