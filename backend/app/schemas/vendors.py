from typing import Annotated

from pydantic import BeforeValidator, Field, StringConstraints

from app.core.normalize import Email, collapse_spaces
from app.schemas.auth import Password
from app.schemas.base import RequestModel, ResponseModel, UtcInstant, blank_to_none

Name = Annotated[str, StringConstraints(min_length=1, max_length=200), BeforeValidator(collapse_spaces)]


def _optional(max_length: int, pattern: str | None = None) -> StringConstraints:
    return StringConstraints(max_length=max_length, pattern=pattern)


# Text that may be left out or blank (both mean "nothing"); its limits apply only when there is some.
# NTN and STRN are digits and hyphens, as FBR prints them: 1234567-8, 03-01-8700-123-45.
TaxNumber = Annotated[Annotated[str, _optional(20, r"^[0-9][0-9-]{5,18}[0-9]$")] | None, BeforeValidator(blank_to_none)]
ContactName = Annotated[Annotated[str, _optional(200)] | None, BeforeValidator(blank_to_none)]
Phone = Annotated[Annotated[str, _optional(40)] | None, BeforeValidator(blank_to_none)]
Address = Annotated[Annotated[str, _optional(500)] | None, BeforeValidator(blank_to_none)]
BankName = Annotated[Annotated[str, _optional(120)] | None, BeforeValidator(blank_to_none)]
AccountNumber = Annotated[Annotated[str, _optional(60)] | None, BeforeValidator(blank_to_none)]
OptionalEmail = Annotated[Email | None, BeforeValidator(blank_to_none)]


class VendorCreate(RequestModel):
    name: Name
    is_sales_tax_registered: bool = False
    is_filer: bool = False
    ntn: TaxNumber = None
    strn: TaxNumber = None
    contact_name: ContactName = None
    phone: Phone = None
    email: OptionalEmail = None
    address: Address = None
    bank_name: BankName = None
    bank_account_number: AccountNumber = None


class VendorUpdate(RequestModel):
    """The bank account has its own action, because changing it needs the password again."""

    name: Name | None = None
    is_sales_tax_registered: bool | None = None
    is_filer: bool | None = None
    ntn: TaxNumber = None
    strn: TaxNumber = None
    contact_name: ContactName = None
    phone: Phone = None
    email: OptionalEmail = None
    address: Address = None


class BankAccountChange(RequestModel):
    account_number: Annotated[str, Field(min_length=1, max_length=60)]
    bank_name: BankName = None
    current_password: Password


class VendorRead(ResponseModel):
    id: int
    name: str
    is_sales_tax_registered: bool
    is_filer: bool
    ntn: str | None
    strn: str | None
    contact_name: str | None
    phone: str | None
    email: str | None
    address: str | None
    bank_name: str | None
    bank_account_masked: str | None
    is_active: bool
    version: int
    created_at: UtcInstant
    updated_at: UtcInstant
