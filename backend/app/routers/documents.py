"""Expenses, purchases and their attachments. HTTP only: the rules are in the services."""

from collections.abc import Sequence
from datetime import date
from decimal import Decimal
from typing import Annotated, Any

from fastapi import APIRouter, File, Query, Response, UploadFile, status

from app.core.enums import DocumentStatus, ExpenseType, Role
from app.core.principal import Principal
from app.deps import (
    AttachmentServiceDep,
    ExpenseServiceDep,
    IfMatchDep,
    OutboxDep,
    PrincipalDep,
    PurchaseServiceDep,
    SettingsDep,
    VoucherServiceDep,
    roles,
)
from app.schemas.documents import (
    AllocationPreviewRead,
    AllocationPreviewRequest,
    AllocationRead,
    AttachmentRead,
    DuplicateWarningRead,
    ExpenseCreate,
    ExpenseRead,
    ExpenseUpdate,
    HistoryItem,
    PurchaseCreate,
    PurchaseLineRead,
    PurchasePreviewRead,
    PurchasePreviewRequest,
    PurchaseRead,
    PurchaseTotals,
    PurchaseUpdate,
    TransitionRequest,
)
from app.schemas.page import Page, PageParamsDep
from app.schemas.vouchers import PurchaseVoucherRequest, VoucherRead
from app.services.expenses import ExpenseService
from app.services.purchases import PurchaseService

ALL_ROLES = roles(Role.ADMIN, Role.ACCOUNTANT, Role.APPROVER, Role.STAFF)
EXPENSE_AUTHORS = roles(Role.ADMIN, Role.ACCOUNTANT, Role.STAFF)
OFFICE = roles(Role.ADMIN, Role.ACCOUNTANT, Role.APPROVER)
PURCHASE_AUTHORS = roles(Role.ADMIN, Role.ACCOUNTANT)
REVIEWERS = roles(Role.ADMIN, Role.APPROVER)

Search = Annotated[str | None, Query(max_length=100)]
Amount = Annotated[Decimal | None, Query(ge=0, max_digits=14, decimal_places=2)]

expenses = APIRouter(prefix="/expenses", tags=["expenses"])
purchases = APIRouter(prefix="/purchases", tags=["purchases"])
attachments = APIRouter(prefix="/attachments", tags=["attachments"])


def _history(events: Sequence[Any]) -> list[HistoryItem]:
    return [HistoryItem.model_validate(event) for event in events]


# Expenses ------------------------------------------------------------------------------------------------------------


@expenses.get("", operation_id="list_expenses", **ALL_ROLES)
def list_expenses(
    actor: PrincipalDep,
    service: ExpenseServiceDep,
    page: PageParamsDep,
    mine: Annotated[bool, Query(description="Only expenses you created. Staff always see only their own.")] = False,
    status: DocumentStatus | None = None,
    expense_type: ExpenseType | None = None,
    category_id: int | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    amount_min: Amount = None,
    amount_max: Amount = None,
    q: Search = None,
) -> Page[ExpenseRead]:
    rows, total = service.list_expenses(
        actor,
        mine=mine,
        status=status,
        expense_type=expense_type,
        category_id=category_id,
        date_from=date_from,
        date_to=date_to,
        amount_min=amount_min,
        amount_max=amount_max,
        q=q.strip().lower() if q else None,
        sort=page.sort,
        limit=page.limit,
        offset=page.offset,
    )
    items = [_expense(row, actor, service) for row in rows]
    return Page(items=items, total=total, limit=page.limit, offset=page.offset)


def _expense(expense: Any, actor: Principal, service: ExpenseService) -> ExpenseRead:
    read = ExpenseRead.model_validate(expense)
    read.actions = service.actions(actor, expense)  # type: ignore[assignment]
    return read


@expenses.post(
    "/preview-allocation",
    operation_id="preview_expense_allocation",
    **EXPENSE_AUTHORS,
)
def preview_expense_allocation(body: AllocationPreviewRequest, service: ExpenseServiceDep) -> AllocationPreviewRead:
    """What a split comes to as typed. A split that does not add up reports how far short it is instead of failing."""
    result = service.preview(body.amount, body.allocation.model_dump())
    return AllocationPreviewRead(
        complete=result["complete"],
        lines=[AllocationRead.model_validate(line) for line in result["lines"]],
        allocated=result["allocated"],
        remaining=result["remaining"],
        remaining_basis_points=result["remaining_basis_points"],
    )


@expenses.get("/{expense_id}", operation_id="get_expense", **ALL_ROLES)
def get_expense(expense_id: int, actor: PrincipalDep, service: ExpenseServiceDep) -> ExpenseRead:
    return _expense(service.get(actor, expense_id), actor, service)


@expenses.get("/{expense_id}/duplicates", operation_id="get_expense_duplicates", **ALL_ROLES)
def get_expense_duplicates(
    expense_id: int, actor: PrincipalDep, service: ExpenseServiceDep
) -> list[DuplicateWarningRead]:
    """Documents this one resembles. A warning only: saving and approving are never blocked."""
    return [DuplicateWarningRead.model_validate(w) for w in service.duplicates(actor, expense_id)]


@expenses.post("", operation_id="create_expense", status_code=status.HTTP_201_CREATED, **EXPENSE_AUTHORS)
def create_expense(body: ExpenseCreate, actor: PrincipalDep, service: ExpenseServiceDep) -> ExpenseRead:
    return _expense(service.create(actor, body.model_dump()), actor, service)


@expenses.patch("/{expense_id}", operation_id="update_expense", **EXPENSE_AUTHORS)
def update_expense(
    expense_id: int, body: ExpenseUpdate, version: IfMatchDep, actor: PrincipalDep, service: ExpenseServiceDep
) -> ExpenseRead:
    return _expense(service.update(actor, expense_id, version, body.model_dump(exclude_unset=True)), actor, service)


@expenses.post("/{expense_id}/submit", operation_id="submit_expense", **EXPENSE_AUTHORS)
def submit_expense(
    expense_id: int, version: IfMatchDep, actor: PrincipalDep, outbox: OutboxDep, service: ExpenseServiceDep
) -> ExpenseRead:
    result = service.submit(actor, expense_id, version)
    outbox.dispatch()
    return _expense(result, actor, service)


@expenses.post("/{expense_id}/approve", operation_id="approve_expense", **REVIEWERS)
def approve_expense(
    expense_id: int,
    version: IfMatchDep,
    actor: PrincipalDep,
    outbox: OutboxDep,
    service: ExpenseServiceDep,
    body: TransitionRequest | None = None,
) -> ExpenseRead:
    comment = body.comment if body else None
    result = service.approve(actor, expense_id, version, comment)
    outbox.dispatch()
    return _expense(result, actor, service)


@expenses.post("/{expense_id}/reject", operation_id="reject_expense", **REVIEWERS)
def reject_expense(
    expense_id: int,
    body: TransitionRequest,
    version: IfMatchDep,
    actor: PrincipalDep,
    outbox: OutboxDep,
    service: ExpenseServiceDep,
) -> ExpenseRead:
    """A comment is required: the author sees it in the history."""
    result = service.reject(actor, expense_id, version, body.comment)
    outbox.dispatch()
    return _expense(result, actor, service)


@expenses.post("/{expense_id}/reopen", operation_id="reopen_expense", **EXPENSE_AUTHORS)
def reopen_expense(
    expense_id: int, version: IfMatchDep, actor: PrincipalDep, service: ExpenseServiceDep
) -> ExpenseRead:
    """Return a rejected expense to Draft. Only its author can."""
    return _expense(service.reopen(actor, expense_id, version), actor, service)


@expenses.get("/{expense_id}/history", operation_id="get_expense_history", **ALL_ROLES)
def get_expense_history(expense_id: int, actor: PrincipalDep, service: ExpenseServiceDep) -> list[HistoryItem]:
    return _history(service.history(actor, expense_id))


@expenses.get("/{expense_id}/attachments", operation_id="list_expense_attachments", **ALL_ROLES)
def list_expense_attachments(
    expense_id: int, actor: PrincipalDep, service: AttachmentServiceDep
) -> list[AttachmentRead]:
    return [AttachmentRead.model_validate(a) for a in service.list_for(actor, "expense", expense_id)]


@expenses.post(
    "/{expense_id}/attachments",
    operation_id="upload_expense_attachment",
    status_code=status.HTTP_201_CREATED,
    **EXPENSE_AUTHORS,
)
def upload_expense_attachment(
    expense_id: int,
    file: Annotated[UploadFile, File(description="A JPEG, PNG or WebP image.")],
    actor: PrincipalDep,
    service: AttachmentServiceDep,
    settings: SettingsDep,
) -> AttachmentRead:
    data = file.file.read(settings.max_upload_bytes + 1)  # one byte over the cap is enough to know it is too big
    return AttachmentRead.model_validate(service.upload(actor, "expense", expense_id, file.filename or "receipt", data))


@expenses.post(
    "/{expense_id}/generate-voucher",
    operation_id="generate_voucher_from_expense",
    status_code=status.HTTP_201_CREATED,
    **PURCHASE_AUTHORS,
)
def generate_voucher_from_expense(expense_id: int, actor: PrincipalDep, service: VoucherServiceDep) -> VoucherRead:
    """A Payment voucher in Draft: cash for a cash expense, the bank otherwise, tax on its own line. Once only."""
    voucher = service.generate_from_expense(actor, expense_id)
    read = VoucherRead.model_validate(voucher)
    read.actions = service.actions(actor, voucher)
    return read


# Purchases -----------------------------------------------------------------------------------------------------------


def _purchase(purchase: Any, actor: Principal, service: PurchaseService) -> PurchaseRead:
    read = PurchaseRead.model_validate(purchase)
    read.actions = service.actions(actor, purchase)  # type: ignore[assignment]
    return read


@purchases.get("", operation_id="list_purchases", **OFFICE)
def list_purchases(
    actor: PrincipalDep,
    service: PurchaseServiceDep,
    page: PageParamsDep,
    status: DocumentStatus | None = None,
    vendor_id: int | None = None,
    registered: bool | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    amount_min: Amount = None,
    amount_max: Amount = None,
    q: Search = None,
) -> Page[PurchaseRead]:
    rows, total = service.list_purchases(
        status=status,
        vendor_id=vendor_id,
        registered=registered,
        date_from=date_from,
        date_to=date_to,
        amount_min=amount_min,
        amount_max=amount_max,
        q=q.strip().lower() if q else None,
        sort=page.sort,
        limit=page.limit,
        offset=page.offset,
    )
    items = [_purchase(row, actor, service) for row in rows]
    return Page(items=items, total=total, limit=page.limit, offset=page.offset)


@purchases.post("/preview", operation_id="preview_purchase", **PURCHASE_AUTHORS)
def preview_purchase(body: PurchasePreviewRequest, service: PurchaseServiceDep) -> PurchasePreviewRead:
    """Price the lines as they would be saved, with nothing stored. The client's figures are never trusted."""
    pricing = service.preview(body.vendor_id, body.document_date, [line.model_dump() for line in body.lines])
    totals = pricing.totals
    lines = [
        PurchaseLineRead(
            line_no=p.line_no,
            item=p.item,
            category=p.category,
            quantity=p.quantity,
            rate=p.rate,
            sales_tax_bp=p.sales_tax_bp,
            subtotal=p.amounts.subtotal,
            sales_tax=p.amounts.sales_tax,
            gross=p.amounts.gross,
            sales_withholding_rule_id=p.sales_rule_id,
            sales_withholding_bp=p.sales_rate_bp,
            sales_tax_withheld=p.amounts.sales_tax_withheld,
            income_withholding_rule_id=p.income_rule_id,
            income_withholding_bp=p.income_rate_bp,
            income_tax_withheld=p.amounts.income_tax_withheld,
            payable=p.amounts.payable,
        )
        for p in pricing.lines
    ]
    return PurchasePreviewRead(
        document_kind=pricing.kind,
        vendor_registered=pricing.registered,
        vendor_filer=pricing.filer,
        lines=lines,
        totals=PurchaseTotals(
            subtotal=totals.subtotal,
            sales_tax_total=totals.sales_tax,
            gross_total=totals.gross,
            sales_tax_withheld=totals.sales_tax_withheld,
            income_tax_withheld=totals.income_tax_withheld,
            payable=totals.payable,
        ),
    )


@purchases.get("/{purchase_id}", operation_id="get_purchase", **OFFICE)
def get_purchase(purchase_id: int, actor: PrincipalDep, service: PurchaseServiceDep) -> PurchaseRead:
    return _purchase(service.get(purchase_id), actor, service)


@purchases.get("/{purchase_id}/duplicates", operation_id="get_purchase_duplicates", **OFFICE)
def get_purchase_duplicates(purchase_id: int, service: PurchaseServiceDep) -> list[DuplicateWarningRead]:
    """Documents this one resembles. A warning only: saving and approving are never blocked."""
    return [DuplicateWarningRead.model_validate(w) for w in service.duplicates(purchase_id)]


@purchases.post("", operation_id="create_purchase", status_code=status.HTTP_201_CREATED, **PURCHASE_AUTHORS)
def create_purchase(body: PurchaseCreate, actor: PrincipalDep, service: PurchaseServiceDep) -> PurchaseRead:
    return _purchase(service.create(actor, body.model_dump()), actor, service)


@purchases.patch("/{purchase_id}", operation_id="update_purchase", **PURCHASE_AUTHORS)
def update_purchase(
    purchase_id: int, body: PurchaseUpdate, version: IfMatchDep, actor: PrincipalDep, service: PurchaseServiceDep
) -> PurchaseRead:
    return _purchase(service.update(actor, purchase_id, version, body.model_dump(exclude_unset=True)), actor, service)


@purchases.post("/{purchase_id}/submit", operation_id="submit_purchase", **PURCHASE_AUTHORS)
def submit_purchase(
    purchase_id: int, version: IfMatchDep, actor: PrincipalDep, outbox: OutboxDep, service: PurchaseServiceDep
) -> PurchaseRead:
    result = service.submit(actor, purchase_id, version)
    outbox.dispatch()
    return _purchase(result, actor, service)


@purchases.post("/{purchase_id}/approve", operation_id="approve_purchase", **REVIEWERS)
def approve_purchase(
    purchase_id: int,
    version: IfMatchDep,
    actor: PrincipalDep,
    outbox: OutboxDep,
    service: PurchaseServiceDep,
    body: TransitionRequest | None = None,
) -> PurchaseRead:
    result = service.approve(actor, purchase_id, version, body.comment if body else None)
    outbox.dispatch()
    return _purchase(result, actor, service)


@purchases.post("/{purchase_id}/reject", operation_id="reject_purchase", **REVIEWERS)
def reject_purchase(
    purchase_id: int,
    body: TransitionRequest,
    version: IfMatchDep,
    actor: PrincipalDep,
    outbox: OutboxDep,
    service: PurchaseServiceDep,
) -> PurchaseRead:
    result = service.reject(actor, purchase_id, version, body.comment)
    outbox.dispatch()
    return _purchase(result, actor, service)


@purchases.post("/{purchase_id}/reopen", operation_id="reopen_purchase", **PURCHASE_AUTHORS)
def reopen_purchase(
    purchase_id: int, version: IfMatchDep, actor: PrincipalDep, service: PurchaseServiceDep
) -> PurchaseRead:
    return _purchase(service.reopen(actor, purchase_id, version), actor, service)


@purchases.get("/{purchase_id}/history", operation_id="get_purchase_history", **OFFICE)
def get_purchase_history(purchase_id: int, service: PurchaseServiceDep) -> list[HistoryItem]:
    return _history(service.history(purchase_id))


@purchases.get("/{purchase_id}/attachments", operation_id="list_purchase_attachments", **OFFICE)
def list_purchase_attachments(
    purchase_id: int, actor: PrincipalDep, service: AttachmentServiceDep
) -> list[AttachmentRead]:
    return [AttachmentRead.model_validate(a) for a in service.list_for(actor, "purchase", purchase_id)]


@purchases.post(
    "/{purchase_id}/attachments",
    operation_id="upload_purchase_attachment",
    status_code=status.HTTP_201_CREATED,
    **PURCHASE_AUTHORS,
)
def upload_purchase_attachment(
    purchase_id: int,
    file: Annotated[UploadFile, File(description="A JPEG, PNG or WebP image.")],
    actor: PrincipalDep,
    service: AttachmentServiceDep,
    settings: SettingsDep,
) -> AttachmentRead:
    data = file.file.read(settings.max_upload_bytes + 1)
    return AttachmentRead.model_validate(
        service.upload(actor, "purchase", purchase_id, file.filename or "receipt", data)
    )


@purchases.post(
    "/{purchase_id}/generate-voucher",
    operation_id="generate_voucher_from_purchase",
    status_code=status.HTTP_201_CREATED,
    **PURCHASE_AUTHORS,
)
def generate_voucher_from_purchase(
    purchase_id: int, body: PurchaseVoucherRequest, actor: PrincipalDep, service: VoucherServiceDep
) -> VoucherRead:
    """A Payment voucher in Draft: the purchase and its sales tax debited, the vendor paid and each withholding credited
    on its own line. Once only. The category and the payment method are chosen here."""
    voucher = service.generate_from_purchase(actor, purchase_id, body.category_id, body.payment_method)
    read = VoucherRead.model_validate(voucher)
    read.actions = service.actions(actor, voucher)
    return read


# Attachments ---------------------------------------------------------------------------------------------------------


@attachments.get(
    "/{attachment_id}/content",
    operation_id="get_attachment_content",
    response_class=Response,
    responses={200: {"content": {"image/jpeg": {}, "image/png": {}, "image/webp": {}}}},
    **ALL_ROLES,
)
def get_attachment_content(attachment_id: int, actor: PrincipalDep, service: AttachmentServiceDep) -> Response:
    """The image itself, only for someone who may see the document it belongs to. It has no public address."""
    stored = service.read(actor, attachment_id)
    return Response(
        content=stored.content,
        media_type=stored.attachment.content_type,
        headers={
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
            "Content-Disposition": f'inline; filename="{stored.attachment.original_name}"',
        },
    )


@attachments.post("/{attachment_id}/remove", operation_id="remove_attachment", **EXPENSE_AUTHORS)
def remove_attachment(attachment_id: int, actor: PrincipalDep, service: AttachmentServiceDep) -> AttachmentRead:
    """Take an attachment off a draft. The record stays; the stored file is deleted."""
    return AttachmentRead.model_validate(service.remove(actor, attachment_id))
