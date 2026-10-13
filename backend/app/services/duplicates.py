"""Duplicate warnings for an expense or a purchase. Advice only: nothing here blocks or changes a document."""

from typing import Any

from sqlalchemy import Row
from sqlalchemy.orm import Session

from app.core.duplicates import DuplicateKind, DuplicateWarning
from app.core.enums import DocumentType
from app.models.documents import Expense, Purchase
from app.repositories import duplicates as duplicate_repository

NAMES = {DocumentType.EXPENSE: "Expense", DocumentType.PURCHASE: "Purchase"}


def _warning(kind: DuplicateKind, document_type: DocumentType, row: Row[Any], reason: str) -> DuplicateWarning:
    return DuplicateWarning(
        kind=kind,
        document_type=document_type,
        document_id=row.id,
        status=row.status,
        document_date=row.document_date,
        amount=row.amount,
        reason=reason,
    )


class DuplicateFinder:
    def __init__(self, session: Session) -> None:
        self._session = session

    def for_purchase(self, purchase: Purchase) -> list[DuplicateWarning]:
        found: list[DuplicateWarning] = []
        for row in duplicate_repository.purchases_with_invoice(self._session, purchase):
            reason = f"Purchase {row.id} from the same vendor already uses invoice number {purchase.invoice_number}."
            found.append(_warning(DuplicateKind.SAME_INVOICE, DocumentType.PURCHASE, row, reason))
        for row in duplicate_repository.similar_purchases(self._session, purchase):
            reason = f"Purchase {row.id} from the same vendor is {row.amount:,.2f} on {row.document_date.isoformat()}."
            found.append(_warning(DuplicateKind.SIMILAR, DocumentType.PURCHASE, row, reason))
        found += self._receipts(purchase_id=purchase.id, expense_id=None, only_author=None)
        return found

    def for_expense(self, expense: Expense, *, only_author: int | None) -> list[DuplicateWarning]:
        """`only_author` limits what is shown to documents that person may see (Staff see only their own)."""
        found: list[DuplicateWarning] = []
        for row in duplicate_repository.similar_expenses(self._session, expense, only_author=only_author):
            reason = f"Expense {row.id} in the same category is {row.amount:,.2f} on {row.document_date.isoformat()}."
            found.append(_warning(DuplicateKind.SIMILAR, DocumentType.EXPENSE, row, reason))
        found += self._receipts(purchase_id=None, expense_id=expense.id, only_author=only_author)
        return found

    def _receipts(
        self, *, expense_id: int | None, purchase_id: int | None, only_author: int | None
    ) -> list[DuplicateWarning]:
        found: list[DuplicateWarning] = []
        for row in duplicate_repository.expenses_sharing_a_receipt(
            self._session, expense_id=expense_id, purchase_id=purchase_id, only_author=only_author
        ):
            reason = f"Expense {row.id} holds a receipt identical to one on this document."
            found.append(_warning(DuplicateKind.SAME_RECEIPT, DocumentType.EXPENSE, row, reason))
        if only_author is None:  # Staff have no access to purchases, so they are never told about one
            for row in duplicate_repository.purchases_sharing_a_receipt(
                self._session, expense_id=expense_id, purchase_id=purchase_id
            ):
                reason = f"Purchase {row.id} holds a receipt identical to one on this document."
                found.append(_warning(DuplicateKind.SAME_RECEIPT, DocumentType.PURCHASE, row, reason))
        return found
