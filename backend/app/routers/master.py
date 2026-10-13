"""Accounts, categories, cost centres, projects, periods, posting accounts and tax rules."""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Query, status

from app.core.enums import AccountType, PostingKey, ProjectKind, Role, TaxCategory, TaxType
from app.deps import (
    AccountingSettingsServiceDep,
    AccountServiceDep,
    CategoryServiceDep,
    CostCenterServiceDep,
    IfMatchDep,
    PeriodServiceDep,
    PostingAccountServiceDep,
    PrincipalDep,
    ProjectServiceDep,
    TaxRuleServiceDep,
    roles,
)
from app.schemas.master import (
    AccountCreate,
    AccountingSettingsRead,
    AccountingSettingsSet,
    AccountRead,
    AccountUpdate,
    CategoryCreate,
    CategoryRead,
    CategoryUpdate,
    CostCenterCreate,
    CostCenterRead,
    CostCenterUpdate,
    PeriodClose,
    PeriodRead,
    PostingAccountRead,
    PostingAccountSet,
    ProjectCreate,
    ProjectRead,
    ProjectUpdate,
    TaxRuleCreate,
    TaxRuleRead,
    TaxRuleUpdate,
)
from app.schemas.page import Page, PageParamsDep

ALL_ROLES = roles(Role.ADMIN, Role.ACCOUNTANT, Role.APPROVER, Role.STAFF)
OFFICE = roles(Role.ADMIN, Role.ACCOUNTANT, Role.APPROVER)  # may read vendors, accounts, rates, periods
EDITORS = roles(Role.ADMIN, Role.ACCOUNTANT)
ADMIN = roles(Role.ADMIN)

Search = Annotated[str | None, Query(max_length=100)]


def _q(value: str | None) -> str | None:
    return value.strip().lower() if value else None


# Accounts ------------------------------------------------------------------------------------------------------------

accounts = APIRouter(prefix="/accounts", tags=["accounts"])


@accounts.get("", operation_id="list_accounts", **OFFICE)
def list_accounts(
    service: AccountServiceDep,
    page: PageParamsDep,
    q: Search = None,
    type: AccountType | None = None,
    parent_id: int | None = None,
    is_active: bool | None = None,
    is_postable: bool | None = None,
) -> Page[AccountRead]:
    rows, total = service.list_accounts(
        q=_q(q),
        type_=type,
        parent_id=parent_id,
        is_active=is_active,
        is_postable=is_postable,
        sort=page.sort,
        limit=page.limit,
        offset=page.offset,
    )
    return Page(items=[AccountRead.model_validate(r) for r in rows], total=total, limit=page.limit, offset=page.offset)


@accounts.get("/{account_id}", operation_id="get_account", **OFFICE)
def get_account(account_id: int, service: AccountServiceDep) -> AccountRead:
    return AccountRead.model_validate(service.get(account_id))


@accounts.post("", operation_id="create_account", status_code=status.HTTP_201_CREATED, **EDITORS)
def create_account(body: AccountCreate, actor: PrincipalDep, service: AccountServiceDep) -> AccountRead:
    return AccountRead.model_validate(service.create(actor, body.model_dump()))


@accounts.patch("/{account_id}", operation_id="update_account", **EDITORS)
def update_account(
    account_id: int, body: AccountUpdate, version: IfMatchDep, actor: PrincipalDep, service: AccountServiceDep
) -> AccountRead:
    changes = body.model_dump(exclude_unset=True, exclude_none=True)
    return AccountRead.model_validate(service.update(actor, account_id, version, changes))


@accounts.post("/{account_id}/deactivate", operation_id="deactivate_account", **EDITORS)
def deactivate_account(account_id: int, actor: PrincipalDep, service: AccountServiceDep) -> AccountRead:
    return AccountRead.model_validate(service.set_active(actor, account_id, active=False))


@accounts.post("/{account_id}/activate", operation_id="activate_account", **EDITORS)
def activate_account(account_id: int, actor: PrincipalDep, service: AccountServiceDep) -> AccountRead:
    return AccountRead.model_validate(service.set_active(actor, account_id, active=True))


# Categories ----------------------------------------------------------------------------------------------------------

categories = APIRouter(prefix="/categories", tags=["categories"])


@categories.get("", operation_id="list_categories", **ALL_ROLES)
def list_categories(
    service: CategoryServiceDep, page: PageParamsDep, q: Search = None, is_active: bool | None = None
) -> Page[CategoryRead]:
    rows, total = service.list_categories(
        q=_q(q), is_active=is_active, sort=page.sort, limit=page.limit, offset=page.offset
    )
    return Page(items=[CategoryRead.model_validate(r) for r in rows], total=total, limit=page.limit, offset=page.offset)


@categories.get("/{category_id}", operation_id="get_category", **ALL_ROLES)
def get_category(category_id: int, service: CategoryServiceDep) -> CategoryRead:
    return CategoryRead.model_validate(service.get(category_id))


@categories.post("", operation_id="create_category", status_code=status.HTTP_201_CREATED, **EDITORS)
def create_category(body: CategoryCreate, actor: PrincipalDep, service: CategoryServiceDep) -> CategoryRead:
    return CategoryRead.model_validate(service.create(actor, body.model_dump()))


@categories.patch("/{category_id}", operation_id="update_category", **EDITORS)
def update_category(
    category_id: int, body: CategoryUpdate, version: IfMatchDep, actor: PrincipalDep, service: CategoryServiceDep
) -> CategoryRead:
    changes = body.model_dump(exclude_unset=True, exclude_none=True)
    return CategoryRead.model_validate(service.update(actor, category_id, version, changes))


@categories.post("/{category_id}/deactivate", operation_id="deactivate_category", **EDITORS)
def deactivate_category(category_id: int, actor: PrincipalDep, service: CategoryServiceDep) -> CategoryRead:
    return CategoryRead.model_validate(service.set_active(actor, category_id, active=False))


@categories.post("/{category_id}/activate", operation_id="activate_category", **EDITORS)
def activate_category(category_id: int, actor: PrincipalDep, service: CategoryServiceDep) -> CategoryRead:
    return CategoryRead.model_validate(service.set_active(actor, category_id, active=True))


# Cost centres --------------------------------------------------------------------------------------------------------

cost_centers = APIRouter(prefix="/cost-centers", tags=["cost centres"])


@cost_centers.get("", operation_id="list_cost_centers", **ALL_ROLES)
def list_cost_centers(
    service: CostCenterServiceDep, page: PageParamsDep, q: Search = None, is_active: bool | None = None
) -> Page[CostCenterRead]:
    rows, total = service.list_cost_centers(
        q=_q(q), is_active=is_active, sort=page.sort, limit=page.limit, offset=page.offset
    )
    return Page(
        items=[CostCenterRead.model_validate(r) for r in rows], total=total, limit=page.limit, offset=page.offset
    )


@cost_centers.get("/{cost_center_id}", operation_id="get_cost_center", **ALL_ROLES)
def get_cost_center(cost_center_id: int, service: CostCenterServiceDep) -> CostCenterRead:
    return CostCenterRead.model_validate(service.get(cost_center_id))


@cost_centers.post("", operation_id="create_cost_center", status_code=status.HTTP_201_CREATED, **EDITORS)
def create_cost_center(body: CostCenterCreate, actor: PrincipalDep, service: CostCenterServiceDep) -> CostCenterRead:
    return CostCenterRead.model_validate(service.create(actor, body.model_dump()))


@cost_centers.patch("/{cost_center_id}", operation_id="update_cost_center", **EDITORS)
def update_cost_center(
    cost_center_id: int,
    body: CostCenterUpdate,
    version: IfMatchDep,
    actor: PrincipalDep,
    service: CostCenterServiceDep,
) -> CostCenterRead:
    changes = body.model_dump(exclude_unset=True, exclude_none=True)
    return CostCenterRead.model_validate(service.update(actor, cost_center_id, version, changes))


@cost_centers.post("/{cost_center_id}/deactivate", operation_id="deactivate_cost_center", **EDITORS)
def deactivate_cost_center(cost_center_id: int, actor: PrincipalDep, service: CostCenterServiceDep) -> CostCenterRead:
    return CostCenterRead.model_validate(service.set_active(actor, cost_center_id, active=False))


@cost_centers.post("/{cost_center_id}/activate", operation_id="activate_cost_center", **EDITORS)
def activate_cost_center(cost_center_id: int, actor: PrincipalDep, service: CostCenterServiceDep) -> CostCenterRead:
    return CostCenterRead.model_validate(service.set_active(actor, cost_center_id, active=True))


# Projects and products -----------------------------------------------------------------------------------------------

projects = APIRouter(prefix="/projects", tags=["projects"])


@projects.get("", operation_id="list_projects", **ALL_ROLES)
def list_projects(
    service: ProjectServiceDep,
    page: PageParamsDep,
    q: Search = None,
    kind: ProjectKind | None = None,
    is_active: bool | None = None,
) -> Page[ProjectRead]:
    rows, total = service.list_projects(
        q=_q(q), kind=kind, is_active=is_active, sort=page.sort, limit=page.limit, offset=page.offset
    )
    return Page(items=[ProjectRead.model_validate(r) for r in rows], total=total, limit=page.limit, offset=page.offset)


@projects.get("/{project_id}", operation_id="get_project", **ALL_ROLES)
def get_project(project_id: int, service: ProjectServiceDep) -> ProjectRead:
    return ProjectRead.model_validate(service.get(project_id))


@projects.post("", operation_id="create_project", status_code=status.HTTP_201_CREATED, **EDITORS)
def create_project(body: ProjectCreate, actor: PrincipalDep, service: ProjectServiceDep) -> ProjectRead:
    return ProjectRead.model_validate(service.create(actor, body.model_dump()))


@projects.patch("/{project_id}", operation_id="update_project", **EDITORS)
def update_project(
    project_id: int, body: ProjectUpdate, version: IfMatchDep, actor: PrincipalDep, service: ProjectServiceDep
) -> ProjectRead:
    changes = body.model_dump(exclude_unset=True, exclude_none=True)
    return ProjectRead.model_validate(service.update(actor, project_id, version, changes))


@projects.post("/{project_id}/deactivate", operation_id="deactivate_project", **EDITORS)
def deactivate_project(project_id: int, actor: PrincipalDep, service: ProjectServiceDep) -> ProjectRead:
    return ProjectRead.model_validate(service.set_active(actor, project_id, active=False))


@projects.post("/{project_id}/activate", operation_id="activate_project", **EDITORS)
def activate_project(project_id: int, actor: PrincipalDep, service: ProjectServiceDep) -> ProjectRead:
    return ProjectRead.model_validate(service.set_active(actor, project_id, active=True))


# Periods -------------------------------------------------------------------------------------------------------------

periods = APIRouter(prefix="/periods", tags=["periods"])


@periods.get("", operation_id="list_periods", **OFFICE)
def list_periods(service: PeriodServiceDep, page: PageParamsDep) -> Page[PeriodRead]:
    rows, total = service.list_periods(sort=page.sort, limit=page.limit, offset=page.offset)
    return Page(items=[PeriodRead.model_validate(r) for r in rows], total=total, limit=page.limit, offset=page.offset)


@periods.post("/close", operation_id="close_period", status_code=status.HTTP_201_CREATED, **ADMIN)
def close_period(body: PeriodClose, actor: PrincipalDep, service: PeriodServiceDep) -> PeriodRead:
    """Close an inclusive range of dates. Nothing can be posted dated inside it until it is reopened."""
    return PeriodRead.model_validate(service.close(actor, body.start_date, body.end_date))


@periods.post("/{period_id}/reopen", operation_id="reopen_period", **ADMIN)
def reopen_period(period_id: int, actor: PrincipalDep, service: PeriodServiceDep) -> PeriodRead:
    return PeriodRead.model_validate(service.reopen(actor, period_id))


# Posting accounts ----------------------------------------------------------------------------------------------------

posting_accounts = APIRouter(prefix="/posting-accounts", tags=["posting accounts"])


@posting_accounts.get("", operation_id="list_posting_accounts", **OFFICE)
def list_posting_accounts(service: PostingAccountServiceDep) -> list[PostingAccountRead]:
    return [PostingAccountRead.model_validate(r) for r in service.list_all()]


@posting_accounts.put("/{key}", operation_id="set_posting_account", **EDITORS)
def set_posting_account(
    key: PostingKey, body: PostingAccountSet, actor: PrincipalDep, service: PostingAccountServiceDep
) -> PostingAccountRead:
    return PostingAccountRead.model_validate(service.set(actor, key, body.account_id))


# Tax rules -----------------------------------------------------------------------------------------------------------

tax_rules = APIRouter(prefix="/tax-rules", tags=["tax rules"])


@tax_rules.get("", operation_id="list_tax_rules", **OFFICE)
def list_tax_rules(
    service: TaxRuleServiceDep,
    page: PageParamsDep,
    tax_type: TaxType | None = None,
    category: TaxCategory | None = None,
    active_on: date | None = None,
) -> Page[TaxRuleRead]:
    rows, total = service.list_rules(
        tax_type=tax_type,
        category=category,
        active_on=active_on,
        sort=page.sort,
        limit=page.limit,
        offset=page.offset,
    )
    return Page(items=[TaxRuleRead.model_validate(r) for r in rows], total=total, limit=page.limit, offset=page.offset)


@tax_rules.get("/resolve", operation_id="resolve_tax_rule", **EDITORS)
def resolve_tax_rule(
    service: TaxRuleServiceDep,
    tax_type: TaxType,
    on: date,
    supplier_registered: bool = False,
    supplier_filer: bool = False,
    category: TaxCategory = TaxCategory.ANY,
) -> TaxRuleRead:
    """The rule in force on a date for a kind of supplier and payment. A specific category beats `any`."""
    return TaxRuleRead.model_validate(
        service.resolve(
            tax_type=tax_type,
            supplier_registered=supplier_registered,
            supplier_filer=supplier_filer,
            category=category,
            on=on,
        )
    )


@tax_rules.get("/{rule_id}", operation_id="get_tax_rule", **OFFICE)
def get_tax_rule(rule_id: int, service: TaxRuleServiceDep) -> TaxRuleRead:
    return TaxRuleRead.model_validate(service.get(rule_id))


@tax_rules.post("", operation_id="create_tax_rule", status_code=status.HTTP_201_CREATED, **EDITORS)
def create_tax_rule(body: TaxRuleCreate, actor: PrincipalDep, service: TaxRuleServiceDep) -> TaxRuleRead:
    return TaxRuleRead.model_validate(service.create(actor, body.model_dump()))


@tax_rules.patch("/{rule_id}", operation_id="update_tax_rule", **EDITORS)
def update_tax_rule(
    rule_id: int, body: TaxRuleUpdate, version: IfMatchDep, actor: PrincipalDep, service: TaxRuleServiceDep
) -> TaxRuleRead:
    return TaxRuleRead.model_validate(service.update(actor, rule_id, version, body.model_dump(exclude_unset=True)))


# Accounting settings -------------------------------------------------------------------------------------------------

accounting_settings = APIRouter(prefix="/settings/accounting", tags=["settings"])


def _settings_read(service: AccountingSettingsServiceDep) -> AccountingSettingsRead:
    row = service.get()
    return AccountingSettingsRead(
        fiscal_year_start_month=row.fiscal_year_start_month,
        numbering_year_today=service.year_today(row),
        updated_by=row.updated_by,
        updated_at=row.updated_at,
    )


@accounting_settings.get("", operation_id="get_accounting_settings", **OFFICE)
def get_accounting_settings(service: AccountingSettingsServiceDep) -> AccountingSettingsRead:
    return _settings_read(service)


@accounting_settings.put("", operation_id="set_accounting_settings", **EDITORS)
def set_accounting_settings(
    body: AccountingSettingsSet, actor: PrincipalDep, service: AccountingSettingsServiceDep
) -> AccountingSettingsRead:
    """Choose the month the voucher numbering year starts in. It applies to vouchers posted from now on; numbers already
    given never change."""
    service.set_year_start(actor, body.fiscal_year_start_month)
    return _settings_read(service)
