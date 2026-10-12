"""The double-entry arithmetic, with no database. A voucher is balanced when its debits equal its credits to the paisa.

The builders turn an approved expense or purchase into the lines of a payment voucher. Every builder returns lines that
balance by construction; the database checks it again at commit."""

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

from app.core.allocation import largest_remainder
from app.core.money import ZERO, from_paisa, to_paisa

Side = Literal["debit", "credit"]


class LedgerError(ValueError):
    """The lines cannot be built from what was given."""


@dataclass(frozen=True)
class LineSpec:
    account_id: int
    debit: Decimal = ZERO
    credit: Decimal = ZERO
    description: str | None = None
    cost_center_id: int | None = None
    project_id: int | None = None


@dataclass(frozen=True)
class Balance:
    debit: Decimal
    credit: Decimal

    @property
    def difference(self) -> Decimal:
        """Debits less credits. Positive means credits are short."""
        return self.debit - self.credit

    @property
    def balanced(self) -> bool:
        return self.debit == self.credit


def balance(lines: Sequence[LineSpec]) -> Balance:
    return Balance(
        debit=sum((line.debit for line in lines), ZERO),
        credit=sum((line.credit for line in lines), ZERO),
    )


def offsetting_line(lines: Sequence[LineSpec]) -> tuple[Side, Decimal] | None:
    """The one line that would balance these, or None if they already do: the side to put it on and its exact amount."""
    difference = balance(lines).difference
    if difference == 0:
        return None
    return ("credit", difference) if difference > 0 else ("debit", -difference)


def reverse(lines: Sequence[LineSpec], note: str | None = None) -> list[LineSpec]:
    """The mirror image: every debit becomes a credit of the same amount and the other way round."""
    return [
        LineSpec(
            account_id=line.account_id,
            debit=line.credit,
            credit=line.debit,
            description=note or line.description,
            cost_center_id=line.cost_center_id,
            project_id=line.project_id,
        )
        for line in lines
    ]


def expense_lines(
    *,
    amount: Decimal,
    tax_amount: Decimal,
    expense_account_id: int,
    input_tax_account_id: int,
    payment_account_id: int,
    project_id: int | None,
    cost_center_id: int | None,
    split: Sequence[tuple[int, int]] | None,
    description: str,
) -> list[LineSpec]:
    """A payment voucher for an approved expense.

    The expense account takes the amount less the tax, the tax goes to its own line (never split), and cash or bank is
    credited for the whole amount. An indirect expense passes `split`, pairs of (cost centre, weight); the net amount is
    shared out over them by the largest-remainder rule, so with no tax it reproduces the approved allocation exactly."""
    net = amount - tax_amount
    if net <= 0:
        raise LedgerError("the tax is the whole amount, so there is nothing to post to an expense account")
    lines: list[LineSpec] = []
    if split is None:
        lines.append(
            LineSpec(
                account_id=expense_account_id,
                debit=net,
                description=description,
                project_id=project_id,
                cost_center_id=cost_center_id,
            )
        )
    else:
        for share in largest_remainder(to_paisa(net), list(split)):
            if share.paisa > 0:
                lines.append(
                    LineSpec(
                        account_id=expense_account_id,
                        debit=from_paisa(share.paisa),
                        description=description,
                        cost_center_id=share.bucket_id,
                    )
                )
    if tax_amount > 0:
        lines.append(
            LineSpec(account_id=input_tax_account_id, debit=tax_amount, description="Sales tax on " + description)
        )
    lines.append(LineSpec(account_id=payment_account_id, credit=amount, description=description))
    return lines


def purchase_lines(
    *,
    subtotal: Decimal,
    sales_tax: Decimal,
    payable: Decimal,
    sales_tax_withheld: Decimal,
    income_tax_withheld: Decimal,
    expense_account_id: int,
    input_tax_account_id: int,
    payment_account_id: int,
    sales_tax_withheld_account_id: int,
    income_tax_withheld_account_id: int,
    description: str,
) -> list[LineSpec]:
    """A payment voucher for an approved purchase.

    Debits: the purchase at its subtotal, and the sales tax on its own line. Credits: what is paid to the vendor, and
    each withholding on its own liability line, never netted. A purchase's own arithmetic makes these balance:
    subtotal + sales tax = payable + both withholdings."""
    lines = [LineSpec(account_id=expense_account_id, debit=subtotal, description=description)]
    if sales_tax > 0:
        lines.append(
            LineSpec(account_id=input_tax_account_id, debit=sales_tax, description="Sales tax on " + description)
        )
    if payable > 0:
        lines.append(LineSpec(account_id=payment_account_id, credit=payable, description=description))
    if sales_tax_withheld > 0:
        lines.append(
            LineSpec(
                account_id=sales_tax_withheld_account_id, credit=sales_tax_withheld, description="Sales tax withheld"
            )
        )
    if income_tax_withheld > 0:
        lines.append(
            LineSpec(
                account_id=income_tax_withheld_account_id, credit=income_tax_withheld, description="Income tax withheld"
            )
        )
    return lines
