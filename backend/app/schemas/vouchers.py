"""Schemas for vouchers, balance checks, posting and voiding."""

from datetime import date
from decimal import Decimal
from typing import Annotated, Literal, Self

from pydantic import BaseModel, BeforeValidator, Field, StringConstraints, model_validator

from app.core.enums import DocumentStatus, PaymentMethod, VoucherType
from app.schemas.base import Money, RequestModel, ResponseModel, SignedMoney, UtcInstant, blank_to_none

Narration = Annotated[str, StringConstraints(max_length=1000)]
LineNote = Annotated[Annotated[str, StringConstraints(max_length=500)] | None, BeforeValidator(blank_to_none)]
Reason = Annotated[str, StringConstraints(min_length=1, max_length=1000)]


class VoucherLineIn(RequestModel):
    """One side of one posting: an account and either a debit or a credit, never both and never neither."""

    account_id: int
    debit: Money = Decimal("0.00")
    credit: Money = Decimal("0.00")
    description: LineNote = None
    cost_center_id: int | None = None
    project_id: int | None = None

    @model_validator(mode="after")
    def _exactly_one_side(self) -> Self:
        if (self.debit > 0) == (self.credit > 0):
            raise ValueError("a line has either a debit or a credit, and the amount must be more than zero")
        return self


class VoucherCreate(RequestModel):
    voucher_type: VoucherType
    document_date: date | None = Field(default=None, description="Defaults to today in the display zone.")
    description: Narration = ""
    lines: Annotated[list[VoucherLineIn], Field(min_length=2, max_length=200)]


class VoucherUpdate(RequestModel):
    document_date: date | None = None
    description: Narration | None = None
    lines: Annotated[list[VoucherLineIn], Field(min_length=2, max_length=200)] | None = None


class BalanceCheckRequest(RequestModel):
    lines: Annotated[list[VoucherLineIn], Field(max_length=200)]


class OffsettingLine(BaseModel):
    side: Literal["debit", "credit"]
    amount: Money


class BalanceCheckRead(BaseModel):
    """Where the lines stand. When they do not balance, `offsetting_line` is the one line that would make them."""

    total_debit: Money
    total_credit: Money
    difference: SignedMoney = Field(description="Debits less credits.")
    balanced: bool
    offsetting_line: OffsettingLine | None


class VoucherLineRead(ResponseModel):
    line_no: int
    account_id: int
    account_code: str
    account_name: str
    debit: Money
    credit: Money
    description: str | None
    cost_center_id: int | None
    project_id: int | None


class VoucherRef(ResponseModel):
    """Enough to link to a voucher from the expense or purchase it was generated from (and back)."""

    id: int
    voucher_type: VoucherType
    number: str | None
    status: DocumentStatus


class VoucherRead(ResponseModel):
    id: int
    voucher_type: VoucherType
    status: DocumentStatus
    number: str | None
    document_date: date
    description: str
    lines: list[VoucherLineRead]
    total_debit: Money
    total_credit: Money
    expense_id: int | None
    purchase_id: int | None
    reversal_of_id: int | None
    reversal_of_number: str | None
    reversed_by_id: int | None
    void_reason: str | None
    voided_at: UtcInstant | None
    created_by: int
    created_by_name: str
    version: int
    actions: list[str] = []
    created_at: UtcInstant
    updated_at: UtcInstant


class VoidRequest(RequestModel):
    reason: Reason


class VoidResult(BaseModel):
    """The voucher now void and the reversing voucher that cancels it."""

    voucher: VoucherRead
    reversal: VoucherRead


class PurchaseVoucherRequest(RequestModel):
    """What the accountant decides when paying a purchase: which expense category it belongs to, and how it is paid."""

    category_id: int
    payment_method: PaymentMethod
