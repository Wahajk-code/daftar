from typing import Annotated

from fastapi import APIRouter, Query, status

from app.core.enums import Role
from app.deps import IfMatchDep, OutboxDep, PrincipalDep, VendorServiceDep, roles
from app.schemas.page import Page, PageParamsDep
from app.schemas.vendors import BankAccountChange, VendorCreate, VendorRead, VendorUpdate

router = APIRouter(prefix="/vendors", tags=["vendors"])

READERS = roles(Role.ADMIN, Role.ACCOUNTANT, Role.APPROVER)
EDITORS = roles(Role.ADMIN, Role.ACCOUNTANT)


@router.get("", operation_id="list_vendors", **READERS)
def list_vendors(
    service: VendorServiceDep,
    page: PageParamsDep,
    q: Annotated[str | None, Query(max_length=100, description="Matches name or NTN.")] = None,
    is_active: bool | None = None,
    registered: bool | None = None,
    filer: bool | None = None,
) -> Page[VendorRead]:
    rows, total = service.list_vendors(
        q=q.strip().lower() if q else None,
        is_active=is_active,
        registered=registered,
        filer=filer,
        sort=page.sort,
        limit=page.limit,
        offset=page.offset,
    )
    return Page(items=[VendorRead.model_validate(r) for r in rows], total=total, limit=page.limit, offset=page.offset)


@router.get("/{vendor_id}", operation_id="get_vendor", **READERS)
def get_vendor(vendor_id: int, service: VendorServiceDep) -> VendorRead:
    return VendorRead.model_validate(service.get(vendor_id))


@router.post("", operation_id="create_vendor", status_code=status.HTTP_201_CREATED, **EDITORS)
def create_vendor(body: VendorCreate, actor: PrincipalDep, service: VendorServiceDep) -> VendorRead:
    return VendorRead.model_validate(service.create(actor, body.model_dump()))


@router.patch("/{vendor_id}", operation_id="update_vendor", **EDITORS)
def update_vendor(
    vendor_id: int, body: VendorUpdate, version: IfMatchDep, actor: PrincipalDep, service: VendorServiceDep
) -> VendorRead:
    return VendorRead.model_validate(service.update(actor, vendor_id, version, body.model_dump(exclude_unset=True)))


@router.post("/{vendor_id}/deactivate", operation_id="deactivate_vendor", **EDITORS)
def deactivate_vendor(vendor_id: int, actor: PrincipalDep, service: VendorServiceDep) -> VendorRead:
    return VendorRead.model_validate(service.set_active(actor, vendor_id, active=False))


@router.post("/{vendor_id}/activate", operation_id="activate_vendor", **EDITORS)
def activate_vendor(vendor_id: int, actor: PrincipalDep, service: VendorServiceDep) -> VendorRead:
    return VendorRead.model_validate(service.set_active(actor, vendor_id, active=True))


@router.post("/{vendor_id}/bank-account", operation_id="change_vendor_bank_account", **EDITORS)
def change_vendor_bank_account(
    vendor_id: int,
    body: BankAccountChange,
    version: IfMatchDep,
    actor: PrincipalDep,
    service: VendorServiceDep,
    outbox: OutboxDep,
) -> VendorRead:
    """Needs your password again. The vendor's creator and every Admin are emailed. The number is never returned."""
    vendor = service.change_bank_account(
        actor,
        vendor_id,
        version,
        account_number=body.account_number,
        bank_name=body.bank_name,
        current_password=body.current_password,
    )
    outbox.dispatch()
    return VendorRead.model_validate(vendor)
