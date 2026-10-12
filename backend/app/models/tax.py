from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    ForeignKey,
    Identity,
    Index,
    SmallInteger,
    String,
    literal_column,
    text,
)
from sqlalchemy.dialects.postgresql import ExcludeConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.enums import TaxCategory, TaxType
from app.models.base import Base, UtcDateTime, pg_enum


class TaxRule(Base):
    """A withholding rate for a kind of supplier and payment over a range of dates.

    Sales tax withholding depends on the supplier's registration, so `supplier_filer` is fixed at false on those rows;
    income tax withholding (section 153) depends on filer status, so `supplier_registered` is fixed at false on those.
    That keeps the exclusion constraint meaningful: a nullable column would never conflict. Rates are configuration:
    the resolved rate and rule id are copied onto each purchase line, so editing a rule never changes a saved document.
    """

    __tablename__ = "tax_rules"
    __table_args__ = (
        CheckConstraint("rate_bp BETWEEN 0 AND 10000", name="rate_in_range"),
        CheckConstraint("effective_to IS NULL OR effective_from <= effective_to", name="dates_in_order"),
        CheckConstraint("length(btrim(source)) > 0", name="source_not_blank"),
        CheckConstraint(
            "(tax_type = 'sales_tax_withholding' AND supplier_filer = false)"
            " OR (tax_type = 'income_tax_withholding' AND supplier_registered = false)",
            name="only_the_relevant_flag",
        ),
        ExcludeConstraint(
            ("tax_type", "="),
            ("supplier_registered", "="),
            ("supplier_filer", "="),
            ("category", "="),
            (literal_column("daterange(effective_from, effective_to, '[]')"), "&&"),
            using="gist",
            name="no_overlapping_rules",
        ),
        Index("ix_tax_rules_lookup", "tax_type", "effective_from"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    tax_type: Mapped[TaxType] = mapped_column(pg_enum(TaxType, "tax_type"))
    supplier_registered: Mapped[bool]
    supplier_filer: Mapped[bool]
    category: Mapped[TaxCategory] = mapped_column(pg_enum(TaxCategory, "tax_category"), server_default=text("'any'"))
    rate_bp: Mapped[int] = mapped_column(SmallInteger)
    effective_from: Mapped[date]
    effective_to: Mapped[date | None] = mapped_column(default=None)
    source: Mapped[str] = mapped_column(String(500))
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), default=None)
    version: Mapped[int] = mapped_column(server_default=text("1"))
    __mapper_args__ = {"version_id_col": version}
    created_at: Mapped[datetime] = mapped_column(UtcDateTime, server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(UtcDateTime, server_default=text("now()"))
