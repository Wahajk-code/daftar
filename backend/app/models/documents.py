"""Expenses, purchases, their lines, attachments and the shared approval history."""

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    ForeignKey,
    Identity,
    Index,
    Numeric,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.enums import (
    AllocationMethod,
    DocumentStatus,
    DocumentType,
    ExpenseType,
    PaymentMethod,
    PurchaseKind,
    TaxCategory,
)
from app.models.base import Base, UtcDateTime, pg_enum
from app.models.master import Category, CostCenter, Project
from app.models.user import User
from app.models.vendor import Vendor

MONEY = Numeric(14, 2)
QUANTITY = Numeric(14, 3)


class Expense(Base):
    __tablename__ = "expenses"
    __table_args__ = (
        CheckConstraint("amount > 0", name="amount_positive"),
        CheckConstraint("tax_amount >= 0 AND tax_amount <= amount", name="tax_within_amount"),
        # Direct spending names where it went; indirect spending names nothing here and is split over cost centres.
        CheckConstraint(
            "(expense_type = 'direct' AND (project_id IS NOT NULL OR cost_center_id IS NOT NULL)"
            " AND allocation_method IS NULL)"
            " OR (expense_type = 'indirect' AND project_id IS NULL AND cost_center_id IS NULL)",
            name="direct_has_attribution_indirect_has_none",
        ),
        Index("ix_expenses_created_by", "created_by"),
        Index("ix_expenses_status", "status"),
        Index("ix_expenses_document_date", "document_date"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    expense_type: Mapped[ExpenseType] = mapped_column(pg_enum(ExpenseType, "expense_type"))
    status: Mapped[DocumentStatus] = mapped_column(
        pg_enum(DocumentStatus, "document_status", create_type=False), server_default=text("'draft'")
    )
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    document_date: Mapped[date] = mapped_column(Date)
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"))
    amount: Mapped[Decimal] = mapped_column(MONEY)
    tax_amount: Mapped[Decimal] = mapped_column(MONEY, server_default=text("0"))
    currency: Mapped[str] = mapped_column(String(3), server_default=text("'PKR'"))
    payment_method: Mapped[PaymentMethod] = mapped_column(pg_enum(PaymentMethod, "payment_method"))
    description: Mapped[str] = mapped_column(String(1000), server_default=text("''"))
    project_id: Mapped[int | None] = mapped_column(ForeignKey("projects.id"), default=None)
    cost_center_id: Mapped[int | None] = mapped_column(ForeignKey("cost_centers.id"), default=None)
    allocation_method: Mapped[AllocationMethod | None] = mapped_column(
        pg_enum(AllocationMethod, "allocation_method"), default=None
    )
    version: Mapped[int] = mapped_column(server_default=text("1"))
    __mapper_args__ = {"version_id_col": version}
    created_at: Mapped[datetime] = mapped_column(UtcDateTime, server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(UtcDateTime, server_default=text("now()"))

    creator: Mapped[User] = relationship(lazy="raise")
    category: Mapped[Category] = relationship(lazy="raise")
    project: Mapped[Project | None] = relationship(lazy="raise")
    cost_center: Mapped[CostCenter | None] = relationship(lazy="raise")
    allocations: Mapped[list["ExpenseAllocation"]] = relationship(
        lazy="raise", order_by="ExpenseAllocation.id", cascade="all, delete-orphan", passive_deletes=False
    )

    @property
    def created_by_name(self) -> str:
        return self.creator.full_name

    @property
    def category_name(self) -> str:
        return self.category.name


class ExpenseAllocation(Base):
    """One cost centre's share of an indirect expense. Percentage splits keep their basis points; every row keeps the
    exact amount, worked out once by the largest-remainder rule."""

    __tablename__ = "expense_allocations"
    __table_args__ = (
        UniqueConstraint("expense_id", "cost_center_id", name="one_row_per_cost_center"),
        CheckConstraint("amount >= 0", name="amount_not_negative"),
        CheckConstraint("basis_points IS NULL OR basis_points BETWEEN 0 AND 10000", name="basis_points_in_range"),
        Index("ix_expense_allocations_cost_center_id", "cost_center_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    expense_id: Mapped[int] = mapped_column(ForeignKey("expenses.id"))
    cost_center_id: Mapped[int] = mapped_column(ForeignKey("cost_centers.id"))
    basis_points: Mapped[int | None] = mapped_column(SmallInteger, default=None)
    amount: Mapped[Decimal] = mapped_column(MONEY)

    cost_center: Mapped[CostCenter] = relationship(lazy="raise")


class Purchase(Base):
    __tablename__ = "purchases"
    __table_args__ = (
        CheckConstraint(
            "(vendor_registered AND document_kind = 'tax_invoice')"
            " OR (NOT vendor_registered AND document_kind = 'purchase_memo')",
            name="kind_follows_registration",
        ),
        CheckConstraint(
            "document_kind <> 'tax_invoice' OR length(btrim(coalesce(invoice_number, ''))) > 0",
            name="tax_invoice_has_a_number",
        ),
        CheckConstraint("payable >= 0", name="payable_not_negative"),
        CheckConstraint("gross_total = subtotal + sales_tax_total", name="gross_is_subtotal_plus_tax"),
        CheckConstraint(
            "payable = gross_total - sales_tax_withheld - income_tax_withheld",
            name="payable_is_gross_less_withholdings",
        ),
        Index("ix_purchases_vendor_id", "vendor_id"),
        Index("ix_purchases_created_by", "created_by"),
        Index("ix_purchases_status", "status"),
        Index("ix_purchases_document_date", "document_date"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    status: Mapped[DocumentStatus] = mapped_column(
        pg_enum(DocumentStatus, "document_status", create_type=False), server_default=text("'draft'")
    )
    vendor_id: Mapped[int] = mapped_column(ForeignKey("vendors.id"))
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    document_date: Mapped[date] = mapped_column(Date)
    document_kind: Mapped[PurchaseKind] = mapped_column(pg_enum(PurchaseKind, "purchase_kind"))
    invoice_number: Mapped[str | None] = mapped_column(String(60), default=None)
    description: Mapped[str] = mapped_column(String(1000), server_default=text("''"))
    # The vendor's flags as they were when this purchase was written; a later edit to the vendor cannot change it.
    vendor_registered: Mapped[bool] = mapped_column(Boolean)
    vendor_filer: Mapped[bool] = mapped_column(Boolean)
    currency: Mapped[str] = mapped_column(String(3), server_default=text("'PKR'"))
    subtotal: Mapped[Decimal] = mapped_column(MONEY)
    sales_tax_total: Mapped[Decimal] = mapped_column(MONEY)
    gross_total: Mapped[Decimal] = mapped_column(MONEY)
    sales_tax_withheld: Mapped[Decimal] = mapped_column(MONEY)
    income_tax_withheld: Mapped[Decimal] = mapped_column(MONEY)
    payable: Mapped[Decimal] = mapped_column(MONEY)
    version: Mapped[int] = mapped_column(server_default=text("1"))
    __mapper_args__ = {"version_id_col": version}
    created_at: Mapped[datetime] = mapped_column(UtcDateTime, server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(UtcDateTime, server_default=text("now()"))

    creator: Mapped[User] = relationship(lazy="raise")
    vendor: Mapped[Vendor] = relationship(lazy="raise")
    lines: Mapped[list["PurchaseLine"]] = relationship(
        lazy="raise", order_by="PurchaseLine.line_no", cascade="all, delete-orphan", passive_deletes=False
    )

    @property
    def created_by_name(self) -> str:
        return self.creator.full_name

    @property
    def vendor_name(self) -> str:
        return self.vendor.name


class PurchaseLine(Base):
    """A line with every figure computed on the server, and the withholding rate and rule it was given, copied here."""

    __tablename__ = "purchase_lines"
    __table_args__ = (
        UniqueConstraint("purchase_id", "line_no", name="one_row_per_line_number"),
        CheckConstraint("quantity > 0 AND rate > 0", name="quantity_and_rate_positive"),
        CheckConstraint("subtotal > 0", name="subtotal_positive"),
        CheckConstraint("sales_tax_bp BETWEEN 0 AND 10000", name="sales_tax_in_range"),
        CheckConstraint("gross = subtotal + sales_tax", name="gross_is_subtotal_plus_tax"),
        CheckConstraint(
            "payable = gross - sales_tax_withheld - income_tax_withheld", name="payable_is_gross_less_withholdings"
        ),
        CheckConstraint("payable >= 0", name="payable_not_negative"),
        Index("ix_purchase_lines_purchase_id", "purchase_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    purchase_id: Mapped[int] = mapped_column(ForeignKey("purchases.id"))
    line_no: Mapped[int] = mapped_column(SmallInteger)
    item: Mapped[str] = mapped_column(String(200))
    category: Mapped[TaxCategory] = mapped_column(pg_enum(TaxCategory, "tax_category", create_type=False))
    quantity: Mapped[Decimal] = mapped_column(QUANTITY)
    rate: Mapped[Decimal] = mapped_column(MONEY)
    sales_tax_bp: Mapped[int] = mapped_column(SmallInteger)
    subtotal: Mapped[Decimal] = mapped_column(MONEY)
    sales_tax: Mapped[Decimal] = mapped_column(MONEY)
    gross: Mapped[Decimal] = mapped_column(MONEY)
    sales_withholding_rule_id: Mapped[int] = mapped_column(ForeignKey("tax_rules.id"))
    sales_withholding_bp: Mapped[int] = mapped_column(SmallInteger)
    sales_tax_withheld: Mapped[Decimal] = mapped_column(MONEY)
    income_withholding_rule_id: Mapped[int] = mapped_column(ForeignKey("tax_rules.id"))
    income_withholding_bp: Mapped[int] = mapped_column(SmallInteger)
    income_tax_withheld: Mapped[Decimal] = mapped_column(MONEY)
    payable: Mapped[Decimal] = mapped_column(MONEY)


class Attachment(Base):
    """A receipt or supporting image on an expense or a purchase. The file itself is in the store under a random key."""

    __tablename__ = "attachments"
    __table_args__ = (
        CheckConstraint("num_nonnulls(expense_id, purchase_id) = 1", name="exactly_one_parent"),
        CheckConstraint("size_bytes > 0", name="size_positive"),
        CheckConstraint("length(sha256) = 64", name="sha256_is_64_hex"),
        CheckConstraint("(removed_at IS NULL) = (removed_by IS NULL)", name="removal_has_both_parts"),
        Index("ix_attachments_expense_id", "expense_id"),
        Index("ix_attachments_purchase_id", "purchase_id"),
        Index("ix_attachments_sha256", "sha256"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    expense_id: Mapped[int | None] = mapped_column(ForeignKey("expenses.id"), default=None)
    purchase_id: Mapped[int | None] = mapped_column(ForeignKey("purchases.id"), default=None)
    storage_key: Mapped[str] = mapped_column(String(200), unique=True)
    content_type: Mapped[str] = mapped_column(String(50))
    size_bytes: Mapped[int] = mapped_column(BigInteger)
    sha256: Mapped[str] = mapped_column(String(64))
    original_name: Mapped[str] = mapped_column(String(255))
    uploaded_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(UtcDateTime)
    removed_at: Mapped[datetime | None] = mapped_column(UtcDateTime, default=None)
    removed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), default=None)


class DocumentEvent(Base):
    """The approval history, one table for expenses, purchases and vouchers. Append only."""

    __tablename__ = "document_events"
    __table_args__ = (Index("ix_document_events_document", "document_type", "document_id", "id"),)

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    document_type: Mapped[DocumentType] = mapped_column(pg_enum(DocumentType, "document_type"))
    document_id: Mapped[int] = mapped_column(BigInteger)
    action: Mapped[str] = mapped_column(String(40))
    from_status: Mapped[DocumentStatus | None] = mapped_column(
        pg_enum(DocumentStatus, "document_status", create_type=False), default=None
    )
    to_status: Mapped[DocumentStatus] = mapped_column(pg_enum(DocumentStatus, "document_status", create_type=False))
    actor_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    comment: Mapped[str | None] = mapped_column(Text, default=None)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime)

    actor: Mapped[User] = relationship(lazy="raise")

    @property
    def actor_name(self) -> str:
        return self.actor.full_name
