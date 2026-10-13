"""Vouchers, and generating them from approved expenses and purchases. HTTP only: the rules are in VoucherService."""

from collections.abc import Sequence
from datetime import date
from decimal import Decimal
from typing import Annotated, Any

from fastapi import APIRouter, Query, status

from app.core.enums import DocumentStatus, Role, VoucherType
from app.core.principal import Principal
from app.deps import IdempotencyKeyDep, IfMatchDep, OutboxDep, PrincipalDep, VoucherServiceDep, roles
from app.schemas.documents import HistoryItem, TransitionRequest
from app.schemas.page import Page, PageParamsDep
from app.schemas.vouchers import (
    BalanceCheckRead,
    BalanceCheckRequest,
    OffsettingLine,
    VoidRequest,
    VoidResult,
    VoucherCreate,
    VoucherRead,
    VoucherUpdate,
)
from app.services.vouchers import VoucherService

router = APIRouter(prefix="/vouchers", tags=["vouchers"])

OFFICE = roles(Role.ADMIN, Role.ACCOUNTANT, Role.APPROVER)
BOOKKEEPERS = roles(Role.ADMIN, Role.ACCOUNTANT)
REVIEWERS = roles(Role.ADMIN, Role.APPROVER)


def _read(voucher: Any, actor: Principal, service: VoucherService) -> VoucherRead:
    read = VoucherRead.model_validate(voucher)
    read.actions = service.actions(actor, voucher)
    return read


def _history(events: Sequence[Any]) -> list[HistoryItem]:
    return [HistoryItem.model_validate(event) for event in events]


@router.get("", operation_id="list_vouchers", **OFFICE)
def list_vouchers(
    actor: PrincipalDep,
    service: VoucherServiceDep,
    page: PageParamsDep,
    voucher_type: VoucherType | None = None,
    status: DocumentStatus | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    amount_min: Annotated[Decimal | None, Query(ge=0, max_digits=14, decimal_places=2)] = None,
    amount_max: Annotated[Decimal | None, Query(ge=0, max_digits=14, decimal_places=2)] = None,
    q: Annotated[str | None, Query(max_length=100, description="Matches the number or the narration.")] = None,
) -> Page[VoucherRead]:
    rows, total = service.list_vouchers(
        actor=actor,
        voucher_type=voucher_type,
        status=status,
        date_from=date_from,
        date_to=date_to,
        amount_min=amount_min,
        amount_max=amount_max,
        q=q.strip().lower() if q else None,
        sort=page.sort,
        limit=page.limit,
        offset=page.offset,
    )
    return Page(items=[_read(r, actor, service) for r in rows], total=total, limit=page.limit, offset=page.offset)


@router.post("/check-balance", operation_id="check_voucher_balance", **BOOKKEEPERS)
def check_voucher_balance(body: BalanceCheckRequest, service: VoucherServiceDep) -> BalanceCheckRead:
    """Where lines stand and the one line that would balance them. Saves nothing: a draft cannot be saved unbalanced."""
    totals, fix = service.check_balance([line.model_dump() for line in body.lines])
    return BalanceCheckRead(
        total_debit=totals.debit,
        total_credit=totals.credit,
        difference=totals.difference,
        balanced=totals.balanced,
        offsetting_line=OffsettingLine(side=fix[0], amount=fix[1]) if fix else None,
    )


@router.get("/{voucher_id}", operation_id="get_voucher", **OFFICE)
def get_voucher(voucher_id: int, actor: PrincipalDep, service: VoucherServiceDep) -> VoucherRead:
    return _read(service.get(voucher_id, actor), actor, service)


@router.post("", operation_id="create_voucher", status_code=status.HTTP_201_CREATED, **BOOKKEEPERS)
def create_voucher(body: VoucherCreate, actor: PrincipalDep, service: VoucherServiceDep) -> VoucherRead:
    return _read(service.create(actor, body.model_dump()), actor, service)


@router.patch("/{voucher_id}", operation_id="update_voucher", **BOOKKEEPERS)
def update_voucher(
    voucher_id: int, body: VoucherUpdate, version: IfMatchDep, actor: PrincipalDep, service: VoucherServiceDep
) -> VoucherRead:
    return _read(service.update(actor, voucher_id, version, body.model_dump(exclude_unset=True)), actor, service)


@router.post("/{voucher_id}/submit", operation_id="submit_voucher", **BOOKKEEPERS)
def submit_voucher(
    voucher_id: int, version: IfMatchDep, actor: PrincipalDep, outbox: OutboxDep, service: VoucherServiceDep
) -> VoucherRead:
    """Refused with the reason when the voucher is not balanced, has fewer than two lines or has no narration."""
    result = service.submit(actor, voucher_id, version)
    outbox.dispatch()
    return _read(result, actor, service)


@router.post("/{voucher_id}/approve", operation_id="approve_voucher", **REVIEWERS)
def approve_voucher(
    voucher_id: int,
    version: IfMatchDep,
    actor: PrincipalDep,
    outbox: OutboxDep,
    service: VoucherServiceDep,
    body: TransitionRequest | None = None,
) -> VoucherRead:
    result = service.approve(actor, voucher_id, version, body.comment if body else None)
    outbox.dispatch()
    return _read(result, actor, service)


@router.post("/{voucher_id}/reject", operation_id="reject_voucher", **REVIEWERS)
def reject_voucher(
    voucher_id: int,
    body: TransitionRequest,
    version: IfMatchDep,
    actor: PrincipalDep,
    outbox: OutboxDep,
    service: VoucherServiceDep,
) -> VoucherRead:
    result = service.reject(actor, voucher_id, version, body.comment)
    outbox.dispatch()
    return _read(result, actor, service)


@router.post("/{voucher_id}/reopen", operation_id="reopen_voucher", **BOOKKEEPERS)
def reopen_voucher(
    voucher_id: int, version: IfMatchDep, actor: PrincipalDep, service: VoucherServiceDep
) -> VoucherRead:
    return _read(service.reopen(actor, voucher_id, version), actor, service)


@router.post("/{voucher_id}/post", operation_id="post_voucher", **BOOKKEEPERS)
def post_voucher(
    voucher_id: int,
    version: IfMatchDep,
    key: IdempotencyKeyDep,
    actor: PrincipalDep,
    service: VoucherServiceDep,
) -> VoucherRead:
    """Number the voucher and post it, and post the expense or purchase it came from. Sending the same
    `Idempotency-Key` again returns the first result and does nothing more."""
    return _read(service.post(actor, voucher_id, version, key), actor, service)


@router.post("/{voucher_id}/void", operation_id="void_voucher", **BOOKKEEPERS)
def void_voucher(
    voucher_id: int,
    body: VoidRequest,
    version: IfMatchDep,
    key: IdempotencyKeyDep,
    actor: PrincipalDep,
    service: VoucherServiceDep,
) -> VoidResult:
    """Cancel a posted voucher with a reason. Creates the linked reversing voucher in the same transaction."""
    original, reversal = service.void(actor, voucher_id, version, body.reason, key)
    return VoidResult(voucher=_read(original, actor, service), reversal=_read(reversal, actor, service))


@router.get("/{voucher_id}/history", operation_id="get_voucher_history", **OFFICE)
def get_voucher_history(voucher_id: int, actor: PrincipalDep, service: VoucherServiceDep) -> list[HistoryItem]:
    return _history(service.history(voucher_id, actor))
