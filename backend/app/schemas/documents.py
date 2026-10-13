"""Schemas for expenses, purchases, attachments and the approval history."""

from datetime import date
from decimal import Decimal
from typing import Annotated, Literal, Self

from pydantic import BaseModel, BeforeValidator, Field, PlainSerializer, StringConstraints, model_validator

from app.core import money
from app.core.duplicates import DuplicateKind
from app.core.enums import (
    AllocationMethod,
    DocumentStatus,
    DocumentType,
    ExpenseType,
    PaymentMethod,
    PurchaseKind,
    TaxCategory,
)
from app.core.normalize import collapse_spaces
from app.schemas.base import Money, PositiveMoney, RequestModel, ResponseModel, SignedMoney, UtcInstant, blank_to_none
from app.schemas.vouchers import VoucherRef


def _parse_quantity(value: object) -> Decimal:
    try:
        return money.parse_quantity(value)
    except money.MoneyError as exc:
        raise ValueError(str(exc)) from exc


Quantity = Annotated[
    Decimal,
    BeforeValidator(_parse_quantity),
    PlainSerializer(money.quantity_to_json, return_type=str, when_used="json"),
]
Description = Annotated[str, StringConstraints(max_length=1000)]
OptionalComment = Annotated[Annotated[str, StringConstraints(max_length=1000)] | None, BeforeValidator(blank_to_none)]
Item = Annotated[str, StringConstraints(min_length=1, max_length=200), BeforeValidator(collapse_spaces)]
Action = Literal["submit", "approve", "reject", "reopen"]


class TransitionRequest(RequestModel):
    comment: OptionalComment = None


# Expenses ------------------------------------------------------------------------------------------------------------


class AllocationLineIn(RequestModel):
    cost_center_id: int
    basis_points: int | None = Field(default=None, ge=0, le=10_000)
    amount: Money | None = None


class AllocationIn(RequestModel):
    """How an indirect expense is split. Percentages are basis points (10,000 is 100%); fixed amounts are exact."""

    method: AllocationMethod
    lines: Annotated[list[AllocationLineIn], Field(min_length=1, max_length=50)]

    @model_validator(mode="after")
    def _lines_match_the_method(self) -> Self:
        for index, line in enumerate(self.lines):
            if self.method is AllocationMethod.PERCENTAGE and (line.basis_points is None or line.amount is not None):
                raise ValueError(f"line {index + 1}: a percentage split gives basis_points and no amount")
            if self.method is AllocationMethod.FIXED and (line.amount is None or line.basis_points is not None):
                raise ValueError(f"line {index + 1}: a fixed split gives an amount and no basis_points")
        centres = [line.cost_center_id for line in self.lines]
        if len(set(centres)) != len(centres):
            raise ValueError("each cost centre may appear once")
        return self


class ExpenseCreate(RequestModel):
    expense_type: ExpenseType
    document_date: date | None = Field(default=None, description="Defaults to today in the display zone.")
    category_id: int
    amount: PositiveMoney = Field(description="Gross of tax: tax is recorded for reporting and never added on top.")
    tax_amount: Money = Decimal("0.00")
    payment_method: PaymentMethod
    description: Description = ""
    project_id: int | None = None
    cost_center_id: int | None = None
    allocation: AllocationIn | None = None


class ExpenseUpdate(RequestModel):
    expense_type: ExpenseType | None = None
    document_date: date | None = None
    category_id: int | None = None
    amount: PositiveMoney | None = None
    tax_amount: Money | None = None
    payment_method: PaymentMethod | None = None
    description: Description | None = None
    project_id: int | None = None
    cost_center_id: int | None = None
    allocation: AllocationIn | None = None


class AllocationRead(ResponseModel):
    cost_center_id: int
    cost_center_code: str
    basis_points: int | None
    amount: Money

    @model_validator(mode="before")
    @classmethod
    def _from_row(cls, data: object) -> object:
        if isinstance(data, dict):
            return data
        return {
            "cost_center_id": data.cost_center_id,  # type: ignore[attr-defined]
            "cost_center_code": data.cost_center.code,  # type: ignore[attr-defined]
            "basis_points": data.basis_points,  # type: ignore[attr-defined]
            "amount": data.amount,  # type: ignore[attr-defined]
        }


class ExpenseRead(ResponseModel):
    id: int
    expense_type: ExpenseType
    status: DocumentStatus
    document_date: date
    category_id: int
    category_name: str
    amount: Money
    tax_amount: Money
    currency: str
    payment_method: PaymentMethod
    description: str
    project_id: int | None
    cost_center_id: int | None
    allocation_method: AllocationMethod | None
    allocations: list[AllocationRead]
    voucher: VoucherRef | None = None
    created_by: int
    created_by_name: str
    version: int
    actions: list[Action] = []
    created_at: UtcInstant
    updated_at: UtcInstant


class AllocationPreviewRequest(RequestModel):
    amount: PositiveMoney
    allocation: AllocationIn


class AllocationPreviewRead(BaseModel):
    """What the split comes to as typed. It never fails: a split that does not add up reports how far short it is."""

    complete: bool
    lines: list[AllocationRead]
    allocated: Money
    remaining: SignedMoney = Field(description="The part of the amount not yet allocated, or the excess if negative.")
    remaining_basis_points: int | None = Field(description="Percentage splits only: 10,000 less what was given.")


# Purchases -----------------------------------------------------------------------------------------------------------


class PurchaseLineIn(RequestModel):
    item: Item
    category: TaxCategory = Field(description="The kind of payment; it selects the income tax withholding rate.")
    quantity: Quantity
    rate: PositiveMoney = Field(description="Price per unit, excluding sales tax.")
    sales_tax_bp: int = Field(
        default=0, ge=0, le=10_000, description="Sales tax charged on the invoice, in basis points."
    )


class PurchaseCreate(RequestModel):
    vendor_id: int
    document_date: date | None = None
    invoice_number: Annotated[
        Annotated[str, StringConstraints(max_length=60)] | None, BeforeValidator(blank_to_none)
    ] = None
    description: Description = ""
    lines: Annotated[list[PurchaseLineIn], Field(min_length=1, max_length=100)]


class PurchaseUpdate(RequestModel):
    vendor_id: int | None = None
    document_date: date | None = None
    invoice_number: Annotated[
        Annotated[str, StringConstraints(max_length=60)] | None, BeforeValidator(blank_to_none)
    ] = None
    description: Description | None = None
    lines: Annotated[list[PurchaseLineIn], Field(min_length=1, max_length=100)] | None = None


class PurchasePreviewRequest(RequestModel):
    vendor_id: int
    document_date: date | None = None
    lines: Annotated[list[PurchaseLineIn], Field(min_length=1, max_length=100)]


class PurchaseLineRead(ResponseModel):
    line_no: int
    item: str
    category: TaxCategory
    quantity: Quantity
    rate: Money
    sales_tax_bp: int
    subtotal: Money
    sales_tax: Money
    gross: Money
    sales_withholding_rule_id: int
    sales_withholding_bp: int
    sales_tax_withheld: Money
    income_withholding_rule_id: int
    income_withholding_bp: int
    income_tax_withheld: Money
    payable: Money


class PurchaseTotals(BaseModel):
    subtotal: Money
    sales_tax_total: Money
    gross_total: Money
    sales_tax_withheld: Money
    income_tax_withheld: Money
    payable: Money


class PurchaseRead(ResponseModel):
    id: int
    status: DocumentStatus
    vendor_id: int
    vendor_name: str
    document_date: date
    document_kind: PurchaseKind
    invoice_number: str | None
    description: str
    vendor_registered: bool
    vendor_filer: bool
    currency: str
    subtotal: Money
    sales_tax_total: Money
    gross_total: Money
    sales_tax_withheld: Money
    income_tax_withheld: Money
    payable: Money
    lines: list[PurchaseLineRead]
    voucher: VoucherRef | None = None
    created_by: int
    created_by_name: str
    version: int
    actions: list[Action] = []
    created_at: UtcInstant
    updated_at: UtcInstant


class PurchasePreviewRead(BaseModel):
    document_kind: PurchaseKind
    vendor_registered: bool
    vendor_filer: bool
    lines: list[PurchaseLineRead]
    totals: PurchaseTotals


# Attachments and history ---------------------------------------------------------------------------------------------


class AttachmentRead(ResponseModel):
    id: int
    content_type: str
    size_bytes: int
    sha256: str
    original_name: str
    uploaded_by: int
    created_at: UtcInstant


class HistoryItem(ResponseModel):
    id: int
    document_type: DocumentType
    action: str
    from_status: DocumentStatus | None
    to_status: DocumentStatus
    actor_id: int
    actor_name: str
    comment: str | None
    created_at: UtcInstant


class DuplicateWarningRead(ResponseModel):
    """A document that resembles this one. Advice only: nothing is blocked."""

    kind: DuplicateKind
    document_type: DocumentType
    document_id: int
    status: DocumentStatus
    document_date: date
    amount: Money
    reason: str
