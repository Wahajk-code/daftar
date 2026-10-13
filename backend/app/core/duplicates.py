"""When two documents look alike. A warning is advice shown to the person deciding; it never blocks a save, a submit
or an approval (domain rules section 8).

"About the same amount" is within 1 per cent, and "nearby" is within 7 days either side of the document date. Both are
judgement calls, recorded in decisions.md, and used by the queries in `repositories/duplicates.py`."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import Final

from app.core.enums import DocumentStatus, DocumentType

AMOUNT_TOLERANCE_PERCENT: Final = 1
DATE_WINDOW_DAYS: Final = 7


class DuplicateKind(StrEnum):
    SAME_INVOICE = "same_invoice"  # the same vendor and the same invoice number
    SIMILAR = "similar"  # about the same amount, close in date (same vendor, or same author and category)
    SAME_RECEIPT = "same_receipt"  # a receipt with identical content (SHA-256)


@dataclass(frozen=True)
class DuplicateWarning:
    kind: DuplicateKind
    document_type: DocumentType
    document_id: int
    status: DocumentStatus
    document_date: date
    amount: Decimal
    reason: str
