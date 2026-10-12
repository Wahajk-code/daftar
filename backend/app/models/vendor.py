from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, Identity, Index, String, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UtcDateTime


class Vendor(Base):
    __tablename__ = "vendors"
    __table_args__ = (
        CheckConstraint(
            "NOT is_sales_tax_registered OR (length(btrim(coalesce(ntn, ''))) > 0"
            " AND length(btrim(coalesce(strn, ''))) > 0)",
            name="registered_has_ntn_and_strn",
        ),
        CheckConstraint(
            "(bank_account_encrypted IS NULL) = (bank_account_last4 IS NULL)", name="bank_account_parts_agree"
        ),
        CheckConstraint("length(btrim(name)) > 0", name="name_not_blank"),
        Index("uq_vendors_name_lower", func.lower(func.btrim(text("name"))), unique=True),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    is_sales_tax_registered: Mapped[bool] = mapped_column(server_default=text("false"))
    # The filer (ATL) flag is independent of sales tax registration; the two drive different withholding rates.
    is_filer: Mapped[bool] = mapped_column(server_default=text("false"))
    ntn: Mapped[str | None] = mapped_column(String(30), default=None)
    strn: Mapped[str | None] = mapped_column(String(30), default=None)
    contact_name: Mapped[str | None] = mapped_column(String(200), default=None)
    phone: Mapped[str | None] = mapped_column(String(40), default=None)
    email: Mapped[str | None] = mapped_column(String(254), default=None)
    address: Mapped[str | None] = mapped_column(String(500), default=None)
    bank_name: Mapped[str | None] = mapped_column(String(120), default=None)
    # The account number is encrypted at rest and never returned; only the last four digits are shown.
    bank_account_encrypted: Mapped[str | None] = mapped_column(String(500), default=None)
    bank_account_last4: Mapped[str | None] = mapped_column(String(4), default=None)
    is_active: Mapped[bool] = mapped_column(server_default=text("true"))
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    version: Mapped[int] = mapped_column(server_default=text("1"))
    __mapper_args__ = {"version_id_col": version}
    created_at: Mapped[datetime] = mapped_column(UtcDateTime, server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(UtcDateTime, server_default=text("now()"))

    @property
    def bank_account_masked(self) -> str | None:
        """What every response shows of the account number: its last four characters, never the rest."""
        return f"****{self.bank_account_last4}" if self.bank_account_last4 else None
