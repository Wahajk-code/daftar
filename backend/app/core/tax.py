"""What a purchase line comes to, in Decimal, rounded once per figure (docs/domain-rules.md section 5).

Each line is computed on its own; the header is the exact sum of its lines. Two withholdings come off the payment:
- sales tax withholding: for a registered supplier, a share of the sales tax shown on the invoice; for an unregistered
  one, a rate on the gross value, because no sales tax was charged;
- income tax withholding (section 153): a rate on the gross amount including sales tax.
Both come out of the amount payable to the supplier."""

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal

from app.core.money import ZERO, percent_of, round_money


class LineError(ValueError):
    """A line that cannot be priced."""


@dataclass(frozen=True)
class LineAmounts:
    subtotal: Decimal
    sales_tax: Decimal
    gross: Decimal
    sales_tax_withheld: Decimal
    income_tax_withheld: Decimal
    payable: Decimal


def compute_line(
    *,
    quantity: Decimal,
    rate: Decimal,
    sales_tax_bp: int,
    supplier_registered: bool,
    sales_withholding_bp: int,
    income_withholding_bp: int,
) -> LineAmounts:
    if quantity <= 0 or rate <= 0:
        raise LineError("quantity and rate must be positive")
    if sales_tax_bp and not supplier_registered:
        raise LineError("an unregistered supplier charges no sales tax")
    subtotal = round_money(quantity * rate)
    if subtotal <= 0:
        raise LineError("the line comes to less than one paisa")
    sales_tax = percent_of(subtotal, sales_tax_bp)
    gross = subtotal + sales_tax
    sales_base = sales_tax if supplier_registered else gross
    sales_tax_withheld = percent_of(sales_base, sales_withholding_bp)
    income_tax_withheld = percent_of(gross, income_withholding_bp)
    return LineAmounts(
        subtotal=subtotal,
        sales_tax=sales_tax,
        gross=gross,
        sales_tax_withheld=sales_tax_withheld,
        income_tax_withheld=income_tax_withheld,
        payable=gross - sales_tax_withheld - income_tax_withheld,
    )


def total_lines(lines: Sequence[LineAmounts]) -> LineAmounts:
    """The header: each figure is the exact sum of the same figure on the lines."""
    return LineAmounts(
        subtotal=sum((line.subtotal for line in lines), ZERO),
        sales_tax=sum((line.sales_tax for line in lines), ZERO),
        gross=sum((line.gross for line in lines), ZERO),
        sales_tax_withheld=sum((line.sales_tax_withheld for line in lines), ZERO),
        income_tax_withheld=sum((line.income_tax_withheld for line in lines), ZERO),
        payable=sum((line.payable for line in lines), ZERO),
    )
