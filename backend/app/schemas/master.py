"""Schemas for the chart of accounts, categories, cost centres, projects, periods, posting accounts and tax rules."""

from datetime import date
from typing import Annotated, Literal

from pydantic import BeforeValidator, Field, StringConstraints, model_validator

from app.core.enums import AccountType, PostingKey, ProjectKind, TaxCategory, TaxType
from app.core.normalize import collapse_spaces
from app.schemas.base import RequestModel, ResponseModel, UtcInstant

Code = Annotated[str, StringConstraints(pattern=r"^[0-9A-Za-z.-]{1,20}$", to_upper=True)]
Name = Annotated[str, StringConstraints(min_length=1, max_length=200), BeforeValidator(collapse_spaces)]


# Accounts ------------------------------------------------------------------------------------------------------------


class AccountCreate(RequestModel):
    code: Code
    name: Name
    type: AccountType
    parent_id: int | None = None
    is_postable: bool = True


class AccountUpdate(RequestModel):
    name: Name | None = None
    is_postable: bool | None = None


class AccountRead(ResponseModel):
    id: int
    code: str
    name: str
    type: AccountType
    parent_id: int | None
    is_postable: bool
    is_active: bool
    version: int
    created_at: UtcInstant
    updated_at: UtcInstant


# Categories, cost centres, projects ----------------------------------------------------------------------------------


class CategoryCreate(RequestModel):
    name: Name
    account_id: int


class CategoryUpdate(RequestModel):
    name: Name | None = None
    account_id: int | None = None


class CategoryRead(ResponseModel):
    id: int
    name: str
    account_id: int
    is_active: bool
    version: int
    created_at: UtcInstant
    updated_at: UtcInstant


class CostCenterCreate(RequestModel):
    code: Code
    name: Name


class CostCenterUpdate(RequestModel):
    name: Name | None = None


class CostCenterRead(ResponseModel):
    id: int
    code: str
    name: str
    is_active: bool
    version: int
    created_at: UtcInstant
    updated_at: UtcInstant


class ProjectCreate(RequestModel):
    code: Code
    name: Name
    kind: ProjectKind


class ProjectUpdate(RequestModel):
    name: Name | None = None


class ProjectRead(ResponseModel):
    id: int
    code: str
    name: str
    kind: ProjectKind
    is_active: bool
    version: int
    created_at: UtcInstant
    updated_at: UtcInstant


# Periods and posting accounts ----------------------------------------------------------------------------------------


class PeriodClose(RequestModel):
    start_date: date
    end_date: date

    @model_validator(mode="after")
    def _in_order(self) -> "PeriodClose":
        if self.start_date > self.end_date:
            raise ValueError("the start date must not be after the end date")
        return self


class PeriodRead(ResponseModel):
    id: int
    start_date: date
    end_date: date
    status: Literal["closed", "reopened"]
    closed_by: int
    closed_at: UtcInstant
    reopened_by: int | None
    reopened_at: UtcInstant | None


class PostingAccountSet(RequestModel):
    account_id: int


class PostingAccountRead(ResponseModel):
    key: PostingKey
    account_id: int
    updated_at: UtcInstant


# Tax rules -----------------------------------------------------------------------------------------------------------


class TaxRuleCreate(RequestModel):
    tax_type: TaxType
    supplier_registered: bool | None = Field(
        default=None, description="Required for sales tax withholding; leave out for income tax."
    )
    supplier_filer: bool | None = Field(
        default=None, description="Required for income tax withholding; leave out for sales tax."
    )
    category: TaxCategory = TaxCategory.ANY
    rate_bp: int = Field(ge=0, le=10_000, description="Basis points: 10,000 is 100%.")
    effective_from: date
    effective_to: date | None = None
    source: str = Field(min_length=1, max_length=500, description="Where the rate comes from, and how it was checked.")

    @model_validator(mode="after")
    def _right_flag_for_the_tax(self) -> "TaxRuleCreate":
        if self.effective_to is not None and self.effective_to < self.effective_from:
            raise ValueError("effective_to must not be before effective_from")
        sales = self.tax_type is TaxType.SALES_TAX_WITHHOLDING
        needed, other = (
            (self.supplier_registered, self.supplier_filer)
            if sales
            else (self.supplier_filer, self.supplier_registered)
        )
        if needed is None:
            raise ValueError(
                "supplier_registered is required for sales tax"
                if sales
                else "supplier_filer is required for income tax"
            )
        if other:
            raise ValueError("that flag does not apply to this tax; leave it out")
        return self


class TaxRuleUpdate(RequestModel):
    rate_bp: int | None = Field(default=None, ge=0, le=10_000)
    effective_to: date | None = None
    source: str | None = Field(default=None, min_length=1, max_length=500)


class TaxRuleRead(ResponseModel):
    id: int
    tax_type: TaxType
    supplier_registered: bool
    supplier_filer: bool
    category: TaxCategory
    rate_bp: int
    effective_from: date
    effective_to: date | None
    source: str
    version: int
    created_at: UtcInstant
    updated_at: UtcInstant
