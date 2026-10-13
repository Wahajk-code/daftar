"""Purchases: what was bought from a vendor, priced on the server.

The client sends item, category, quantity, rate and the sales tax rate for each line and nothing else; every other
figure is computed here in Decimal. The vendor's registration and filer flags, and the withholding rate and rule found
for the document date, are copied onto the purchase when it is written, so a later change to the vendor or the rate
table never alters a saved purchase. Both withholdings come out of the amount payable to the vendor."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.config import Settings
from app.core.clock import Clock
from app.core.duplicates import DuplicateWarning
from app.core.enums import DocumentStatus, DocumentType, PurchaseKind, TaxType
from app.core.errors import (
    ErrorCode,
    FieldError,
    ForbiddenError,
    GuardFailedError,
    NotFoundError,
    ValidationFailedError,
    VersionConflictError,
)
from app.core.mail import Outbox
from app.core.money import MAX_AMOUNT
from app.core.principal import Principal
from app.core.tax import LineAmounts, LineError, compute_line, total_lines
from app.models.base import JsonDict
from app.models.documents import DocumentEvent, Purchase, PurchaseLine
from app.models.vendor import Vendor
from app.repositories import documents as document_repository
from app.repositories import tax_rules as rule_repository
from app.repositories import vendors as vendor_repository
from app.services.audit import AuditService
from app.services.duplicates import DuplicateFinder
from app.services.master import changed, snapshot
from app.services.notifications import MoveNotifier, summary_line
from app.services.tax_rules import relevant_flags
from app.services.workflow import Workflow, available_actions

FIELDS = ("vendor_id", "document_date", "document_kind", "invoice_number", "description", "status")


@dataclass(frozen=True)
class PricedLine:
    """A line with every figure worked out and the rate and rule it was given."""

    line_no: int
    item: str
    category: Any
    quantity: Decimal
    rate: Decimal
    sales_tax_bp: int
    amounts: LineAmounts
    sales_rule_id: int
    sales_rate_bp: int
    income_rule_id: int
    income_rate_bp: int


@dataclass(frozen=True)
class Pricing:
    kind: PurchaseKind
    registered: bool
    filer: bool
    lines: list[PricedLine]
    totals: LineAmounts


class PurchaseService:
    def __init__(self, session: Session, clock: Clock, settings: Settings, outbox: Outbox) -> None:
        self._session = session
        self._clock = clock
        self._settings = settings
        self._workflow = Workflow(session, clock)
        self._notifier = MoveNotifier(session, settings, outbox)
        self._audit = AuditService(session, clock)

    # Reading ---------------------------------------------------------------------------------------------------------

    def get(self, purchase_id: int) -> Purchase:
        purchase = document_repository.get_purchase(self._session, purchase_id)
        if purchase is None:
            raise NotFoundError("There is no such purchase.")
        return purchase

    def duplicates(self, purchase_id: int) -> list[DuplicateWarning]:
        """Other purchases and expenses that look like this one."""
        return DuplicateFinder(self._session).for_purchase(self.get(purchase_id))

    def list_purchases(
        self,
        *,
        status: DocumentStatus | None,
        vendor_id: int | None,
        registered: bool | None,
        date_from: date | None,
        date_to: date | None,
        amount_min: Decimal | None,
        amount_max: Decimal | None,
        q: str | None,
        sort: str | None,
        limit: int,
        offset: int,
    ) -> tuple[list[Purchase], int]:
        return document_repository.list_purchases(
            self._session,
            only_created_by=None,
            status=status,
            vendor_id=vendor_id,
            registered=registered,
            date_from=date_from,
            date_to=date_to,
            amount_min=amount_min,
            amount_max=amount_max,
            q=q,
            sort=sort,
            limit=limit,
            offset=offset,
        )

    def history(self, purchase_id: int) -> list[DocumentEvent]:
        self.get(purchase_id)
        return document_repository.events_of(self._session, DocumentType.PURCHASE, purchase_id)

    def actions(self, actor: Principal, purchase: Purchase) -> list[str]:
        return available_actions(DocumentType.PURCHASE, purchase.status, purchase.created_by, actor)

    def preview(self, vendor_id: int, document_date: date | None, lines: list[dict[str, Any]]) -> Pricing:
        """What these lines come to, with nothing saved."""
        vendor = self._require_vendor(vendor_id)
        return self._price(vendor, document_date or self._today(), lines)

    # Writing ---------------------------------------------------------------------------------------------------------

    def create(self, actor: Principal, data: dict[str, Any]) -> Purchase:
        vendor = self._require_vendor(data["vendor_id"])
        document_date = data.get("document_date") or self._today()
        pricing = self._price(vendor, document_date, data["lines"])
        invoice_number = self._invoice_number(pricing.kind, data.get("invoice_number"))
        purchase = Purchase(
            created_by=actor.id,
            vendor_id=vendor.id,
            document_date=document_date,
            document_kind=pricing.kind,
            invoice_number=invoice_number,
            description=data.get("description", ""),
            vendor_registered=pricing.registered,
            vendor_filer=pricing.filer,
            lines=[],
            **self._header(pricing),
        )
        document_repository.add_purchase(self._session, purchase)
        self._add_lines(purchase, pricing)
        self._workflow.record_creation(purchase, DocumentType.PURCHASE, actor)
        self._audit.record(
            actor_id=actor.id,
            action="purchase.created",
            entity_type="purchase",
            entity_id=purchase.id,
            after=self._snapshot(purchase),
        )
        self._session.commit()
        return self._reload(purchase.id)

    def update(self, actor: Principal, purchase_id: int, expected_version: int, changes: dict[str, Any]) -> Purchase:
        purchase = self._locked(purchase_id)
        if purchase.created_by != actor.id:
            raise ForbiddenError("Only the author can change this purchase.")
        if purchase.status is not DocumentStatus.DRAFT:
            raise GuardFailedError("Only a draft can be changed.", code=ErrorCode.DOCUMENT_LOCKED)
        if purchase.version != expected_version:
            raise VersionConflictError("Someone else changed this record. Reload it and try again.")
        before = self._snapshot(purchase)
        purchase.updated_at = self._clock.now()  # written together with the changes below

        vendor = purchase.vendor
        if changes.get("vendor_id") not in (None, purchase.vendor_id):
            vendor = self._require_vendor(changes["vendor_id"])
        document_date = changes.get("document_date") or purchase.document_date
        lines = changes.get("lines") or [
            {
                "item": line.item,
                "category": line.category,
                "quantity": line.quantity,
                "rate": line.rate,
                "sales_tax_bp": line.sales_tax_bp,
            }
            for line in purchase.lines
        ]
        # Priced again on every edit: the vendor, the date or a line may have changed which rates apply.
        pricing = self._price(vendor, document_date, lines)
        invoice_number = self._invoice_number(pricing.kind, changes.get("invoice_number", purchase.invoice_number))

        purchase.vendor_id = vendor.id
        purchase.document_date = document_date
        purchase.document_kind = pricing.kind
        purchase.invoice_number = invoice_number
        if "description" in changes and changes["description"] is not None:
            purchase.description = changes["description"]
        purchase.vendor_registered = pricing.registered
        purchase.vendor_filer = pricing.filer
        for name, value in self._header(pricing).items():
            setattr(purchase, name, value)
        purchase.lines.clear()
        self._session.flush()
        self._add_lines(purchase, pricing)
        old, new = changed(before, self._snapshot(purchase))
        self._audit.record(
            actor_id=actor.id,
            action="purchase.updated",
            entity_type="purchase",
            entity_id=purchase.id,
            before=old,
            after=new,
        )
        self._session.commit()
        return self._reload(purchase.id)

    # Moves -----------------------------------------------------------------------------------------------------------

    def submit(self, actor: Principal, purchase_id: int, expected_version: int) -> Purchase:
        purchase = self._locked(purchase_id)
        if purchase.created_by != actor.id:
            raise ForbiddenError("Only the author can submit this purchase.")
        problems: list[FieldError] = []
        if not purchase.lines:
            problems.append(FieldError("lines", "Add at least one line.", "required"))
        return self._move(actor, purchase, DocumentStatus.SUBMITTED, expected_version, problems=problems)

    def approve(self, actor: Principal, purchase_id: int, expected_version: int, comment: str | None) -> Purchase:
        return self._move(actor, self._locked(purchase_id), DocumentStatus.APPROVED, expected_version, comment)

    def reject(self, actor: Principal, purchase_id: int, expected_version: int, comment: str | None) -> Purchase:
        return self._move(actor, self._locked(purchase_id), DocumentStatus.REJECTED, expected_version, comment)

    def reopen(self, actor: Principal, purchase_id: int, expected_version: int) -> Purchase:
        return self._move(actor, self._locked(purchase_id), DocumentStatus.DRAFT, expected_version)

    # -----------------------------------------------------------------------------------------------------------------

    def _move(
        self,
        actor: Principal,
        purchase: Purchase,
        target: DocumentStatus,
        expected_version: int,
        comment: str | None = None,
        problems: list[FieldError] | None = None,
    ) -> Purchase:
        audience = self._notifier.audience(target, purchase.created_by)
        purchase.updated_at = self._clock.now()
        self._workflow.move(
            purchase,
            DocumentType.PURCHASE,
            actor,
            target,
            expected_version=expected_version,
            comment=comment,
            problems=problems or [],
        )
        self._notifier.announce(
            audience,
            document_type=DocumentType.PURCHASE,
            document_id=purchase.id,
            summary=summary_line(purchase.gross_total, purchase.description),
            actor=actor,
            target=target,
            comment=comment,
            when=purchase.updated_at,
        )
        self._session.commit()
        return self._reload(purchase.id)

    def _locked(self, purchase_id: int) -> Purchase:
        purchase = document_repository.get_purchase(self._session, purchase_id, for_update=True)
        if purchase is None:
            raise NotFoundError("There is no such purchase.")
        return purchase

    def _reload(self, purchase_id: int) -> Purchase:
        purchase = document_repository.get_purchase(self._session, purchase_id, refresh=True)
        assert purchase is not None
        return purchase

    def _today(self) -> date:
        return self._clock.today(ZoneInfo(self._settings.display_timezone))

    def _require_vendor(self, vendor_id: int) -> Vendor:
        vendor = vendor_repository.get(self._session, vendor_id)
        if vendor is None or not vendor.is_active:
            raise ValidationFailedError(
                "Choose an active vendor.",
                errors=[FieldError("vendor_id", "That vendor is not available.", "inactive_reference")],
            )
        return vendor

    @staticmethod
    def _invoice_number(kind: PurchaseKind, supplied: str | None) -> str | None:
        number = (supplied or "").strip() or None
        if kind is PurchaseKind.TAX_INVOICE and number is None:
            raise ValidationFailedError(
                "A registered vendor's purchase needs the tax invoice number.",
                errors=[FieldError("invoice_number", "Enter the number printed on the tax invoice.", "required")],
            )
        return number

    def _price(self, vendor: Vendor, on: date, lines: list[dict[str, Any]]) -> Pricing:
        registered, filer = vendor.is_sales_tax_registered, vendor.is_filer
        sales_registered, sales_filer = relevant_flags(TaxType.SALES_TAX_WITHHOLDING, registered, filer)
        income_registered, income_filer = relevant_flags(TaxType.INCOME_TAX_WITHHOLDING, registered, filer)
        priced: list[PricedLine] = []
        for index, line in enumerate(lines):
            where = f"lines.{index}"
            sales_rule = rule_repository.find(
                self._session,
                tax_type=TaxType.SALES_TAX_WITHHOLDING,
                supplier_registered=sales_registered,
                supplier_filer=sales_filer,
                category=line["category"],
                on=on,
            )
            income_rule = rule_repository.find(
                self._session,
                tax_type=TaxType.INCOME_TAX_WITHHOLDING,
                supplier_registered=income_registered,
                supplier_filer=income_filer,
                category=line["category"],
                on=on,
            )
            if sales_rule is None or income_rule is None:
                missing = "sales tax" if sales_rule is None else "income tax"
                raise GuardFailedError(
                    f"No {missing} withholding rate applies to line {index + 1}. Ask an Admin to add one.",
                    code=ErrorCode.TAX_RULE_MISSING,
                    errors=[FieldError(f"{where}.category", f"No {missing} rate for this kind of payment.", "no_rate")],
                )
            try:
                amounts = compute_line(
                    quantity=line["quantity"],
                    rate=line["rate"],
                    sales_tax_bp=line["sales_tax_bp"],
                    supplier_registered=registered,
                    sales_withholding_bp=sales_rule.rate_bp,
                    income_withholding_bp=income_rule.rate_bp,
                )
            except LineError as exc:
                raise ValidationFailedError(
                    str(exc).capitalize() + ".", errors=[FieldError(f"{where}.sales_tax_bp", str(exc), "invalid_line")]
                ) from exc
            if amounts.payable < 0:
                raise GuardFailedError(
                    f"Line {index + 1}: the withholdings come to more than the amount.",
                    code=ErrorCode.PAYABLE_NEGATIVE,
                    errors=[FieldError(where, "The amount payable would be negative.", "payable_negative")],
                )
            priced.append(
                PricedLine(
                    line_no=index + 1,
                    item=line["item"],
                    category=line["category"],
                    quantity=line["quantity"],
                    rate=line["rate"],
                    sales_tax_bp=line["sales_tax_bp"],
                    amounts=amounts,
                    sales_rule_id=sales_rule.id,
                    sales_rate_bp=sales_rule.rate_bp,
                    income_rule_id=income_rule.id,
                    income_rate_bp=income_rule.rate_bp,
                )
            )
        totals = total_lines([p.amounts for p in priced])
        if totals.gross > MAX_AMOUNT:
            raise ValidationFailedError(
                "The purchase is larger than the system can hold.",
                errors=[FieldError("lines", "Reduce the quantities or rates.", "too_large")],
            )
        kind = PurchaseKind.TAX_INVOICE if registered else PurchaseKind.PURCHASE_MEMO
        return Pricing(kind=kind, registered=registered, filer=filer, lines=priced, totals=totals)

    @staticmethod
    def _header(pricing: Pricing) -> dict[str, Decimal]:
        t = pricing.totals
        return {
            "subtotal": t.subtotal,
            "sales_tax_total": t.sales_tax,
            "gross_total": t.gross,
            "sales_tax_withheld": t.sales_tax_withheld,
            "income_tax_withheld": t.income_tax_withheld,
            "payable": t.payable,
        }

    def _add_lines(self, purchase: Purchase, pricing: Pricing) -> None:
        for line in pricing.lines:
            purchase.lines.append(
                PurchaseLine(
                    line_no=line.line_no,
                    item=line.item,
                    category=line.category,
                    quantity=line.quantity,
                    rate=line.rate,
                    sales_tax_bp=line.sales_tax_bp,
                    subtotal=line.amounts.subtotal,
                    sales_tax=line.amounts.sales_tax,
                    gross=line.amounts.gross,
                    sales_withholding_rule_id=line.sales_rule_id,
                    sales_withholding_bp=line.sales_rate_bp,
                    sales_tax_withheld=line.amounts.sales_tax_withheld,
                    income_withholding_rule_id=line.income_rule_id,
                    income_withholding_bp=line.income_rate_bp,
                    income_tax_withheld=line.amounts.income_tax_withheld,
                    payable=line.amounts.payable,
                )
            )
        self._session.flush()

    def _snapshot(self, purchase: Purchase) -> JsonDict:
        values = snapshot(purchase, FIELDS)
        values["totals"] = {
            "gross_total": str(purchase.gross_total),
            "sales_tax_withheld": str(purchase.sales_tax_withheld),
            "income_tax_withheld": str(purchase.income_tax_withheld),
            "payable": str(purchase.payable),
        }
        values["lines"] = [
            {"item": line.item, "category": line.category.value, "quantity": str(line.quantity), "rate": str(line.rate)}
            for line in purchase.lines
        ]
        return values
