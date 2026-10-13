"""Stories E1 (lines), E2 (balance), E3 (numbering), E5 (idempotent post, fixed posted lines) and E6 (void)."""

import uuid
from collections.abc import Callable
from datetime import date
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.enums import Role
from app.models.user import User
from app.repositories import vouchers as voucher_repository
from tests.support.clock import FakeClock
from tests.support.documents import Ledger, Lookups, create_ledger, create_lookups, voucher_body

Make = Callable[..., User]
Auth = Callable[[User], dict[str, str]]


@pytest.fixture
def lookups(db_session: Session, make: Make) -> Lookups:
    return create_lookups(db_session, make(Role.ADMIN))


@pytest.fixture
def ledger(db_session: Session, make: Make, lookups: Lookups) -> Ledger:
    return create_ledger(db_session, lookups, make(Role.ADMIN))


@pytest.fixture
def bookkeeper(make: Make, auth: Auth) -> dict[str, str]:
    return auth(make(Role.ACCOUNTANT))


@pytest.fixture
def approver(make: Make, auth: Auth) -> dict[str, str]:
    return auth(make(Role.APPROVER))


@pytest.fixture
def admin(make: Make, auth: Auth) -> dict[str, str]:
    return auth(make(Role.ADMIN))


def key() -> str:
    return "key-" + uuid.uuid4().hex


def versioned(headers: dict[str, str], voucher: dict[str, Any], **extra: str) -> dict[str, str]:
    return {**headers, "If-Match": str(voucher["version"]), **extra}


def create(client: TestClient, headers: dict[str, str], body: dict[str, Any]) -> Any:
    return client.post("/api/v1/vouchers", json=body, headers=headers)


def move(client: TestClient, headers: dict[str, str], voucher: dict[str, Any], action: str, **body: Any) -> Any:
    return client.post(
        f"/api/v1/vouchers/{voucher['id']}/{action}", json=body or None, headers=versioned(headers, voucher)
    )


def post_it(
    client: TestClient, headers: dict[str, str], voucher: dict[str, Any], idempotency: str | None = None
) -> Any:
    return client.post(
        f"/api/v1/vouchers/{voucher['id']}/post",
        headers=versioned(headers, voucher, **{"Idempotency-Key": idempotency or key()}),
    )


def void_it(
    client: TestClient,
    headers: dict[str, str],
    voucher: dict[str, Any],
    reason: str = "Entered twice",
    idempotency: str | None = None,
) -> Any:
    return client.post(
        f"/api/v1/vouchers/{voucher['id']}/void",
        json={"reason": reason},
        headers=versioned(headers, voucher, **{"Idempotency-Key": idempotency or key()}),
    )


def approved(
    client: TestClient, author: dict[str, str], reviewer: dict[str, str], body: dict[str, Any]
) -> dict[str, Any]:
    voucher = create(client, author, body).json()
    voucher = move(client, author, voucher, "submit").json()
    result: dict[str, Any] = move(client, reviewer, voucher, "approve").json()
    assert result["status"] == "approved", result
    return result


def posted(
    client: TestClient, author: dict[str, str], reviewer: dict[str, str], body: dict[str, Any]
) -> dict[str, Any]:
    voucher = approved(client, author, reviewer, body)
    result: dict[str, Any] = post_it(client, author, voucher).json()
    assert result["status"] == "posted", result
    return result


# E1: lines -----------------------------------------------------------------------------------------------------------


def test_e1_a_voucher_has_lines_each_with_an_account_and_one_side(
    client: TestClient, bookkeeper: dict[str, str], ledger: Ledger
) -> None:
    response = create(client, bookkeeper, voucher_body(ledger, "250.50"))
    assert response.status_code == 201, response.text
    body = response.json()
    assert (body["voucher_type"], body["status"], body["number"]) == ("PV", "draft", None)
    assert [(ln["line_no"], ln["account_code"], ln["debit"], ln["credit"]) for ln in body["lines"]] == [
        (1, "5100", "250.50", "0.00"),
        (2, "1100", "0.00", "250.50"),
    ]
    assert body["lines"][0]["account_name"] == "Rent"
    assert (body["total_debit"], body["total_credit"]) == ("250.50", "250.50")
    assert body["actions"] == ["submit"]


@pytest.mark.parametrize("voucher_type", ["PV", "RV", "JV"])
def test_e1_all_three_types_are_accepted(
    client: TestClient, bookkeeper: dict[str, str], ledger: Ledger, voucher_type: str
) -> None:
    assert (
        create(client, bookkeeper, voucher_body(ledger, voucher_type=voucher_type)).json()["voucher_type"]
        == voucher_type
    )
    assert create(client, bookkeeper, voucher_body(ledger, voucher_type="XV")).status_code == 422


@pytest.mark.parametrize(
    "line",
    [
        {"debit": "10.00", "credit": "10.00"},
        {},
        {"debit": "0.00", "credit": "0.00"},
        {"debit": "-5.00"},
        {"debit": 10.5},
        {"credit": "10.005"},
    ],
)
def test_e1_a_line_has_exactly_one_positive_side(
    client: TestClient, bookkeeper: dict[str, str], ledger: Ledger, line: dict[str, Any]
) -> None:
    body = voucher_body(ledger)
    body["lines"][0] = {"account_id": ledger.expense.id, **line}
    assert create(client, bookkeeper, body).status_code == 422


def test_e1_only_postable_active_accounts_can_be_used(
    client: TestClient, bookkeeper: dict[str, str], ledger: Ledger, db_session: Session
) -> None:
    parent = voucher_body(ledger)
    parent["lines"][0]["account_id"] = ledger.parent.id
    refused = create(client, bookkeeper, parent)
    assert refused.status_code == 422
    assert refused.json()["errors"][0] == {
        "field": "lines.0.account_id",
        "message": "This is a parent account; choose a sub-account.",
        "code": "not_postable",
    }
    ledger.other_expense.is_active = False
    db_session.commit()
    inactive = voucher_body(ledger)
    inactive["lines"][0]["account_id"] = ledger.other_expense.id
    assert create(client, bookkeeper, inactive).json()["errors"][0]["field"] == "lines.0.account_id"
    unknown = voucher_body(ledger)
    unknown["lines"][0]["account_id"] = 999_999
    assert create(client, bookkeeper, unknown).status_code == 422


def test_e1_lines_may_carry_a_cost_centre_and_a_project(
    client: TestClient, bookkeeper: dict[str, str], ledger: Ledger, lookups: Lookups
) -> None:
    body = voucher_body(ledger)
    body["lines"][0].update(cost_center_id=lookups.centres[0].id, project_id=lookups.project.id)
    line = create(client, bookkeeper, body).json()["lines"][0]
    assert (line["cost_center_id"], line["project_id"]) == (lookups.centres[0].id, lookups.project.id)
    lookups.centres[0].is_active = False
    body["lines"][0]["cost_center_id"] = 999_999
    assert create(client, bookkeeper, body).json()["errors"][0]["field"] == "lines.0.cost_center_id"


def test_e1_a_voucher_needs_two_lines(client: TestClient, bookkeeper: dict[str, str], ledger: Ledger) -> None:
    body = voucher_body(ledger)
    body["lines"] = body["lines"][:1]
    assert create(client, bookkeeper, body).status_code == 422


# E2: balance ---------------------------------------------------------------------------------------------------------


def test_e2_an_unbalanced_voucher_cannot_be_saved_and_the_fix_is_named(
    client: TestClient, bookkeeper: dict[str, str], ledger: Ledger
) -> None:
    body = voucher_body(ledger)
    body["lines"][1]["credit"] = "99.99"
    response = create(client, bookkeeper, body)
    assert (response.status_code, response.json()["code"]) == (422, "VOUCHER_UNBALANCED")
    assert "credit of 0.01" in response.json()["detail"]
    assert response.json()["errors"][0]["field"] == "lines"
    assert client.get("/api/v1/vouchers", headers=bookkeeper).json()["total"] == 0


def test_e2_the_balance_check_returns_the_difference_and_the_offsetting_line(
    client: TestClient, bookkeeper: dict[str, str], ledger: Ledger
) -> None:
    def check(lines: list[dict[str, Any]]) -> dict[str, Any]:
        response = client.post("/api/v1/vouchers/check-balance", json={"lines": lines}, headers=bookkeeper)
        assert response.status_code == 200, response.text
        result: dict[str, Any] = response.json()
        return result

    expense, cash = ledger.expense.id, ledger.cash.id
    balanced = check([{"account_id": expense, "debit": "100.00"}, {"account_id": cash, "credit": "100.00"}])
    assert (balanced["balanced"], balanced["difference"], balanced["offsetting_line"]) == (True, "0.00", None)
    short = check([{"account_id": expense, "debit": "100.00"}, {"account_id": cash, "credit": "40.25"}])
    assert (short["balanced"], short["difference"], short["offsetting_line"]) == (
        False,
        "59.75",
        {"side": "credit", "amount": "59.75"},
    )
    over = check([{"account_id": expense, "debit": "10.00"}, {"account_id": cash, "credit": "500.00"}])
    assert (over["difference"], over["offsetting_line"]) == ("-490.00", {"side": "debit", "amount": "490.00"})
    assert check([])["balanced"] is True
    # Taking the suggestion balances it, to the paisa.
    fixed = check(
        [
            {"account_id": expense, "debit": "10.00"},
            {"account_id": cash, "credit": "500.00"},
            {"account_id": expense, "debit": over["offsetting_line"]["amount"]},
        ]
    )
    assert fixed["balanced"] is True


def test_e2_the_balance_check_saves_nothing_and_is_for_bookkeepers(
    client: TestClient, bookkeeper: dict[str, str], approver: dict[str, str], ledger: Ledger
) -> None:
    body = {"lines": [{"account_id": ledger.expense.id, "debit": "1.00"}]}
    client.post("/api/v1/vouchers/check-balance", json=body, headers=bookkeeper)
    assert client.get("/api/v1/vouchers", headers=bookkeeper).json()["total"] == 0
    assert client.post("/api/v1/vouchers/check-balance", json=body, headers=approver).status_code == 403


def test_e2_editing_the_lines_keeps_the_voucher_balanced(
    client: TestClient, bookkeeper: dict[str, str], ledger: Ledger
) -> None:
    voucher = create(client, bookkeeper, voucher_body(ledger)).json()
    headers = versioned(bookkeeper, voucher)
    unbalanced = [
        {"account_id": ledger.expense.id, "debit": "50.00"},
        {"account_id": ledger.cash.id, "credit": "40.00"},
    ]
    refused = client.patch(f"/api/v1/vouchers/{voucher['id']}", json={"lines": unbalanced}, headers=headers)
    assert (refused.status_code, refused.json()["code"]) == (422, "VOUCHER_UNBALANCED")
    unchanged = client.get(f"/api/v1/vouchers/{voucher['id']}", headers=bookkeeper).json()
    assert unchanged["total_debit"] == "100.00"
    good = [{"account_id": ledger.expense.id, "debit": "50.00"}, {"account_id": ledger.bank.id, "credit": "50.00"}]
    edited = client.patch(
        f"/api/v1/vouchers/{voucher['id']}",
        json={"lines": good, "description": "Revised"},
        headers=versioned(bookkeeper, unchanged),
    )
    assert edited.status_code == 200
    assert (edited.json()["total_debit"], edited.json()["description"], edited.json()["lines"][1]["account_code"]) == (
        "50.00",
        "Revised",
        "1200",
    )


def test_e2_submit_explains_what_is_missing(client: TestClient, bookkeeper: dict[str, str], ledger: Ledger) -> None:
    voucher = create(client, bookkeeper, voucher_body(ledger, description="  ")).json()
    refused = move(client, bookkeeper, voucher, "submit")
    assert (refused.status_code, refused.json()["code"]) == (422, "DOCUMENT_INCOMPLETE")
    assert refused.json()["errors"][0]["field"] == "description"
    fixed = client.patch(
        f"/api/v1/vouchers/{voucher['id']}", json={"description": "Rent"}, headers=versioned(bookkeeper, voucher)
    ).json()
    assert move(client, bookkeeper, fixed, "submit").json()["status"] == "submitted"


def test_e2_the_lines_of_a_submitted_voucher_are_frozen(
    client: TestClient, bookkeeper: dict[str, str], ledger: Ledger
) -> None:
    submitted = move(client, bookkeeper, create(client, bookkeeper, voucher_body(ledger)).json(), "submit").json()
    locked = client.patch(
        f"/api/v1/vouchers/{submitted['id']}",
        json={"description": "Too late"},
        headers=versioned(bookkeeper, submitted),
    )
    assert (locked.status_code, locked.json()["code"]) == (409, "DOCUMENT_LOCKED")


# Workflow roles ------------------------------------------------------------------------------------------------------


def test_the_voucher_goes_through_the_same_steps_with_the_same_rules(
    client: TestClient, make: Make, auth: Auth, bookkeeper: dict[str, str], approver: dict[str, str], ledger: Ledger
) -> None:
    voucher = create(client, bookkeeper, voucher_body(ledger)).json()
    submitted = move(client, bookkeeper, voucher, "submit").json()
    assert move(client, bookkeeper, submitted, "approve").status_code == 403  # an accountant cannot approve
    blank = client.post(
        f"/api/v1/vouchers/{voucher['id']}/reject", json={"comment": " "}, headers=versioned(approver, submitted)
    )
    assert blank.json()["code"] == "COMMENT_REQUIRED"
    rejected = move(client, approver, submitted, "reject", comment="Wrong account").json()
    reopened = move(client, bookkeeper, rejected, "reopen").json()
    assert reopened["status"] == "draft"
    again = move(client, bookkeeper, reopened, "submit").json()
    assert move(client, approver, again, "approve", comment="Fine").json()["status"] == "approved"
    history = client.get(f"/api/v1/vouchers/{voucher['id']}/history", headers=approver).json()
    assert [h["action"] for h in history] == ["created", "submitted", "rejected", "reopened", "submitted", "approved"]
    assert {h["document_type"] for h in history} == {"voucher"}
    assert client.get("/api/v1/vouchers", headers=auth(make(Role.STAFF))).status_code == 403


def test_a4_nobody_approves_the_voucher_they_created(client: TestClient, admin: dict[str, str], ledger: Ledger) -> None:
    own = move(client, admin, create(client, admin, voucher_body(ledger)).json(), "submit").json()
    refused = move(client, admin, own, "approve")
    assert (refused.status_code, refused.json()["code"]) == (403, "SELF_APPROVAL_FORBIDDEN")


# E3: numbering -------------------------------------------------------------------------------------------------------


def test_e3_a_number_is_given_at_post_and_only_then(
    client: TestClient, bookkeeper: dict[str, str], approver: dict[str, str], ledger: Ledger
) -> None:
    voucher = create(client, bookkeeper, voucher_body(ledger)).json()
    submitted = move(client, bookkeeper, voucher, "submit").json()
    ready = move(client, approver, submitted, "approve").json()
    assert voucher["number"] is None
    assert submitted["number"] is None
    assert ready["number"] is None
    done = post_it(client, bookkeeper, ready).json()
    assert (done["number"], done["status"]) == ("PV-2026-0001", "posted")


def test_e3_numbers_are_consecutive_per_type_and_year(
    client: TestClient, bookkeeper: dict[str, str], approver: dict[str, str], ledger: Ledger
) -> None:
    numbers = [
        posted(client, bookkeeper, approver, voucher_body(ledger, amount))["number"]
        for amount in ("10.00", "20.00", "30.00")
    ]
    assert numbers == ["PV-2026-0001", "PV-2026-0002", "PV-2026-0003"]
    receipt = posted(client, bookkeeper, approver, voucher_body(ledger, voucher_type="RV"))
    journal = posted(client, bookkeeper, approver, voucher_body(ledger, voucher_type="JV"))
    assert (receipt["number"], journal["number"]) == ("RV-2026-0001", "JV-2026-0001")  # each type counts on its own
    assert posted(client, bookkeeper, approver, voucher_body(ledger))["number"] == "PV-2026-0004"


def test_e3_the_year_follows_the_document_date_not_the_clock(
    client: TestClient, bookkeeper: dict[str, str], approver: dict[str, str], ledger: Ledger
) -> None:
    last_year = posted(client, bookkeeper, approver, voucher_body(ledger, document_date="2025-12-31"))
    this_year = posted(client, bookkeeper, approver, voucher_body(ledger, document_date="2026-01-01"))
    again = posted(client, bookkeeper, approver, voucher_body(ledger, document_date="2025-06-30"))
    assert (last_year["number"], this_year["number"], again["number"]) == (
        "PV-2025-0001",
        "PV-2026-0001",
        "PV-2025-0002",
    )


def test_e3_the_accountant_chooses_the_month_the_numbering_year_starts_in(
    client: TestClient, bookkeeper: dict[str, str], approver: dict[str, str], ledger: Ledger
) -> None:
    initial = client.get("/api/v1/settings/accounting", headers=bookkeeper).json()
    assert initial["fiscal_year_start_month"] == 1  # a new install numbers by calendar year
    assert initial["numbering_year_today"] == 2026
    changed = client.put("/api/v1/settings/accounting", json={"fiscal_year_start_month": 7}, headers=bookkeeper)
    assert changed.status_code == 200
    assert changed.json()["fiscal_year_start_month"] == 7
    assert changed.json()["numbering_year_today"] == 2027  # 12 October 2026 falls in the year that ends in June 2027
    june = posted(client, bookkeeper, approver, voucher_body(ledger, document_date="2026-06-30"))
    july = posted(client, bookkeeper, approver, voucher_body(ledger, document_date="2026-07-01"))
    assert (june["number"], july["number"]) == ("PV-2026-0001", "PV-2027-0001")


def test_e3_a_different_choice_never_renumbers_what_was_already_posted(
    client: TestClient, bookkeeper: dict[str, str], approver: dict[str, str], ledger: Ledger
) -> None:
    before = posted(client, bookkeeper, approver, voucher_body(ledger, document_date="2026-10-01"))
    client.put("/api/v1/settings/accounting", json={"fiscal_year_start_month": 4}, headers=bookkeeper)
    after = posted(client, bookkeeper, approver, voucher_body(ledger, document_date="2026-10-02"))
    assert before["number"] == "PV-2026-0001"
    assert after["number"] == "PV-2027-0001"  # a new year label starts its own count: no number is ever reused
    assert client.get(f"/api/v1/vouchers/{before['id']}", headers=bookkeeper).json()["number"] == "PV-2026-0001"


def test_e3_the_year_setting_is_for_bookkeepers_to_change_and_the_office_to_read(
    client: TestClient, make: Make, auth: Auth, bookkeeper: dict[str, str], approver: dict[str, str]
) -> None:
    assert client.get("/api/v1/settings/accounting", headers=approver).status_code == 200
    assert (
        client.put("/api/v1/settings/accounting", json={"fiscal_year_start_month": 7}, headers=approver).status_code
        == 403
    )
    staff = auth(make(Role.STAFF))
    assert client.get("/api/v1/settings/accounting", headers=staff).status_code == 403
    for month in (0, 13, "July"):
        refused = client.put("/api/v1/settings/accounting", json={"fiscal_year_start_month": month}, headers=bookkeeper)
        assert refused.status_code == 422
    assert client.get("/api/v1/settings/accounting", headers=bookkeeper).json()["fiscal_year_start_month"] == 1


def test_e3_a_change_to_the_year_setting_is_audited_and_repeating_it_is_not(
    client: TestClient, bookkeeper: dict[str, str], db_session: Session
) -> None:
    for _ in range(2):
        client.put("/api/v1/settings/accounting", json={"fiscal_year_start_month": 7}, headers=bookkeeper)
    rows = db_session.execute(
        text("SELECT before, after FROM audit_events WHERE action = 'accounting_settings.updated'")
    ).all()
    assert [(r.before, r.after) for r in rows] == [({"fiscal_year_start_month": 1}, {"fiscal_year_start_month": 7})]


def test_e3_a_failed_transaction_gives_its_number_back_but_a_sequence_would_not(db_session: Session) -> None:
    """Why the counter is a row and not a sequence: a rollback undoes the row, never a sequence."""
    from app.core.enums import VoucherType

    db_session.execute(text("SAVEPOINT attempt"))
    assert voucher_repository.next_sequence(db_session, VoucherType.PAYMENT, 2099) == 1
    db_session.execute(text("ROLLBACK TO SAVEPOINT attempt"))
    assert voucher_repository.next_sequence(db_session, VoucherType.PAYMENT, 2099) == 1  # taken back, so reused: no gap
    assert voucher_repository.next_sequence(db_session, VoucherType.PAYMENT, 2099) == 2

    db_session.execute(text("CREATE TEMP SEQUENCE demo_sequence"))
    db_session.execute(text("SAVEPOINT attempt"))
    assert db_session.execute(text("SELECT nextval('demo_sequence')")).scalar_one() == 1
    db_session.execute(text("ROLLBACK TO SAVEPOINT attempt"))
    assert (
        db_session.execute(text("SELECT nextval('demo_sequence')")).scalar_one() == 2
    )  # the rolled-back number is lost


# E5: posting ---------------------------------------------------------------------------------------------------------


def test_e5_the_same_key_posts_once_and_a_repeat_returns_the_first_result(
    client: TestClient, bookkeeper: dict[str, str], approver: dict[str, str], ledger: Ledger
) -> None:
    ready = approved(client, bookkeeper, approver, voucher_body(ledger))
    attempt = key()
    first = post_it(client, bookkeeper, ready, attempt)
    repeat = post_it(client, bookkeeper, ready, attempt)  # the same, stale version and all
    assert (first.status_code, repeat.status_code) == (200, 200)
    assert first.json()["number"] == repeat.json()["number"] == "PV-2026-0001"
    assert first.json() == repeat.json()
    # The repeat consumed no number: the next voucher is the second.
    assert posted(client, bookkeeper, approver, voucher_body(ledger))["number"] == "PV-2026-0002"
    audits = client.get(f"/api/v1/vouchers/{ready['id']}/history", headers=approver).json()
    assert [h["action"] for h in audits].count("posted") == 1


def test_e5_a_key_cannot_be_used_for_a_different_voucher(
    client: TestClient, bookkeeper: dict[str, str], approver: dict[str, str], ledger: Ledger
) -> None:
    first, second = (approved(client, bookkeeper, approver, voucher_body(ledger)) for _ in range(2))
    shared = key()
    assert post_it(client, bookkeeper, first, shared).status_code == 200
    reused = post_it(client, bookkeeper, second, shared)
    assert (reused.status_code, reused.json()["code"]) == (409, "IDEMPOTENCY_KEY_REUSED")
    assert client.get(f"/api/v1/vouchers/{second['id']}", headers=bookkeeper).json()["status"] == "approved"


@pytest.mark.parametrize("bad", [None, "short", "has spaces in it!", "x" * 101])
def test_e5_a_post_without_a_proper_key_is_refused(
    client: TestClient, bookkeeper: dict[str, str], approver: dict[str, str], ledger: Ledger, bad: str | None
) -> None:
    ready = approved(client, bookkeeper, approver, voucher_body(ledger))
    extra = {} if bad is None else {"Idempotency-Key": bad}
    response = client.post(f"/api/v1/vouchers/{ready['id']}/post", headers=versioned(bookkeeper, ready, **extra))
    assert (response.status_code, response.json()["code"]) == (422, "IDEMPOTENCY_KEY_REQUIRED")


def test_e5_only_an_approved_voucher_can_be_posted_by_a_bookkeeper(
    client: TestClient, make: Make, auth: Auth, bookkeeper: dict[str, str], approver: dict[str, str], ledger: Ledger
) -> None:
    draft = create(client, bookkeeper, voucher_body(ledger)).json()
    early = post_it(client, bookkeeper, draft)
    assert (early.status_code, early.json()["code"]) == (409, "INVALID_TRANSITION")
    ready = approved(client, bookkeeper, approver, voucher_body(ledger))
    assert post_it(client, approver, ready).status_code == 403
    assert post_it(client, auth(make(Role.STAFF)), ready).status_code == 403
    assert post_it(client, bookkeeper, ready).status_code == 200


def test_e5_a_posted_voucher_cannot_be_posted_again_under_a_new_key(
    client: TestClient, bookkeeper: dict[str, str], approver: dict[str, str], ledger: Ledger
) -> None:
    done = posted(client, bookkeeper, approver, voucher_body(ledger))
    again = post_it(client, bookkeeper, done)
    assert (again.status_code, again.json()["code"]) == (409, "INVALID_TRANSITION")


def test_e5_a_posted_voucher_is_fixed(
    client: TestClient, bookkeeper: dict[str, str], approver: dict[str, str], ledger: Ledger
) -> None:
    done = posted(client, bookkeeper, approver, voucher_body(ledger))
    edit = client.patch(
        f"/api/v1/vouchers/{done['id']}", json={"description": "Changed"}, headers=versioned(bookkeeper, done)
    )
    assert (edit.status_code, edit.json()["code"]) == (409, "DOCUMENT_LOCKED")
    assert move(client, bookkeeper, done, "reopen").status_code == 409
    assert move(client, approver, done, "reject", comment="no").status_code == 409


def test_e5_posting_into_a_closed_period_is_refused_and_reopening_it_allows_it(
    client: TestClient, bookkeeper: dict[str, str], approver: dict[str, str], admin: dict[str, str], ledger: Ledger
) -> None:
    ready = approved(client, bookkeeper, approver, voucher_body(ledger, document_date="2026-09-15"))
    closed = client.post(
        "/api/v1/periods/close", json={"start_date": "2026-09-01", "end_date": "2026-09-30"}, headers=admin
    ).json()
    refused = post_it(client, bookkeeper, ready)
    assert (refused.status_code, refused.json()["code"]) == (409, "PERIOD_CLOSED")
    assert (
        client.get(f"/api/v1/vouchers/{ready['id']}", headers=bookkeeper).json()["number"] is None
    )  # and no number was used
    client.post(f"/api/v1/periods/{closed['id']}/reopen", headers=admin)
    assert post_it(client, bookkeeper, ready).json()["number"] == "PV-2026-0001"


# E6: void and reversal -----------------------------------------------------------------------------------------------


def lines_of(voucher: dict[str, Any]) -> list[tuple[str, str, str]]:
    return [(ln["account_code"], ln["debit"], ln["credit"]) for ln in voucher["lines"]]


def test_e6_voiding_posts_a_linked_reversal_with_the_sides_swapped(
    client: TestClient, bookkeeper: dict[str, str], approver: dict[str, str], admin: dict[str, str], ledger: Ledger
) -> None:
    original = posted(client, bookkeeper, approver, voucher_body(ledger, "75.00"))
    response = void_it(client, admin, original, reason="Entered twice")
    assert response.status_code == 200, response.text
    result = response.json()
    voided, reversal = result["voucher"], result["reversal"]
    assert (voided["status"], voided["void_reason"], voided["number"]) == ("void", "Entered twice", "PV-2026-0001")
    assert voided["reversed_by_id"] == reversal["id"]
    assert lines_of(voided) == [("5100", "75.00", "0.00"), ("1100", "0.00", "75.00")]  # the original is untouched
    assert (reversal["status"], reversal["number"], reversal["reversal_of_id"]) == (
        "posted",
        "PV-2026-0002",
        original["id"],
    )
    assert reversal["reversal_of_number"] == "PV-2026-0001"
    assert lines_of(reversal) == [("5100", "0.00", "75.00"), ("1100", "75.00", "0.00")]
    assert reversal["document_date"] == "2026-10-12"
    assert "Entered twice" in reversal["description"]
    assert reversal["expense_id"] is None
    assert reversal["purchase_id"] is None


def test_e6_the_original_and_its_reversal_cancel_each_other_exactly(
    client: TestClient,
    bookkeeper: dict[str, str],
    approver: dict[str, str],
    admin: dict[str, str],
    ledger: Ledger,
    db_session: Session,
) -> None:
    original = posted(client, bookkeeper, approver, voucher_body(ledger, "123.45"))
    void_it(client, admin, original)
    net = db_session.execute(
        text("SELECT account_id, sum(debit) - sum(credit) FROM voucher_lines GROUP BY account_id")
    ).all()
    assert {row[1] for row in net} == {0}


def test_e6_the_reversal_is_dated_today_in_the_display_zone(
    client: TestClient,
    make: Make,
    auth: Auth,
    bookkeeper: dict[str, str],
    approver: dict[str, str],
    ledger: Ledger,
    clock: FakeClock,
) -> None:
    original = posted(client, bookkeeper, approver, voucher_body(ledger, document_date="2026-08-01"))
    from datetime import UTC, datetime

    clock.set(datetime(2026, 10, 12, 19, 30, tzinfo=UTC))  # 00:30 on the 13th in Karachi
    later_admin = auth(make(Role.ADMIN))  # the earlier token has expired by now
    reversal = void_it(client, later_admin, original).json()["reversal"]
    assert reversal["document_date"] == "2026-10-13"
    assert reversal["number"] == "PV-2026-0002"


def test_e6_a_reason_is_required_and_an_approver_cannot_void(
    client: TestClient, bookkeeper: dict[str, str], approver: dict[str, str], admin: dict[str, str], ledger: Ledger
) -> None:
    original = posted(client, bookkeeper, approver, voucher_body(ledger))
    for reason in ("", "   "):
        response = client.post(
            f"/api/v1/vouchers/{original['id']}/void",
            json={"reason": reason},
            headers=versioned(admin, original, **{"Idempotency-Key": key()}),
        )
        assert response.status_code == 422
    assert (
        client.post(
            f"/api/v1/vouchers/{original['id']}/void",
            json={},
            headers=versioned(admin, original, **{"Idempotency-Key": key()}),
        ).status_code
        == 422
    )
    assert void_it(client, approver, original).status_code == 403
    assert client.get(f"/api/v1/vouchers/{original['id']}", headers=admin).json()["status"] == "posted"


def test_e6_an_accountant_can_void_and_the_void_is_traced_to_them(
    client: TestClient,
    make: Callable[..., User],
    auth: Callable[[User], dict[str, str]],
    approver: dict[str, str],
    ledger: Ledger,
    db_session: Session,
) -> None:
    """The accountant who made a mistake can undo it, and the record keeps who did, why, and the reversal beside it."""
    accountant = make(Role.ACCOUNTANT, full_name="Usman Tariq")
    headers = auth(accountant)
    original = posted(client, headers, approver, voucher_body(ledger))
    response = void_it(client, headers, original)
    assert response.status_code == 200, response.text
    pair = response.json()
    assert pair["voucher"]["status"] == "void"
    assert pair["reversal"]["reversal_of_number"] == original["number"]
    row = db_session.execute(
        text("SELECT voided_by, void_reason FROM vouchers WHERE id = :v"), {"v": original["id"]}
    ).one()
    assert row.voided_by == accountant.id
    audit = db_session.execute(
        text("SELECT actor_id FROM audit_events WHERE action = 'voucher.reversal_created' AND entity_id = :v"),
        {"v": pair["reversal"]["id"]},
    ).scalar_one()
    assert audit == accountant.id


def test_e6_only_a_posted_voucher_can_be_voided(
    client: TestClient, bookkeeper: dict[str, str], approver: dict[str, str], admin: dict[str, str], ledger: Ledger
) -> None:
    ready = approved(client, bookkeeper, approver, voucher_body(ledger))
    refused = void_it(client, admin, ready)
    assert (refused.status_code, refused.json()["code"]) == (409, "INVALID_TRANSITION")


def test_e6_a_voucher_is_voided_once_and_a_repeat_with_the_same_key_returns_the_same_pair(
    client: TestClient, bookkeeper: dict[str, str], approver: dict[str, str], admin: dict[str, str], ledger: Ledger
) -> None:
    original = posted(client, bookkeeper, approver, voucher_body(ledger))
    attempt = key()
    first = void_it(client, admin, original, idempotency=attempt)
    repeat = void_it(client, admin, original, idempotency=attempt)
    assert (first.status_code, repeat.status_code) == (200, 200)
    assert first.json() == repeat.json()
    other_key = void_it(client, admin, first.json()["voucher"])  # a different key is a second attempt: refused
    assert (other_key.status_code, other_key.json()["code"]) == (409, "INVALID_TRANSITION")
    count = client.get("/api/v1/vouchers", headers=admin).json()["total"]
    assert count == 2  # the original and one reversal


def test_e6_a_void_key_cannot_be_reused_on_another_voucher(
    client: TestClient, bookkeeper: dict[str, str], approver: dict[str, str], admin: dict[str, str], ledger: Ledger
) -> None:
    first, second = (posted(client, bookkeeper, approver, voucher_body(ledger)) for _ in range(2))
    shared = key()
    assert void_it(client, admin, first, idempotency=shared).status_code == 200
    reused = void_it(client, admin, second, idempotency=shared)
    assert (reused.status_code, reused.json()["code"]) == (409, "IDEMPOTENCY_KEY_REUSED")


def test_e6_a_reversal_cannot_itself_be_voided(
    client: TestClient, bookkeeper: dict[str, str], approver: dict[str, str], admin: dict[str, str], ledger: Ledger
) -> None:
    original = posted(client, bookkeeper, approver, voucher_body(ledger))
    reversal = void_it(client, admin, original).json()["reversal"]
    refused = void_it(client, admin, reversal)
    assert (refused.status_code, refused.json()["code"]) == (409, "REVERSAL_NOT_VOIDABLE")
    assert client.get(f"/api/v1/vouchers/{reversal['id']}", headers=admin).json()["status"] == "posted"


def test_e6_a_void_voucher_stays_void(
    client: TestClient, bookkeeper: dict[str, str], approver: dict[str, str], admin: dict[str, str], ledger: Ledger
) -> None:
    original = posted(client, bookkeeper, approver, voucher_body(ledger))
    voided = void_it(client, admin, original).json()["voucher"]
    assert post_it(client, bookkeeper, voided).status_code == 409
    assert move(client, bookkeeper, voided, "reopen").status_code == 409


def test_e6_voiding_into_a_closed_period_is_refused(
    client: TestClient, bookkeeper: dict[str, str], approver: dict[str, str], admin: dict[str, str], ledger: Ledger
) -> None:
    original = posted(client, bookkeeper, approver, voucher_body(ledger, document_date="2026-09-15"))
    client.post(
        "/api/v1/periods/close", json={"start_date": "2026-10-01", "end_date": "2026-10-31"}, headers=admin
    )  # today's month
    refused = void_it(client, admin, original)
    assert (refused.status_code, refused.json()["code"]) == (409, "PERIOD_CLOSED")
    assert client.get(f"/api/v1/vouchers/{original['id']}", headers=admin).json()["status"] == "posted"
    assert client.get("/api/v1/vouchers", headers=admin).json()["total"] == 1  # no reversal, no number used


def test_e6_the_voucher_list_filters_and_links_voids_to_their_reversals(
    client: TestClient, bookkeeper: dict[str, str], approver: dict[str, str], admin: dict[str, str], ledger: Ledger
) -> None:
    keep = posted(client, bookkeeper, approver, voucher_body(ledger, "10.00", description="Keep me"))
    cancel = posted(client, bookkeeper, approver, voucher_body(ledger, "20.00", description="Cancel me"))
    void_it(client, admin, cancel)
    create(client, bookkeeper, voucher_body(ledger, voucher_type="JV", description="Still draft"))

    def numbers(query: str) -> list[str | None]:
        return [
            v["number"] for v in client.get(f"/api/v1/vouchers?{query}&sort=created_at", headers=admin).json()["items"]
        ]

    assert numbers("status=posted") == ["PV-2026-0001", "PV-2026-0003"]
    assert numbers("status=void") == ["PV-2026-0002"]
    assert numbers("voucher_type=JV") == [None]
    assert numbers("q=pv-2026-0001") == ["PV-2026-0001"]
    assert numbers("q=keep") == ["PV-2026-0001"]
    # The voided voucher and the reversal that cancels it come to the same amount.
    assert numbers("amount_min=15&amount_max=25") == ["PV-2026-0002", "PV-2026-0003"]
    assert numbers("amount_max=9.99") == []
    assert client.get("/api/v1/vouchers?amount_min=-1", headers=admin).status_code == 422
    page = client.get("/api/v1/vouchers?limit=2&offset=1&sort=created_at", headers=admin).json()
    assert (page["total"], len(page["items"])) == (4, 2)
    assert client.get("/api/v1/vouchers?sort=void_key", headers=admin).status_code == 422
    assert keep["number"] == "PV-2026-0001"
    assert date.fromisoformat(client.get(f"/api/v1/vouchers/{keep['id']}", headers=admin).json()["document_date"])
