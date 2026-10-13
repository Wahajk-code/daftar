from datetime import date, timedelta
from decimal import Decimal

import pytest
from hypothesis import given
from hypothesis import strategies as st

from app.core.enums import VoucherType
from app.core.ledger import (
    LedgerError,
    LineSpec,
    balance,
    expense_lines,
    offsetting_line,
    purchase_lines,
    reverse,
)
from app.core.numbering import format_number, voucher_year

D = Decimal


# Numbering (E3) ------------------------------------------------------------------------------------------------------


def test_e3_numbers_read_type_year_and_four_digit_sequence() -> None:
    assert format_number(VoucherType.PAYMENT, 2026, 1) == "PV-2026-0001"
    assert format_number(VoucherType.RECEIPT, 2026, 42) == "RV-2026-0042"
    assert format_number(VoucherType.JOURNAL, 2031, 12345) == "JV-2031-12345"  # grows past four digits, never truncates


@pytest.mark.parametrize(
    ("day", "year"),
    [(date(2026, 1, 1), 2026), (date(2026, 6, 30), 2026), (date(2026, 7, 1), 2026), (date(2026, 12, 31), 2026)],
)
def test_e3_month_one_is_the_calendar_year_the_dates_own(day: date, year: int) -> None:
    assert voucher_year(day, 1) == year


@pytest.mark.parametrize(
    ("day", "year"),
    [
        (date(2025, 7, 1), 2026),  # the first day of the fiscal year that ends in June 2026
        (date(2026, 6, 30), 2026),  # its last day
        (date(2026, 7, 1), 2027),
        (date(2026, 1, 15), 2026),
        (date(2026, 12, 31), 2027),
    ],
)
def test_e3_a_july_start_runs_july_to_june_and_is_named_by_the_year_it_ends(day: date, year: int) -> None:
    assert voucher_year(day, 7) == year


@pytest.mark.parametrize(
    ("start", "day", "year"),
    [
        (4, date(2026, 3, 31), 2026),  # an April to March year ends in March 2026
        (4, date(2026, 4, 1), 2027),
        (10, date(2026, 9, 30), 2026),  # October to September
        (10, date(2026, 10, 1), 2027),
        (12, date(2026, 12, 1), 2027),  # a December start: the last month already belongs to the next year
        (12, date(2026, 11, 30), 2026),
        (2, date(2026, 1, 31), 2026),
        (2, date(2026, 2, 1), 2027),
    ],
)
def test_e3_any_start_month_names_the_year_by_the_year_it_ends(start: int, day: date, year: int) -> None:
    assert voucher_year(day, start) == year


@given(
    day=st.dates(min_value=date(2000, 1, 1), max_value=date(2099, 12, 31)), start=st.integers(min_value=2, max_value=12)
)
def test_e3_a_numbering_year_is_one_year_long_and_follows_the_calendar(day: date, start: int) -> None:
    """The label never jumps back, and a date is at most one year ahead of the calendar."""
    assert voucher_year(day, start) - day.year in (0, 1)
    next_day = day + timedelta(days=1)
    assert voucher_year(next_day, start) - voucher_year(day, start) in (0, 1)


@pytest.mark.parametrize("start", [0, 13, -1])
def test_e3_a_start_month_must_be_a_real_month(start: int) -> None:
    with pytest.raises(ValueError, match="1 to 12"):
        voucher_year(date(2026, 1, 1), start)


# Balance and reversal (E2, E6) ---------------------------------------------------------------------------------------


def line(account: int, debit: str = "0.00", credit: str = "0.00") -> LineSpec:
    return LineSpec(account_id=account, debit=D(debit), credit=D(credit))


def test_e2_balanced_lines_have_no_offsetting_line() -> None:
    lines = [line(1, debit="100.00"), line(2, credit="60.00"), line(3, credit="40.00")]
    assert balance(lines).balanced
    assert offsetting_line(lines) is None


def test_e2_the_offsetting_line_is_exact_and_on_the_short_side() -> None:
    short_credit = [line(1, debit="100.00"), line(2, credit="99.99")]
    assert balance(short_credit).difference == D("0.01")
    assert offsetting_line(short_credit) == ("credit", D("0.01"))
    short_debit = [line(1, debit="10.50"), line(2, credit="500.25")]
    assert offsetting_line(short_debit) == ("debit", D("489.75"))


@given(
    st.lists(
        st.tuples(st.sampled_from(["debit", "credit"]), st.decimals(min_value="0.01", max_value="99999.99", places=2)),
        min_size=1,
        max_size=12,
    )
)
def test_e2_adding_the_offsetting_line_always_balances(entries: list[tuple[str, Decimal]]) -> None:
    lines = [line(1, debit=str(a)) if side == "debit" else line(1, credit=str(a)) for side, a in entries]
    fix = offsetting_line(lines)
    if fix is not None:
        side, amount = fix
        lines.append(line(2, debit=str(amount)) if side == "debit" else line(2, credit=str(amount)))
    assert balance(lines).balanced


def test_e6_a_reversal_swaps_every_side_and_keeps_everything_else() -> None:
    original = [
        LineSpec(account_id=1, debit=D("100.00"), description="Rent", cost_center_id=7, project_id=9),
        LineSpec(account_id=2, credit=D("100.00")),
    ]
    mirror = reverse(original, note="Reversal of PV-2026-0001")
    assert [(m.account_id, m.debit, m.credit) for m in mirror] == [
        (1, D("0.00"), D("100.00")),
        (2, D("100.00"), D("0.00")),
    ]
    assert (mirror[0].cost_center_id, mirror[0].project_id) == (7, 9)
    assert all(m.description == "Reversal of PV-2026-0001" for m in mirror)
    assert balance(mirror).balanced
    combined = original + mirror
    assert {a: sum(x.debit - x.credit for x in combined if x.account_id == a) for a in (1, 2)} == {1: 0, 2: 0}


# Generated lines (E4) ------------------------------------------------------------------------------------------------


def expense(**overrides: object) -> list[LineSpec]:
    values: dict[str, object] = {
        "amount": D("1000.00"),
        "tax_amount": D("0.00"),
        "expense_account_id": 10,
        "input_tax_account_id": 11,
        "payment_account_id": 12,
        "project_id": None,
        "cost_center_id": 5,
        "split": None,
        "description": "Printer paper",
        **overrides,
    }
    return expense_lines(**values)  # type: ignore[arg-type]


def test_e4_a_direct_expense_debits_the_expense_and_credits_the_payment_account() -> None:
    lines = expense()
    assert [(x.account_id, x.debit, x.credit, x.cost_center_id) for x in lines] == [
        (10, D("1000.00"), D("0.00"), 5),
        (12, D("0.00"), D("1000.00"), None),
    ]


def test_e4_the_tax_is_its_own_line_and_the_expense_gets_the_net() -> None:
    lines = expense(amount=D("1180.00"), tax_amount=D("180.00"))
    assert [(x.account_id, x.debit, x.credit) for x in lines] == [
        (10, D("1000.00"), D("0.00")),
        (11, D("180.00"), D("0.00")),
        (12, D("0.00"), D("1180.00")),
    ]
    assert balance(lines).balanced


def test_e4_an_indirect_expense_reproduces_its_approved_split() -> None:
    lines = expense(amount=D("100.00"), cost_center_id=None, split=[(1, 3333), (2, 3333), (3, 3334)])
    assert [(x.cost_center_id, x.debit) for x in lines if x.debit] == [
        (1, D("33.33")),
        (2, D("33.33")),
        (3, D("33.34")),
    ]
    assert balance(lines).balanced


def test_e4_the_tax_line_is_never_split_across_cost_centres() -> None:
    lines = expense(amount=D("118.00"), tax_amount=D("18.00"), cost_center_id=None, split=[(1, 5000), (2, 5000)])
    debits = [(x.account_id, x.cost_center_id, x.debit) for x in lines if x.debit]
    assert debits == [(10, 1, D("50.00")), (10, 2, D("50.00")), (11, None, D("18.00"))]


def test_e4_a_fixed_split_is_followed_in_proportion() -> None:
    lines = expense(
        amount=D("100.00"), cost_center_id=None, split=[(1, 6010), (2, 3990)]
    )  # the approved amounts in paisa
    assert [(x.cost_center_id, x.debit) for x in lines if x.debit] == [(1, D("60.10")), (2, D("39.90"))]


def test_e4_an_expense_that_is_all_tax_cannot_be_posted() -> None:
    with pytest.raises(LedgerError, match="tax is the whole amount"):
        expense(amount=D("100.00"), tax_amount=D("100.00"))


@given(
    amount=st.decimals(min_value="1.00", max_value="999999.99", places=2),
    tax_share=st.integers(min_value=0, max_value=90),
    weights=st.lists(st.integers(min_value=1, max_value=10_000), min_size=1, max_size=6),
)
def test_e4_a_generated_expense_voucher_always_balances(amount: Decimal, tax_share: int, weights: list[int]) -> None:
    tax = (amount * tax_share / 100).quantize(D("0.01"))
    lines = expense(
        amount=amount, tax_amount=tax, cost_center_id=None, split=[(i + 1, w) for i, w in enumerate(weights)]
    )
    assert balance(lines).balanced
    assert sum(x.debit for x in lines) == amount


def test_e4_a_purchase_keeps_each_withholding_on_its_own_credit_line() -> None:
    lines = purchase_lines(
        subtotal=D("4200.00"),
        sales_tax=D("756.00"),
        payable=D("4581.78"),
        sales_tax_withheld=D("151.20"),
        income_tax_withheld=D("223.02"),
        expense_account_id=10,
        input_tax_account_id=11,
        payment_account_id=12,
        sales_tax_withheld_account_id=13,
        income_tax_withheld_account_id=14,
        description="Paper",
    )
    assert [(x.account_id, x.debit, x.credit) for x in lines] == [
        (10, D("4200.00"), D("0.00")),
        (11, D("756.00"), D("0.00")),
        (12, D("0.00"), D("4581.78")),
        (13, D("0.00"), D("151.20")),
        (14, D("0.00"), D("223.02")),
    ]
    assert balance(lines).balanced


def test_e4_a_purchase_without_tax_or_withholding_has_two_lines() -> None:
    lines = purchase_lines(
        subtotal=D("500.00"),
        sales_tax=D("0.00"),
        payable=D("500.00"),
        sales_tax_withheld=D("0.00"),
        income_tax_withheld=D("0.00"),
        expense_account_id=10,
        input_tax_account_id=11,
        payment_account_id=12,
        sales_tax_withheld_account_id=13,
        income_tax_withheld_account_id=14,
        description="Cartage",
    )
    assert [x.account_id for x in lines] == [10, 12]
