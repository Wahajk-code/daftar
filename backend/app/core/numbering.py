"""Voucher numbers: {type}-{year}-{sequence:04d}, for example PV-2026-0007.

The year comes from the document date, never from the clock. A number is given only when a voucher is posted
(docs/domain-rules.md section 3), by the counter row in the database; this module only works out the year and the
text."""

from datetime import date

from app.core.enums import VoucherType, YearMode

FISCAL_YEAR_STARTS_IN = 7  # July


def voucher_year(document_date: date, mode: YearMode) -> int:
    """The year a voucher dated `document_date` is numbered in.

    Calendar mode is the date's own year. Fiscal mode runs July to June and is named by the year it ends in, as the tax
    year is: 1 July 2025 to 30 June 2026 is 2026."""
    if mode is YearMode.CALENDAR:
        return document_date.year
    return document_date.year + 1 if document_date.month >= FISCAL_YEAR_STARTS_IN else document_date.year


def format_number(voucher_type: VoucherType, year: int, sequence: int) -> str:
    return f"{voucher_type.value}-{year}-{sequence:04d}"
