from decimal import Decimal

import pytest
from hypothesis import given
from hypothesis import strategies as st

from app.core.tax import LineError, compute_line, total_lines


def line(**overrides: object) -> object:
    values: dict[str, object] = {
        "quantity": Decimal("1"),
        "rate": Decimal("100.00"),
        "sales_tax_bp": 0,
        "supplier_registered": True,
        "sales_withholding_bp": 2000,
        "income_withholding_bp": 450,
    }
    return compute_line(**{**values, **overrides})  # type: ignore[arg-type]


def test_registered_supplier_worked_example() -> None:
    result = compute_line(
        quantity=Decimal("3.500"),
        rate=Decimal("1200.00"),
        sales_tax_bp=1800,
        supplier_registered=True,
        sales_withholding_bp=2000,
        income_withholding_bp=450,
    )
    assert result.subtotal == Decimal("4200.00")
    assert result.sales_tax == Decimal("756.00")
    assert result.gross == Decimal("4956.00")
    assert result.sales_tax_withheld == Decimal("151.20")  # one fifth of the sales tax
    assert result.income_tax_withheld == Decimal("223.02")  # 4.5% of the gross, tax included
    assert result.payable == Decimal("4581.78")


def test_unregistered_supplier_is_withheld_on_the_gross_value() -> None:
    result = compute_line(
        quantity=Decimal("1"),
        rate=Decimal("10000.00"),
        sales_tax_bp=0,
        supplier_registered=False,
        sales_withholding_bp=1800,
        income_withholding_bp=1800,
    )
    assert result.sales_tax == Decimal("0.00")
    assert result.sales_tax_withheld == Decimal("1800.00")
    assert result.income_tax_withheld == Decimal("1800.00")
    assert result.payable == Decimal("6400.00")


def test_an_unregistered_supplier_cannot_charge_sales_tax() -> None:
    with pytest.raises(LineError, match="unregistered"):
        compute_line(
            quantity=Decimal("1"),
            rate=Decimal("100.00"),
            sales_tax_bp=1800,
            supplier_registered=False,
            sales_withholding_bp=1800,
            income_withholding_bp=0,
        )


@pytest.mark.parametrize(("quantity", "rate"), [("0", "10.00"), ("1", "0.00"), ("-1", "10.00"), ("0.001", "1.00")])
def test_a_line_must_come_to_something(quantity: str, rate: str) -> None:
    with pytest.raises(LineError):
        compute_line(
            quantity=Decimal(quantity),
            rate=Decimal(rate),
            sales_tax_bp=0,
            supplier_registered=True,
            sales_withholding_bp=0,
            income_withholding_bp=0,
        )


def test_each_figure_is_rounded_half_up_once() -> None:
    result = compute_line(
        quantity=Decimal("1"),
        rate=Decimal("0.35"),  # 0.35 * 5% = 0.0175 -> 0.02
        sales_tax_bp=500,
        supplier_registered=True,
        sales_withholding_bp=0,
        income_withholding_bp=0,
    )
    assert result.sales_tax == Decimal("0.02")
    assert result.gross == Decimal("0.37")


def test_the_header_is_the_exact_sum_of_the_lines() -> None:
    first = line(rate=Decimal("33.33"), sales_tax_bp=1800)
    second = line(rate=Decimal("66.67"), sales_tax_bp=1800)
    total = total_lines([first, second])  # type: ignore[list-item]
    assert total.subtotal == first.subtotal + second.subtotal  # type: ignore[attr-defined]
    assert total.payable == first.payable + second.payable  # type: ignore[attr-defined]


@given(
    quantity=st.decimals(min_value=Decimal("0.001"), max_value=Decimal("1000"), places=3),
    rate=st.decimals(min_value=Decimal("0.01"), max_value=Decimal("100000"), places=2),
    tax_bp=st.integers(min_value=0, max_value=3000),
    sales_bp=st.integers(min_value=0, max_value=2500),
    income_bp=st.integers(min_value=0, max_value=2500),
    registered=st.booleans(),
)
def test_every_line_adds_up(
    quantity: Decimal, rate: Decimal, tax_bp: int, sales_bp: int, income_bp: int, registered: bool
) -> None:
    try:
        result = compute_line(
            quantity=quantity,
            rate=rate,
            sales_tax_bp=tax_bp if registered else 0,
            supplier_registered=registered,
            sales_withholding_bp=sales_bp,
            income_withholding_bp=income_bp,
        )
    except LineError:
        return  # a line that rounds to nothing is refused, which is the point
    assert result.gross == result.subtotal + result.sales_tax
    assert result.payable == result.gross - result.sales_tax_withheld - result.income_tax_withheld
    assert min(result.subtotal, result.sales_tax, result.sales_tax_withheld, result.income_tax_withheld) >= 0
    for figure in (result.subtotal, result.sales_tax, result.gross, result.payable):
        assert figure == figure.quantize(Decimal("0.01"))
