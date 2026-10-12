"""The rules the database holds for vouchers, each reached by going around the service.

The balance trigger is deferred, so it only fires at commit; these tests never commit and call SET CONSTRAINTS ALL
IMMEDIATE (`settle_constraints`) to make the database check now. Every test that expects a refusal does exactly one
refused statement, because a refused statement aborts the transaction."""

from collections.abc import Callable
from typing import Any

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.enums import Role
from app.models.user import User
from tests.support.database import settle_constraints
from tests.support.documents import Ledger, Lookups, create_ledger, create_lookups

Make = Callable[..., User]


@pytest.fixture
def lookups(db_session: Session, make: Make) -> Lookups:
    return create_lookups(db_session, make(Role.ADMIN))


@pytest.fixture
def ledger(db_session: Session, make: Make, lookups: Lookups) -> Ledger:
    return create_ledger(db_session, lookups, make(Role.ADMIN))


@pytest.fixture
def author(make: Make) -> User:
    return make(Role.ACCOUNTANT)


def new_voucher(session: Session, author: User, **columns: Any) -> int:
    """Insert straight into the table, the way a script that skips the service would. Pass any column as a keyword."""
    names = ["voucher_type", "created_by", "document_date", *columns]
    values = ["CAST(:voucher_type AS voucher_type)", ":created_by", "'2026-10-12'"]
    values += ["CAST(:status AS document_status)" if name == "status" else f":{name}" for name in columns]
    return int(
        session.execute(
            text(f"INSERT INTO vouchers ({', '.join(names)}) VALUES ({', '.join(values)}) RETURNING id"),
            {"voucher_type": "PV", "created_by": author.id, **columns},
        ).scalar_one()
    )


def add_line(
    session: Session, voucher_id: int, line_no: int, account_id: int, debit: str = "0", credit: str = "0"
) -> None:
    session.execute(
        text("INSERT INTO voucher_lines (voucher_id, line_no, account_id, debit, credit) VALUES (:v, :n, :a, :d, :c)"),
        {"v": voucher_id, "n": line_no, "a": account_id, "d": debit, "c": credit},
    )


def balanced(session: Session, author: User, ledger: Ledger, amount: str = "100.00", **columns: Any) -> int:
    voucher = new_voucher(session, author, **columns)
    add_line(session, voucher, 1, ledger.expense.id, debit=amount)
    add_line(session, voucher, 2, ledger.cash.id, credit=amount)
    return voucher


def post(session: Session, voucher_id: int, seq: int = 1, key: str | None = None) -> None:
    """Turn a draft into a posted voucher by writing the columns directly, the way a careless script would."""
    session.execute(
        text(
            "UPDATE vouchers SET status = 'posted', number = 'PV-2026-' || lpad(CAST(:s AS text), 4, '0'), year = 2026,"
            " seq = :s, post_key = :k WHERE id = :v"
        ),
        {"s": seq, "v": voucher_id, "k": key},
    )


def posted(session: Session, author: User, ledger: Ledger, seq: int = 1, **columns: Any) -> int:
    voucher = balanced(session, author, ledger, **columns)
    settle_constraints(session)
    session.execute(text("SET CONSTRAINTS ALL DEFERRED"))
    post(session, voucher, seq)
    return voucher


def new_expense(session: Session, lookups: Lookups, author: User) -> int:
    return int(
        session.execute(
            text(
                "INSERT INTO expenses (expense_type, created_by, document_date, category_id, amount, payment_method,"
                " cost_center_id) VALUES ('direct', :by, '2026-10-12', :cat, 100.00, 'cash', :cc) RETURNING id"
            ),
            {"by": author.id, "cat": lookups.category.id, "cc": lookups.centres[0].id},
        ).scalar_one()
    )


def new_purchase(session: Session, lookups: Lookups, author: User) -> int:
    return int(
        session.execute(
            text(
                "INSERT INTO purchases (vendor_id, created_by, document_date, document_kind, vendor_registered,"
                " vendor_filer, subtotal, sales_tax_total, gross_total, sales_tax_withheld, income_tax_withheld,"
                " payable)"
                " VALUES (:v, :u, '2026-10-12', 'purchase_memo', false, false, 100, 0, 100, 0, 0, 100) RETURNING id"
            ),
            {"v": lookups.vendors["unreg_nonfiler"].id, "u": author.id},
        ).scalar_one()
    )


# E2: debits equal credits, from every side ---------------------------------------------------------------------------


def test_a_balanced_voucher_passes_the_check(db_session: Session, author: User, ledger: Ledger) -> None:
    balanced(db_session, author, ledger)
    settle_constraints(db_session)


def test_lines_that_do_not_balance_are_refused_at_commit(db_session: Session, author: User, ledger: Ledger) -> None:
    voucher = new_voucher(db_session, author)
    add_line(db_session, voucher, 1, ledger.expense.id, debit="100.00")
    add_line(db_session, voucher, 2, ledger.cash.id, credit="99.99")
    with pytest.raises(IntegrityError, match="voucher_balanced"):
        settle_constraints(db_session)


def test_the_check_waits_for_the_last_line_so_lines_can_arrive_one_at_a_time(
    db_session: Session, author: User, ledger: Ledger
) -> None:
    """The reason the trigger is deferred: after the first line the voucher is out of balance, and that is fine."""
    voucher = new_voucher(db_session, author)
    add_line(db_session, voucher, 1, ledger.expense.id, debit="100.00")
    add_line(db_session, voucher, 2, ledger.cash.id, credit="60.00")
    add_line(db_session, voucher, 3, ledger.bank.id, credit="40.00")
    settle_constraints(db_session)


def test_changing_one_amount_later_is_caught(db_session: Session, author: User, ledger: Ledger) -> None:
    voucher = balanced(db_session, author, ledger)
    settle_constraints(db_session)
    db_session.execute(text("SET CONSTRAINTS ALL DEFERRED"))
    db_session.execute(
        text("UPDATE voucher_lines SET credit = 90.00 WHERE voucher_id = :v AND line_no = 2"), {"v": voucher}
    )
    with pytest.raises(IntegrityError, match="voucher_balanced"):
        settle_constraints(db_session)


def test_removing_one_line_of_a_draft_is_caught(db_session: Session, author: User, ledger: Ledger) -> None:
    voucher = balanced(db_session, author, ledger)
    settle_constraints(db_session)
    db_session.execute(text("SET CONSTRAINTS ALL DEFERRED"))
    db_session.execute(text("DELETE FROM voucher_lines WHERE voucher_id = :v AND line_no = 2"), {"v": voucher})
    with pytest.raises(IntegrityError, match="voucher_balanced"):
        settle_constraints(db_session)


def test_replacing_all_lines_with_a_balanced_set_is_allowed(db_session: Session, author: User, ledger: Ledger) -> None:
    voucher = balanced(db_session, author, ledger)
    settle_constraints(db_session)
    db_session.execute(text("SET CONSTRAINTS ALL DEFERRED"))
    db_session.execute(text("DELETE FROM voucher_lines WHERE voucher_id = :v"), {"v": voucher})
    add_line(db_session, voucher, 1, ledger.other_expense.id, debit="250.00")
    add_line(db_session, voucher, 2, ledger.bank.id, credit="250.00")
    settle_constraints(db_session)


# E1: what a line is -------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("debit", "credit", "rule"),
    [
        ("10.00", "10.00", "exactly_one_side"),  # both sides
        ("0", "0", "exactly_one_side"),  # neither side
        ("-5.00", "0", "exactly_one_side"),  # negative
        ("0", "-5.00", "exactly_one_side"),
    ],
)
def test_a_line_has_exactly_one_positive_side(
    db_session: Session, author: User, ledger: Ledger, debit: str, credit: str, rule: str
) -> None:
    voucher = new_voucher(db_session, author)
    with pytest.raises(IntegrityError, match=rule):
        add_line(db_session, voucher, 1, ledger.expense.id, debit=debit, credit=credit)


def test_a_line_cannot_have_more_than_two_decimal_places_kept(
    db_session: Session, author: User, ledger: Ledger
) -> None:
    """NUMERIC(14,2) rounds rather than keeping a third place, so a sub-paisa amount cannot survive in the books."""
    voucher = new_voucher(db_session, author)
    add_line(db_session, voucher, 1, ledger.expense.id, debit="10.005")
    stored = db_session.execute(
        text("SELECT debit FROM voucher_lines WHERE voucher_id = :v"), {"v": voucher}
    ).scalar_one()
    assert str(stored) == "10.01"


def test_two_lines_cannot_share_a_line_number(db_session: Session, author: User, ledger: Ledger) -> None:
    voucher = new_voucher(db_session, author)
    add_line(db_session, voucher, 1, ledger.expense.id, debit="10.00")
    with pytest.raises(IntegrityError, match="one_voucher_line_per_number"):
        add_line(db_session, voucher, 1, ledger.cash.id, credit="10.00")


def test_a_line_cannot_post_to_a_parent_account(db_session: Session, author: User, ledger: Ledger) -> None:
    voucher = new_voucher(db_session, author)
    with pytest.raises(IntegrityError, match="voucher_line_account_postable"):
        add_line(db_session, voucher, 1, ledger.parent.id, debit="10.00")


def test_a_line_cannot_be_moved_to_a_parent_account(db_session: Session, author: User, ledger: Ledger) -> None:
    voucher = balanced(db_session, author, ledger)
    with pytest.raises(IntegrityError, match="voucher_line_account_postable"):
        db_session.execute(
            text("UPDATE voucher_lines SET account_id = :a WHERE voucher_id = :v AND line_no = 1"),
            {"a": ledger.parent.id, "v": voucher},
        )


def test_an_account_with_postings_cannot_stop_being_postable(db_session: Session, author: User, ledger: Ledger) -> None:
    """Closes the Pass 2 gap: the account tree check now knows about postings."""
    balanced(db_session, author, ledger)
    settle_constraints(db_session)
    db_session.execute(text("SET CONSTRAINTS ALL DEFERRED"))
    db_session.execute(text("UPDATE accounts SET is_postable = false WHERE id = :a"), {"a": ledger.expense.id})
    with pytest.raises(IntegrityError, match="has postings"):
        settle_constraints(db_session)


# E3: numbers ---------------------------------------------------------------------------------------------------------


def test_a_posted_voucher_must_have_a_number(db_session: Session, author: User) -> None:
    with pytest.raises(IntegrityError, match="numbered_iff_posted_or_void"):
        new_voucher(db_session, author, status="posted")


def test_a_draft_cannot_carry_a_number(db_session: Session, author: User) -> None:
    with pytest.raises(IntegrityError, match="numbered_iff_posted_or_void"):
        new_voucher(db_session, author, number="PV-2026-0001", year=2026, seq=1)


def test_the_parts_of_a_number_agree(db_session: Session, author: User) -> None:
    with pytest.raises(IntegrityError, match="number_parts_agree"):
        new_voucher(db_session, author, status="posted", number="PV-2026-0001", year=2026)


def test_a_number_is_given_once(db_session: Session, author: User, ledger: Ledger) -> None:
    posted(db_session, author, ledger, seq=1)
    other = balanced(db_session, author, ledger)
    settle_constraints(db_session)
    db_session.execute(text("SET CONSTRAINTS ALL DEFERRED"))
    with pytest.raises(IntegrityError, match="uq_vouchers_number"):
        db_session.execute(
            text("UPDATE vouchers SET status = 'posted', number = 'PV-2026-0001', year = 2026, seq = 2 WHERE id = :v"),
            {"v": other},
        )


def test_a_sequence_number_is_given_once_per_type_and_year(db_session: Session, author: User, ledger: Ledger) -> None:
    posted(db_session, author, ledger, seq=1)
    other = balanced(db_session, author, ledger)
    settle_constraints(db_session)
    db_session.execute(text("SET CONSTRAINTS ALL DEFERRED"))
    with pytest.raises(IntegrityError, match="one_number_per_type_year"):
        db_session.execute(
            text("UPDATE vouchers SET status = 'posted', number = 'PV-2026-OTHER', year = 2026, seq = 1 WHERE id = :v"),
            {"v": other},
        )


def test_the_counter_is_one_row_per_type_and_year(db_session: Session) -> None:
    insert = "INSERT INTO number_counters (voucher_type, year, last_seq) VALUES ('PV', 2026, 1)"
    db_session.execute(text(insert))
    with pytest.raises(IntegrityError, match="pk_number_counters"):
        db_session.execute(text(insert))


# E5: keys, sources, reversals ----------------------------------------------------------------------------------------


def test_a_post_key_is_used_once(db_session: Session, author: User, ledger: Ledger) -> None:
    first = balanced(db_session, author, ledger)
    second = balanced(db_session, author, ledger)
    settle_constraints(db_session)
    db_session.execute(text("SET CONSTRAINTS ALL DEFERRED"))
    post(db_session, first, seq=1, key="same-key-1")
    with pytest.raises(IntegrityError, match="uq_vouchers_post_key"):
        post(db_session, second, seq=2, key="same-key-1")


def test_a_post_key_needs_a_number(db_session: Session, author: User) -> None:
    with pytest.raises(IntegrityError, match="post_key_only_when_numbered"):
        new_voucher(db_session, author, post_key="a-key-alone")


def test_one_voucher_per_expense(db_session: Session, author: User, lookups: Lookups, ledger: Ledger) -> None:
    expense = new_expense(db_session, lookups, author)
    balanced(db_session, author, ledger, expense_id=expense)
    with pytest.raises(IntegrityError, match="uq_vouchers_expense_id"):
        balanced(db_session, author, ledger, expense_id=expense)


def test_one_voucher_per_purchase(db_session: Session, author: User, lookups: Lookups, ledger: Ledger) -> None:
    purchase = new_purchase(db_session, lookups, author)
    balanced(db_session, author, ledger, purchase_id=purchase)
    with pytest.raises(IntegrityError, match="uq_vouchers_purchase_id"):
        balanced(db_session, author, ledger, purchase_id=purchase)


def test_a_voucher_has_at_most_one_source(db_session: Session, author: User, lookups: Lookups) -> None:
    expense = new_expense(db_session, lookups, author)
    purchase = new_purchase(db_session, lookups, author)
    with pytest.raises(IntegrityError, match="at_most_one_source"):
        new_voucher(db_session, author, expense_id=expense, purchase_id=purchase)


def test_a_reversal_has_no_source(db_session: Session, author: User, lookups: Lookups, ledger: Ledger) -> None:
    original = posted(db_session, author, ledger)
    expense = new_expense(db_session, lookups, author)
    with pytest.raises(IntegrityError, match="a_reversal_has_no_source"):
        new_voucher(db_session, author, reversal_of_id=original, expense_id=expense)


def test_a_voucher_is_reversed_once(db_session: Session, author: User, ledger: Ledger) -> None:
    original = posted(db_session, author, ledger)
    new_voucher(db_session, author, reversal_of_id=original)
    with pytest.raises(IntegrityError, match="uq_vouchers_reversal_of_id"):
        new_voucher(db_session, author, reversal_of_id=original)


def void_columns(**extra: Any) -> dict[str, Any]:
    return {"status": "void", "number": "PV-2026-0009", "year": 2026, "seq": 9, **extra}


def test_a_void_voucher_needs_a_reason_and_an_actor(db_session: Session, author: User) -> None:
    with pytest.raises(IntegrityError, match="void_has_reason_and_actor"):
        new_voucher(db_session, author, **void_columns())


def test_a_reason_without_a_void_is_refused(db_session: Session, author: User) -> None:
    with pytest.raises(IntegrityError, match="void_has_reason_and_actor"):
        new_voucher(db_session, author, void_reason="Because")


def test_a_void_key_needs_a_void(db_session: Session, author: User) -> None:
    with pytest.raises(IntegrityError, match="void_key_only_when_void"):
        new_voucher(db_session, author, void_key="a-void-key-1")


def test_a_reversal_cannot_itself_be_voided(db_session: Session, author: User, ledger: Ledger) -> None:
    original = posted(db_session, author, ledger)
    columns = void_columns(
        void_reason="Mistake", voided_by=author.id, voided_at="2026-10-12T10:00:00+00:00", reversal_of_id=original
    )
    with pytest.raises(IntegrityError, match="a_reversal_cannot_be_voided"):
        new_voucher(db_session, author, **columns)


# Frozen once posted --------------------------------------------------------------------------------------------------


def test_the_lines_of_a_posted_voucher_cannot_change(db_session: Session, author: User, ledger: Ledger) -> None:
    voucher = posted(db_session, author, ledger)
    with pytest.raises(IntegrityError, match="no longer be changed"):
        db_session.execute(
            text("UPDATE voucher_lines SET debit = 1.00 WHERE voucher_id = :v AND line_no = 1"), {"v": voucher}
        )


def test_a_line_cannot_be_added_to_a_posted_voucher(db_session: Session, author: User, ledger: Ledger) -> None:
    voucher = posted(db_session, author, ledger)
    with pytest.raises(IntegrityError, match="no longer be changed"):
        add_line(db_session, voucher, 3, ledger.expense.id, debit="1.00")


def test_a_line_cannot_be_removed_from_a_posted_voucher(db_session: Session, author: User, ledger: Ledger) -> None:
    voucher = posted(db_session, author, ledger)
    with pytest.raises(IntegrityError, match="no longer be changed"):
        db_session.execute(text("DELETE FROM voucher_lines WHERE voucher_id = :v"), {"v": voucher})


@pytest.mark.parametrize(
    "assignment",
    ["description = 'changed'", "document_date = '2026-01-01'", "voucher_type = 'JV'", "created_by = created_by + 1"],
)
def test_the_header_of_a_posted_voucher_cannot_change(
    db_session: Session, author: User, ledger: Ledger, assignment: str
) -> None:
    voucher = posted(db_session, author, ledger)
    with pytest.raises(IntegrityError):
        db_session.execute(text(f"UPDATE vouchers SET {assignment} WHERE id = :v"), {"v": voucher})


def test_a_number_is_permanent(db_session: Session, author: User, ledger: Ledger) -> None:
    voucher = posted(db_session, author, ledger, seq=1)
    with pytest.raises(IntegrityError, match="number is never changed"):
        db_session.execute(text("UPDATE vouchers SET number = 'PV-2026-0099', seq = 99 WHERE id = :v"), {"v": voucher})


def test_a_posted_voucher_can_only_be_voided(db_session: Session, author: User, ledger: Ledger) -> None:
    voucher = posted(db_session, author, ledger)
    with pytest.raises(IntegrityError, match="can only be voided"):
        db_session.execute(text("UPDATE vouchers SET status = 'draft' WHERE id = :v"), {"v": voucher})


def test_a_void_voucher_stays_void(db_session: Session, author: User, ledger: Ledger) -> None:
    voucher = posted(db_session, author, ledger)
    db_session.execute(
        text(
            "UPDATE vouchers SET status = 'void', void_reason = 'Paid twice', voided_by = :u, voided_at = now()"
            " WHERE id = :v"
        ),
        {"v": voucher, "u": author.id},
    )
    with pytest.raises(IntegrityError):
        db_session.execute(
            text(
                "UPDATE vouchers SET status = 'posted', void_reason = NULL, voided_by = NULL, voided_at = NULL"
                " WHERE id = :v"
            ),
            {"v": voucher},
        )


def test_a_voucher_is_never_deleted(db_session: Session, author: User, ledger: Ledger) -> None:
    voucher = new_voucher(db_session, author)
    with pytest.raises(IntegrityError, match="never deleted"):
        db_session.execute(text("DELETE FROM vouchers WHERE id = :v"), {"v": voucher})


def test_a_counter_is_never_deleted(db_session: Session) -> None:
    db_session.execute(text("INSERT INTO number_counters (voucher_type, year, last_seq) VALUES ('RV', 2026, 1)"))
    with pytest.raises(IntegrityError, match="never deleted"):
        db_session.execute(text("DELETE FROM number_counters WHERE voucher_type = 'RV'"))


def test_the_application_role_cannot_rewrite_history_around_the_triggers(db_session: Session) -> None:
    """The app role is a plain role: it cannot switch the triggers off."""
    with pytest.raises(Exception, match=r"permission denied|must be owner"):
        db_session.execute(text("ALTER TABLE vouchers DISABLE TRIGGER vouchers_freeze"))
