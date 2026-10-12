"""The rules the database holds for documents, each reached by going around the service.

Deferred triggers only fire at commit, and these tests never commit, so each one calls SET CONSTRAINTS ALL IMMEDIATE (the
`settle_constraints` helper) to make the database check now."""

from collections.abc import Callable

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError, ProgrammingError
from sqlalchemy.orm import Session

from app.core.enums import Role
from app.models.user import User
from tests.support.database import settle_constraints
from tests.support.documents import Lookups, create_lookups

Make = Callable[..., User]


@pytest.fixture
def lookups(db_session: Session, make: Make) -> Lookups:
    return create_lookups(db_session, make(Role.ADMIN))


def new_expense(
    session: Session,
    lookups: Lookups,
    author: User,
    *,
    kind: str = "indirect",
    method: str | None = "percentage",
    amount: str = "100.00",
    status: str = "draft",
) -> int:
    attribution = ", cost_center_id" if kind == "direct" else ""
    value = f", {lookups.centres[0].id}" if kind == "direct" else ""
    return int(
        session.execute(
            text(
                "INSERT INTO expenses (expense_type, status, created_by, document_date, category_id, amount, payment_method,"
                f" allocation_method{attribution}) VALUES (CAST(:kind AS expense_type), CAST(:status AS document_status), :by,"
                f" '2026-10-12', :cat, :amount, 'cash', CAST(:method AS allocation_method){value}) RETURNING id"
            ),
            {
                "kind": kind,
                "status": status,
                "by": author.id,
                "cat": lookups.category.id,
                "amount": amount,
                "method": method,
            },
        ).scalar_one()
    )


def allocate(session: Session, expense_id: int, centre_id: int, amount: str, bps: int | None) -> None:
    session.execute(
        text(
            "INSERT INTO expense_allocations (expense_id, cost_center_id, basis_points, amount) VALUES (:e, :c, :bp, :a)"
        ),
        {"e": expense_id, "c": centre_id, "bp": bps, "a": amount},
    )


def valid_split(session: Session, lookups: Lookups, expense_id: int) -> None:
    allocate(session, expense_id, lookups.centres[0].id, "60.00", 6000)
    allocate(session, expense_id, lookups.centres[1].id, "40.00", 4000)


# Allocations add up, from both sides (the Pass 3 review step) --------------------------------------------------------


def test_a_valid_split_passes_the_check(db_session: Session, lookups: Lookups, make: Make) -> None:
    expense = new_expense(db_session, lookups, make(Role.STAFF))
    valid_split(db_session, lookups, expense)
    settle_constraints(db_session)


def test_allocations_that_do_not_total_the_expense_are_refused_at_commit(
    db_session: Session, lookups: Lookups, make: Make
) -> None:
    expense = new_expense(db_session, lookups, make(Role.STAFF))
    allocate(db_session, expense, lookups.centres[0].id, "60.00", 6000)
    allocate(db_session, expense, lookups.centres[1].id, "30.00", 4000)  # 90.00 of 100.00
    with pytest.raises(IntegrityError, match="expense_allocations_consistent"):
        settle_constraints(db_session)


def test_percentages_that_do_not_total_ten_thousand_are_refused_at_commit(
    db_session: Session, lookups: Lookups, make: Make
) -> None:
    expense = new_expense(db_session, lookups, make(Role.STAFF))
    allocate(db_session, expense, lookups.centres[0].id, "60.00", 6000)
    allocate(db_session, expense, lookups.centres[1].id, "40.00", 3999)
    with pytest.raises(IntegrityError, match="10000 basis points"):
        settle_constraints(db_session)


def test_a_fixed_split_may_not_carry_percentages(db_session: Session, lookups: Lookups, make: Make) -> None:
    expense = new_expense(db_session, lookups, make(Role.STAFF), method="fixed")
    valid_split(db_session, lookups, expense)
    with pytest.raises(IntegrityError, match="fixed allocations carry amounts"):
        settle_constraints(db_session)


def test_allocations_need_a_method(db_session: Session, lookups: Lookups, make: Make) -> None:
    expense = new_expense(db_session, lookups, make(Role.STAFF), method=None)
    valid_split(db_session, lookups, expense)
    with pytest.raises(IntegrityError, match="need an allocation method"):
        settle_constraints(db_session)


def test_a_direct_expense_has_no_allocations(db_session: Session, lookups: Lookups, make: Make) -> None:
    expense = new_expense(db_session, lookups, make(Role.STAFF), kind="direct", method=None)
    allocate(db_session, expense, lookups.centres[1].id, "100.00", None)
    with pytest.raises(IntegrityError, match="only an indirect expense"):
        settle_constraints(db_session)


def test_changing_the_expense_amount_alone_is_caught_from_the_other_side(
    db_session: Session, lookups: Lookups, make: Make
) -> None:
    expense = new_expense(db_session, lookups, make(Role.STAFF))
    valid_split(db_session, lookups, expense)
    settle_constraints(db_session)
    db_session.execute(text("SET CONSTRAINTS ALL DEFERRED"))
    db_session.execute(text("UPDATE expenses SET amount = 200.00 WHERE id = :e"), {"e": expense})
    with pytest.raises(IntegrityError, match="expense_allocations_consistent"):
        settle_constraints(db_session)


def test_removing_one_allocation_is_caught(db_session: Session, lookups: Lookups, make: Make) -> None:
    expense = new_expense(db_session, lookups, make(Role.STAFF))
    valid_split(db_session, lookups, expense)
    settle_constraints(db_session)
    db_session.execute(text("SET CONSTRAINTS ALL DEFERRED"))
    db_session.execute(
        text("DELETE FROM expense_allocations WHERE expense_id = :e AND basis_points = 4000"), {"e": expense}
    )
    with pytest.raises(IntegrityError, match="expense_allocations_consistent"):
        settle_constraints(db_session)


def test_turning_a_split_expense_into_a_direct_one_without_clearing_the_split_is_caught(
    db_session: Session, lookups: Lookups, make: Make
) -> None:
    expense = new_expense(db_session, lookups, make(Role.STAFF))
    valid_split(db_session, lookups, expense)
    settle_constraints(db_session)
    db_session.execute(text("SET CONSTRAINTS ALL DEFERRED"))
    db_session.execute(
        text(
            "UPDATE expenses SET expense_type = 'direct', allocation_method = NULL, cost_center_id = :c WHERE id = :e"
        ),
        {"e": expense, "c": lookups.centres[0].id},
    )
    with pytest.raises(IntegrityError, match="only an indirect expense"):
        settle_constraints(db_session)


def test_an_indirect_expense_with_no_rows_passes_the_database_and_is_refused_at_submit_by_the_service(
    db_session: Session, lookups: Lookups, make: Make
) -> None:
    """The known gap in architecture.md section 5, stated as a test so it cannot be forgotten."""
    new_expense(db_session, lookups, make(Role.STAFF))
    settle_constraints(db_session)


def test_a_cost_centre_appears_once_in_a_split(db_session: Session, lookups: Lookups, make: Make) -> None:
    expense = new_expense(db_session, lookups, make(Role.STAFF))
    allocate(db_session, expense, lookups.centres[0].id, "50.00", 5000)
    db_session.execute(text("SAVEPOINT s"))
    with pytest.raises(IntegrityError, match="one_row_per_cost_center"):
        allocate(db_session, expense, lookups.centres[0].id, "50.00", 5000)
    db_session.execute(text("ROLLBACK TO SAVEPOINT s"))


@pytest.mark.parametrize(
    ("amount", "tax", "rule"),
    [("0.00", "0.00", "ck_expenses_amount_positive"), ("100.00", "200.00", "ck_expenses_tax_within_amount")],
)
def test_expense_checks_hold_without_the_service(
    db_session: Session, lookups: Lookups, make: Make, amount: str, tax: str, rule: str
) -> None:
    author = make(Role.STAFF)
    with pytest.raises(IntegrityError, match=rule):
        db_session.execute(
            text(
                "INSERT INTO expenses (expense_type, created_by, document_date, category_id, amount, tax_amount,"
                " payment_method, cost_center_id) VALUES ('direct', :u, '2026-10-12', :c, :a, :t, 'cash', :cc)"
            ),
            {"u": author.id, "c": lookups.category.id, "a": amount, "t": tax, "cc": lookups.centres[0].id},
        )


def test_a_direct_expense_without_a_destination_and_an_indirect_one_with_one_are_refused(
    db_session: Session, lookups: Lookups, make: Make
) -> None:
    author = make(Role.STAFF)
    insert = (
        "INSERT INTO expenses (expense_type, created_by, document_date, category_id, amount, payment_method{extra})"
        " VALUES (CAST(:k AS expense_type), :u, '2026-10-12', :c, 10, 'cash'{value})"
    )
    params = {"u": author.id, "c": lookups.category.id}
    db_session.execute(text("SAVEPOINT s"))
    with pytest.raises(IntegrityError, match="direct_has_attribution_indirect_has_none"):
        db_session.execute(text(insert.format(extra="", value="")), {"k": "direct", **params})
    db_session.execute(text("ROLLBACK TO SAVEPOINT s"))
    with pytest.raises(IntegrityError, match="direct_has_attribution_indirect_has_none"):
        db_session.execute(
            text(insert.format(extra=", cost_center_id", value=f", {lookups.centres[0].id}")),
            {"k": "indirect", **params},
        )


# Nothing changes after Draft -----------------------------------------------------------------------------------------


def submitted_expense(session: Session, lookups: Lookups, make: Make) -> int:
    expense = new_expense(session, lookups, make(Role.STAFF))
    valid_split(session, lookups, expense)
    session.execute(text("UPDATE expenses SET status = 'submitted' WHERE id = :e"), {"e": expense})
    return expense


def test_a_submitted_expense_cannot_be_edited(db_session: Session, lookups: Lookups, make: Make) -> None:
    expense = submitted_expense(db_session, lookups, make)
    db_session.execute(text("SAVEPOINT s"))
    with pytest.raises(IntegrityError, match="not a draft") as caught:
        db_session.execute(text("UPDATE expenses SET description = 'sneaky' WHERE id = :e"), {"e": expense})
    # The name the API's error handler maps to DOCUMENT_LOCKED is what the database reports.
    assert caught.value.orig.diag.constraint_name == "document_is_not_a_draft"  # type: ignore[union-attr]
    db_session.execute(text("ROLLBACK TO SAVEPOINT s"))
    with pytest.raises(IntegrityError, match="not a draft"):
        db_session.execute(text("UPDATE expenses SET amount = 1 WHERE id = :e"), {"e": expense})


def test_a_submitted_expense_may_still_change_status(db_session: Session, lookups: Lookups, make: Make) -> None:
    expense = submitted_expense(db_session, lookups, make)
    db_session.execute(
        text("UPDATE expenses SET status = 'approved', version = version + 1 WHERE id = :e"), {"e": expense}
    )
    db_session.execute(text("UPDATE expenses SET status = 'posted' WHERE id = :e"), {"e": expense})
    settle_constraints(db_session)


def test_the_split_of_a_submitted_expense_is_frozen(db_session: Session, lookups: Lookups, make: Make) -> None:
    expense = submitted_expense(db_session, lookups, make)
    statements = (
        f"INSERT INTO expense_allocations (expense_id, cost_center_id, amount) VALUES ({expense}, {lookups.centres[2].id}, 1)",
        f"UPDATE expense_allocations SET amount = 59.00 WHERE expense_id = {expense} AND basis_points = 6000",
        f"DELETE FROM expense_allocations WHERE expense_id = {expense}",
    )
    for statement in statements:
        db_session.execute(text("SAVEPOINT s"))
        with pytest.raises(IntegrityError, match="not a draft"):
            db_session.execute(text(statement))
        db_session.execute(text("ROLLBACK TO SAVEPOINT s"))


# Purchases -----------------------------------------------------------------------------------------------------------


def new_purchase(
    session: Session, lookups: Lookups, author: User, *, registered: bool = True, status: str = "draft"
) -> int:
    vendor = lookups.vendors["reg_filer" if registered else "unreg_nonfiler"]
    kind = "tax_invoice" if registered else "purchase_memo"
    number = "'INV-1'" if registered else "NULL"
    purchase = session.execute(
        text(
            "INSERT INTO purchases (status, vendor_id, created_by, document_date, document_kind, invoice_number,"
            " vendor_registered, vendor_filer, subtotal, sales_tax_total, gross_total, sales_tax_withheld,"
            " income_tax_withheld, payable) VALUES (CAST(:status AS document_status), :v, :u, '2026-10-12',"
            f" CAST(:kind AS purchase_kind), {number}, :r, false, 100, 0, 100, 20, 5, 75) RETURNING id"
        ),
        {"status": status, "v": vendor.id, "u": author.id, "kind": kind, "r": registered},
    ).scalar_one()
    rule_id = session.execute(text("SELECT id FROM tax_rules LIMIT 1")).scalar_one()
    session.execute(
        text(
            "INSERT INTO purchase_lines (purchase_id, line_no, item, category, quantity, rate, sales_tax_bp, subtotal,"
            " sales_tax, gross, sales_withholding_rule_id, sales_withholding_bp, sales_tax_withheld,"
            " income_withholding_rule_id, income_withholding_bp, income_tax_withheld, payable)"
            " VALUES (:p, 1, 'Paper', 'goods', 1, 100, 0, 100, 0, 100, :rule, 2000, 20, :rule, 500, 5, 75)"
        ),
        {"p": purchase, "rule": rule_id},
    )
    return int(purchase)


def test_a_purchase_whose_header_matches_its_lines_passes(db_session: Session, lookups: Lookups, make: Make) -> None:
    new_purchase(db_session, lookups, make(Role.ACCOUNTANT))
    settle_constraints(db_session)


@pytest.mark.parametrize(
    "column", ["subtotal", "sales_tax_total", "gross_total", "sales_tax_withheld", "income_tax_withheld", "payable"]
)
def test_a_purchase_header_that_is_not_the_sum_of_its_lines_is_refused_at_commit(
    db_session: Session, lookups: Lookups, make: Make, column: str
) -> None:
    purchase = new_purchase(db_session, lookups, make(Role.ACCOUNTANT))
    settle_constraints(db_session)
    db_session.execute(text("SET CONSTRAINTS ALL DEFERRED"))
    # Keep the header's own arithmetic consistent so only the line-sum rule can object.
    bump = {
        "subtotal": "subtotal = 101, gross_total = 101, payable = 76",
        "sales_tax_total": "sales_tax_total = 1, gross_total = 101, payable = 76",
        "gross_total": "subtotal = 100, sales_tax_total = 1, gross_total = 101, payable = 76",
        "sales_tax_withheld": "sales_tax_withheld = 21, payable = 74",
        "income_tax_withheld": "income_tax_withheld = 6, payable = 74",
        "payable": "sales_tax_withheld = 25, income_tax_withheld = 0, payable = 75",
    }[column]
    db_session.execute(text(f"UPDATE purchases SET {bump} WHERE id = :p"), {"p": purchase})
    with pytest.raises(IntegrityError, match="purchase_totals_match"):
        settle_constraints(db_session)


def test_purchase_checks_hold_without_the_service(db_session: Session, lookups: Lookups, make: Make) -> None:
    author = make(Role.ACCOUNTANT)
    base = (
        "INSERT INTO purchases (vendor_id, created_by, document_date, document_kind, invoice_number, vendor_registered,"
        " vendor_filer, subtotal, sales_tax_total, gross_total, sales_tax_withheld, income_tax_withheld, payable)"
        " VALUES (:v, :u, '2026-10-12', CAST(:kind AS purchase_kind), :n, :r, false, {amounts})"
    )
    vendor = lookups.vendors["reg_filer"].id
    cases = [
        ("tax_invoice", None, True, "100, 0, 100, 0, 0, 100", "ck_purchases_tax_invoice_has_a_number"),
        ("purchase_memo", None, True, "100, 0, 100, 0, 0, 100", "ck_purchases_kind_follows_registration"),
        ("tax_invoice", "N1", False, "100, 0, 100, 0, 0, 100", "ck_purchases_kind_follows_registration"),
        ("tax_invoice", "N1", True, "100, 0, 100, 60, 60, -20", "ck_purchases_payable_not_negative"),
        ("tax_invoice", "N1", True, "100, 0, 99, 0, 0, 99", "ck_purchases_gross_is_subtotal_plus_tax"),
        ("tax_invoice", "N1", True, "100, 0, 100, 10, 0, 100", "ck_purchases_payable_is_gross_less_withholdings"),
    ]
    for kind, number, registered, amounts, expected in cases:
        db_session.execute(text("SAVEPOINT s"))
        with pytest.raises(IntegrityError, match=expected):
            db_session.execute(
                text(base.format(amounts=amounts)),
                {"v": vendor, "u": author.id, "kind": kind, "n": number, "r": registered},
            )
        db_session.execute(text("ROLLBACK TO SAVEPOINT s"))


def test_a_submitted_purchase_and_its_lines_are_frozen(db_session: Session, lookups: Lookups, make: Make) -> None:
    purchase = new_purchase(db_session, lookups, make(Role.ACCOUNTANT))
    db_session.execute(text("UPDATE purchases SET status = 'submitted' WHERE id = :p"), {"p": purchase})
    for statement in (
        f"UPDATE purchases SET description = 'changed' WHERE id = {purchase}",
        f"UPDATE purchase_lines SET rate = 1 WHERE purchase_id = {purchase}",
        f"DELETE FROM purchase_lines WHERE purchase_id = {purchase}",
    ):
        db_session.execute(text("SAVEPOINT s"))
        with pytest.raises(IntegrityError, match="not a draft"):
            db_session.execute(text(statement))
        db_session.execute(text("ROLLBACK TO SAVEPOINT s"))
    db_session.execute(text("UPDATE purchases SET status = 'approved' WHERE id = :p"), {"p": purchase})


def test_purchase_lines_check_their_own_arithmetic(db_session: Session, lookups: Lookups, make: Make) -> None:
    purchase = new_purchase(db_session, lookups, make(Role.ACCOUNTANT))
    rule_id = db_session.execute(text("SELECT id FROM tax_rules LIMIT 1")).scalar_one()
    insert = (
        "INSERT INTO purchase_lines (purchase_id, line_no, item, category, quantity, rate, sales_tax_bp, subtotal, sales_tax,"
        " gross, sales_withholding_rule_id, sales_withholding_bp, sales_tax_withheld, income_withholding_rule_id,"
        " income_withholding_bp, income_tax_withheld, payable)"
        " VALUES (:p, :n, 'x', 'goods', :q, 10, 0, :sub, 0, :gross, :rule, 0, 0, :rule, 0, 0, :pay)"
    )
    cases = [
        (2, "0", "0", "0", "0", "quantity_and_rate_positive"),
        (3, "1", "0", "0", "0", "subtotal_positive"),
        (4, "1", "10", "11", "11", "gross_is_subtotal_plus_tax"),
        (5, "1", "10", "10", "9", "payable_is_gross_less_withholdings"),
    ]
    for number, quantity, subtotal, gross, payable, expected in cases:
        db_session.execute(text("SAVEPOINT s"))
        with pytest.raises(IntegrityError, match=expected):
            db_session.execute(
                text(insert),
                {
                    "p": purchase,
                    "n": number,
                    "q": quantity,
                    "sub": subtotal,
                    "gross": gross,
                    "pay": payable,
                    "rule": rule_id,
                },
            )
        db_session.execute(text("ROLLBACK TO SAVEPOINT s"))
    db_session.execute(text("SAVEPOINT s"))
    with pytest.raises(IntegrityError, match="one_row_per_line_number"):
        db_session.execute(
            text(insert), {"p": purchase, "n": 1, "q": "1", "sub": "10", "gross": "10", "pay": "10", "rule": rule_id}
        )


# Attachments and history ---------------------------------------------------------------------------------------------


def test_an_attachment_belongs_to_exactly_one_document(db_session: Session, lookups: Lookups, make: Make) -> None:
    author = make(Role.STAFF)
    expense = new_expense(db_session, lookups, author)
    purchase = new_purchase(db_session, lookups, make(Role.ACCOUNTANT))
    insert = (
        "INSERT INTO attachments (expense_id, purchase_id, storage_key, content_type, size_bytes, sha256, original_name,"
        " uploaded_by, created_at) VALUES (:e, :p, :k, 'image/png', 10, :h, 'a.png', :u, now())"
    )
    digest = "a" * 64
    for parent, key in (({"e": expense, "p": purchase}, "both"), ({"e": None, "p": None}, "neither")):
        db_session.execute(text("SAVEPOINT s"))
        with pytest.raises(IntegrityError, match="exactly_one_parent"):
            db_session.execute(text(insert), {**parent, "k": key, "h": digest, "u": author.id})
        db_session.execute(text("ROLLBACK TO SAVEPOINT s"))
    db_session.execute(text("SAVEPOINT s"))
    with pytest.raises(IntegrityError, match="sha256_is_64_hex"):
        db_session.execute(text(insert), {"e": expense, "p": None, "k": "short", "h": "abc", "u": author.id})
    db_session.execute(text("ROLLBACK TO SAVEPOINT s"))
    db_session.execute(text(insert), {"e": expense, "p": None, "k": "fine", "h": digest, "u": author.id})


def test_the_approval_history_can_only_be_appended_to(db_session: Session, make: Make) -> None:
    actor = make(Role.APPROVER)
    db_session.execute(
        text(
            "INSERT INTO document_events (document_type, document_id, action, to_status, actor_id, created_at)"
            " VALUES ('expense', 1, 'created', 'draft', :u, now())"
        ),
        {"u": actor.id},
    )
    assert db_session.execute(text("SELECT count(*) FROM document_events")).scalar_one() == 1
    for statement in (
        "UPDATE document_events SET action = 'x'",
        "DELETE FROM document_events",
        "TRUNCATE document_events",
    ):
        db_session.execute(text("SAVEPOINT s"))
        with pytest.raises((ProgrammingError, DBAPIError)) as caught:
            db_session.execute(text(statement))
        assert getattr(getattr(caught.value, "orig", None), "sqlstate", None) in {"42501", "23001"}
        db_session.execute(text("ROLLBACK TO SAVEPOINT s"))


def test_documents_and_attachments_are_never_deleted(db_session: Session, lookups: Lookups, make: Make) -> None:
    new_expense(db_session, lookups, make(Role.STAFF), kind="direct", method=None)
    new_purchase(db_session, lookups, make(Role.ACCOUNTANT))
    for table in ("expenses", "purchases"):
        db_session.execute(text("SAVEPOINT s"))
        with pytest.raises(Exception, match="never deleted"):
            db_session.execute(text(f"DELETE FROM {table}"))
        db_session.execute(text("ROLLBACK TO SAVEPOINT s"))
