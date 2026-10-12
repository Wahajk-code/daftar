"""Vouchers, their lines, and the counters that number them."""

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    ForeignKey,
    Identity,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
    select,
    text,
)
from sqlalchemy.orm import Mapped, aliased, column_property, mapped_column, relationship

from app.core.enums import DocumentStatus, VoucherType
from app.models.base import Base, UtcDateTime, pg_enum
from app.models.master import Account
from app.models.user import User

MONEY = Numeric(14, 2)


class NumberCounter(Base):
    """The last number given for a type and year. Incremented inside the posting transaction, so a rollback gives the
    number back and there is never a gap."""

    __tablename__ = "number_counters"

    voucher_type: Mapped[VoucherType] = mapped_column(pg_enum(VoucherType, "voucher_type"), primary_key=True)
    year: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
    last_seq: Mapped[int] = mapped_column(Integer)


class Voucher(Base):
    __tablename__ = "vouchers"
    __table_args__ = (
        UniqueConstraint("voucher_type", "year", "seq", name="one_number_per_type_year"),
        CheckConstraint("(number IS NOT NULL) = (status IN ('posted', 'void'))", name="numbered_iff_posted_or_void"),
        CheckConstraint(
            "(number IS NULL) = (year IS NULL) AND (number IS NULL) = (seq IS NULL)", name="number_parts_agree"
        ),
        CheckConstraint(
            "(status = 'void' AND length(btrim(coalesce(void_reason, ''))) > 0 AND voided_by IS NOT NULL"
            " AND voided_at IS NOT NULL) OR (status <> 'void' AND void_reason IS NULL AND voided_by IS NULL"
            " AND voided_at IS NULL)",
            name="void_has_reason_and_actor",
        ),
        CheckConstraint("reversal_of_id IS NULL OR status <> 'void'", name="a_reversal_cannot_be_voided"),
        CheckConstraint("num_nonnulls(expense_id, purchase_id) <= 1", name="at_most_one_source"),
        CheckConstraint(
            "reversal_of_id IS NULL OR num_nonnulls(expense_id, purchase_id) = 0", name="a_reversal_has_no_source"
        ),
        CheckConstraint("void_key IS NULL OR status = 'void'", name="void_key_only_when_void"),
        CheckConstraint("post_key IS NULL OR number IS NOT NULL", name="post_key_only_when_numbered"),
        Index("uq_vouchers_number", "number", unique=True, postgresql_where=text("number IS NOT NULL")),
        Index("uq_vouchers_expense_id", "expense_id", unique=True, postgresql_where=text("expense_id IS NOT NULL")),
        Index("uq_vouchers_purchase_id", "purchase_id", unique=True, postgresql_where=text("purchase_id IS NOT NULL")),
        Index(
            "uq_vouchers_reversal_of_id",
            "reversal_of_id",
            unique=True,
            postgresql_where=text("reversal_of_id IS NOT NULL"),
        ),
        Index("uq_vouchers_post_key", "post_key", unique=True, postgresql_where=text("post_key IS NOT NULL")),
        Index("uq_vouchers_void_key", "void_key", unique=True, postgresql_where=text("void_key IS NOT NULL")),
        Index("ix_vouchers_status", "status"),
        Index("ix_vouchers_document_date", "document_date"),
        Index("ix_vouchers_created_by", "created_by"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    voucher_type: Mapped[VoucherType] = mapped_column(pg_enum(VoucherType, "voucher_type", create_type=False))
    status: Mapped[DocumentStatus] = mapped_column(
        pg_enum(DocumentStatus, "document_status", create_type=False), server_default=text("'draft'")
    )
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    document_date: Mapped[date] = mapped_column(Date)
    description: Mapped[str] = mapped_column(String(1000), server_default=text("''"))
    number: Mapped[str | None] = mapped_column(String(30), default=None)
    year: Mapped[int | None] = mapped_column(SmallInteger, default=None)
    seq: Mapped[int | None] = mapped_column(Integer, default=None)
    expense_id: Mapped[int | None] = mapped_column(ForeignKey("expenses.id"), default=None)
    purchase_id: Mapped[int | None] = mapped_column(ForeignKey("purchases.id"), default=None)
    reversal_of_id: Mapped[int | None] = mapped_column(ForeignKey("vouchers.id"), default=None)
    post_key: Mapped[str | None] = mapped_column(String(100), default=None)
    void_key: Mapped[str | None] = mapped_column(String(100), default=None)
    void_reason: Mapped[str | None] = mapped_column(Text, default=None)
    voided_at: Mapped[datetime | None] = mapped_column(UtcDateTime, default=None)
    voided_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), default=None)
    version: Mapped[int] = mapped_column(server_default=text("1"))
    __mapper_args__ = {"version_id_col": version}
    created_at: Mapped[datetime] = mapped_column(UtcDateTime, server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(UtcDateTime, server_default=text("now()"))

    creator: Mapped[User] = relationship(lazy="raise", foreign_keys=[created_by])
    lines: Mapped[list["VoucherLine"]] = relationship(
        lazy="raise", order_by="VoucherLine.line_no", cascade="all, delete-orphan", passive_deletes=False
    )

    @property
    def created_by_name(self) -> str:
        return self.creator.full_name

    @property
    def is_reversal(self) -> bool:
        return self.reversal_of_id is not None


class VoucherLine(Base):
    """One side of one posting. Exactly one of debit and credit is positive."""

    __tablename__ = "voucher_lines"
    __table_args__ = (
        UniqueConstraint("voucher_id", "line_no", name="one_voucher_line_per_number"),
        CheckConstraint("debit >= 0 AND credit >= 0 AND ((debit > 0) <> (credit > 0))", name="exactly_one_side"),
        Index("ix_voucher_lines_voucher_id", "voucher_id"),
        Index("ix_voucher_lines_account_id", "account_id"),
        Index("ix_voucher_lines_cost_center_id", "cost_center_id"),
        Index("ix_voucher_lines_project_id", "project_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    voucher_id: Mapped[int] = mapped_column(ForeignKey("vouchers.id"))
    line_no: Mapped[int] = mapped_column(SmallInteger)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"))
    debit: Mapped[Decimal] = mapped_column(MONEY, server_default=text("0"))
    credit: Mapped[Decimal] = mapped_column(MONEY, server_default=text("0"))
    description: Mapped[str | None] = mapped_column(String(500), default=None)
    cost_center_id: Mapped[int | None] = mapped_column(ForeignKey("cost_centers.id"), default=None)
    project_id: Mapped[int | None] = mapped_column(ForeignKey("projects.id"), default=None)

    account: Mapped[Account] = relationship(lazy="raise")

    @property
    def account_code(self) -> str:
        return self.account.code

    @property
    def account_name(self) -> str:
        return self.account.name


# What a voucher comes to, worked out from its lines whenever it is read. Never stored, so it cannot drift.
Voucher.total_debit = column_property(
    select(func.coalesce(func.sum(VoucherLine.debit), 0)).where(VoucherLine.voucher_id == Voucher.id).scalar_subquery()
)
Voucher.total_credit = column_property(
    select(func.coalesce(func.sum(VoucherLine.credit), 0)).where(VoucherLine.voucher_id == Voucher.id).scalar_subquery()
)


# The voucher that reverses this one, and the number of the one this reverses. Plain columns computed on read, so
# loading a reversal never reloads (and so never disturbs) the voucher it points at.
_reversal = aliased(Voucher)
_original = aliased(Voucher)
Voucher.reversed_by_id = column_property(
    select(_reversal.id).where(_reversal.reversal_of_id == Voucher.id).scalar_subquery()
)
Voucher.reversal_of_number = column_property(
    select(_original.number).where(_original.id == Voucher.reversal_of_id).scalar_subquery()
)
