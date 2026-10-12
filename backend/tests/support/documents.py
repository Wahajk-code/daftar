"""Reference data and image bytes for the document tests."""

import os
from dataclasses import dataclass
from io import BytesIO
from typing import Any

from PIL import Image
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
    rent = Account(code="5100", name="Rent", type=AccountType.EXPENSE)
    supplies = Account(code="5600", name="Office Supplies", type=AccountType.EXPENSE)
    session.add_all([rent, supplies])
    session.flush()
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
