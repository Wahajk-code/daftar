"""Reference data and image bytes for the document tests."""

import os
from dataclasses import dataclass
from io import BytesIO
from typing import Any

from PIL import Image
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.enums import AccountType, ProjectKind
from app.models.master import Account, Category, CostCenter, Project
from app.models.user import User
from app.models.vendor import Vendor


@dataclass
class Lookups:
    category: Category
    other_category: Category
    centres: list[CostCenter]
    project: Project
    product: Project
    vendors: dict[str, Vendor]  # keyed "reg_filer", "reg_nonfiler", "unreg_filer", "unreg_nonfiler"


def create_lookups(session: Session, owner: User) -> Lookups:
    def expense_account(code: str, name: str) -> Account:
        """A scratch database arrives with the starting chart, the fast one without it: use what is there."""
        existing = session.scalars(select(Account).where(Account.code == code)).one_or_none()
        if existing is not None:
            return existing
        created = Account(code=code, name=name, type=AccountType.EXPENSE)
        session.add(created)
        session.flush()
        return created

    rent = expense_account("5100", "Rent")
    supplies = expense_account("5600", "Office Supplies")
    category = Category(name="Office rent", account_id=rent.id)
    other = Category(name="Stationery", account_id=supplies.id)
    centres = [
        CostCenter(code=code, name=name) for code, name in (("HO", "Head Office"), ("OPS", "Operations"), ("IT", "IT"))
    ]
    project = Project(code="PRJ-001", name="Gulberg Fit-out", kind=ProjectKind.PROJECT)
    product = Project(code="SKU-1", name="Cable drum", kind=ProjectKind.PRODUCT)
    session.add_all([category, other, *centres, project, product])
    vendors = {
        "reg_filer": Vendor(
            name="Ravi Stationers",
            is_sales_tax_registered=True,
            is_filer=True,
            ntn="1234567-8",
            strn="03-01-8700-123-45",
            created_by=owner.id,
        ),
        "reg_nonfiler": Vendor(
            name="Zarai Traders",
            is_sales_tax_registered=True,
            is_filer=False,
            ntn="7654321-2",
            strn="03-01-8700-765-43",
            created_by=owner.id,
        ),
        "unreg_filer": Vendor(
            name="Al-Madina Printers",
            is_sales_tax_registered=False,
            is_filer=True,
            ntn="9988776-1",
            created_by=owner.id,
        ),
        "unreg_nonfiler": Vendor(
            name="Haji Noor Transport", is_sales_tax_registered=False, is_filer=False, created_by=owner.id
        ),
    }
    session.add_all(vendors.values())
    session.commit()
    return Lookups(category, other, centres, project, product, vendors)


def direct_expense(lookups: Lookups, **overrides: Any) -> dict[str, Any]:
    return {
        "expense_type": "direct",
        "category_id": lookups.category.id,
        "amount": "1500.00",
        "tax_amount": "0.00",
        "payment_method": "cash",
        "description": "Printer paper for the head office",
        "cost_center_id": lookups.centres[0].id,
        **overrides,
    }


def indirect_expense(
    lookups: Lookups, lines: list[dict[str, Any]], method: str = "percentage", **overrides: Any
) -> dict[str, Any]:
    return {
        "expense_type": "indirect",
        "category_id": lookups.category.id,
        "amount": "100.00",
        "tax_amount": "0.00",
        "payment_method": "bank_transfer",
        "description": "Shared electricity bill",
        "allocation": {"method": method, "lines": lines},
        **overrides,
    }


def purchase_body(vendor: Vendor, lines: list[dict[str, Any]] | None = None, **overrides: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "vendor_id": vendor.id,
        "description": "Quarterly supplies",
        "lines": lines if lines is not None else [purchase_line()],
        **overrides,
    }
    if vendor.is_sales_tax_registered:
        body.setdefault("invoice_number", "INV-2026-0042")
    return body


def purchase_line(**overrides: Any) -> dict[str, Any]:
    return {
        "item": "A4 paper, 500 sheets",
        "category": "goods",
        "quantity": "10",
        "rate": "1000.00",
        "sales_tax_bp": 0,
        **overrides,
    }


# Images --------------------------------------------------------------------------------------------------------------


def image_bytes(kind: str = "JPEG", size: tuple[int, int] = (64, 48), **save_options: Any) -> bytes:
    out = BytesIO()
    Image.new("RGB", size, (200, 120, 40)).save(out, format=kind, **save_options)
    return out.getvalue()


def noisy_png(side: int = 400) -> bytes:
    """A PNG that does not compress, so a test can make a large upload without a large file in the repository."""
    out = BytesIO()
    Image.frombytes("RGB", (side, side), os.urandom(side * side * 3)).save(out, format="PNG")
    return out.getvalue()


def jpeg_with_metadata() -> bytes:
    """A JPEG carrying a camera make, a timestamp and a GPS position, the way a phone writes one."""
    exif = Image.Exif()
    exif[0x010F] = "SecretCameraMaker"
    exif[0x0132] = "2026:10:12 14:05:00"
    gps = exif.get_ifd(0x8825)
    gps[1] = "N"
    gps[2] = (31.0, 33.0, 0.0)
    gps[3] = "E"
    gps[4] = (74.0, 21.0, 0.0)
    out = BytesIO()
    Image.new("RGB", (64, 48), (10, 200, 90)).save(out, format="JPEG", exif=exif)
    return out.getvalue()


# Ledger --------------------------------------------------------------------------------------------------------------


@dataclass
class Ledger:
    """Accounts a voucher can post to, with the posting accounts pointed at them."""

    expense: Any  # 5100 Rent
    other_expense: Any  # 5600 Office Supplies
    cash: Any
    bank: Any
    input_tax: Any
    sales_tax_withheld: Any
    income_tax_withheld: Any
    revenue: Any
    parent: Any  # a parent account: not postable


def create_ledger(session: Session, lookups: Lookups, admin: User, skip: tuple[str, ...] = ()) -> Ledger:
    """`skip` leaves the named posting keys unset, as on an install nobody has configured."""
    from app.core.enums import PostingKey
    from app.models.master import PostingAccount

    def account(code: str, name: str, kind: AccountType, **extra: Any) -> Account:
        row = Account(code=code, name=name, type=kind, **extra)
        session.add(row)
        session.flush()
        return row

    expense = session.scalars(select(Account).where(Account.code == "5100")).one()
    other = session.scalars(select(Account).where(Account.code == "5600")).one()
    ledger = Ledger(
        expense=expense,
        other_expense=other,
        cash=account("1100", "Cash in Hand", AccountType.ASSET),
        bank=account("1200", "Bank - Meezan Current", AccountType.ASSET),
        input_tax=account("1300", "Advance Tax Receivable", AccountType.ASSET),
        sales_tax_withheld=account("2200", "Sales Tax Payable", AccountType.LIABILITY),
        income_tax_withheld=account("2300", "Withholding Tax Payable", AccountType.LIABILITY),
        revenue=account("4100", "Service Revenue", AccountType.INCOME),
        parent=account("1000", "Assets", AccountType.ASSET, is_postable=False),
    )
    for key, row in (
        (PostingKey.CASH, ledger.cash),
        (PostingKey.BANK, ledger.bank),
        (PostingKey.INPUT_SALES_TAX, ledger.input_tax),
        (PostingKey.SALES_TAX_WITHHELD, ledger.sales_tax_withheld),
        (PostingKey.INCOME_TAX_WITHHELD, ledger.income_tax_withheld),
    ):
        if key.value not in skip:
            session.add(PostingAccount(key=key, account_id=row.id, updated_by=admin.id))
    session.commit()
    return ledger


def voucher_body(ledger: Ledger, amount: str = "100.00", **overrides: Any) -> dict[str, Any]:
    """A balanced payment voucher: the expense debited, cash credited."""
    return {
        "voucher_type": "PV",
        "description": "Office rent for October",
        "lines": [
            {"account_id": ledger.expense.id, "debit": amount, "description": "Rent"},
            {"account_id": ledger.cash.id, "credit": amount},
        ],
        **overrides,
    }
