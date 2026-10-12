"""Stories E4 (generate a voucher from an approved expense or purchase), C6 (posting the voucher posts its expense)
and D5 (a purchase and its paying voucher link both ways)."""

from collections.abc import Callable
from decimal import Decimal
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.enums import PostingKey, Role
from app.models.user import User
from tests.support.documents import (
    Ledger,
    Lookups,
    create_ledger,
    create_lookups,
    direct_expense,
    indirect_expense,
    purchase_body,
    purchase_line,
)

Make = Callable[..., User]
Auth = Callable[[User], dict[str, str]]


@pytest.fixture
def lookups(db_session: Session, make: Make) -> Lookups:
    return create_lookups(db_session, make(Role.ADMIN))


@pytest.fixture
def ledger(db_session: Session, make: Make, lookups: Lookups) -> Ledger:
    return create_ledger(db_session, lookups, make(Role.ADMIN))


@pytest.fixture
def staff(make: Make, auth: Auth) -> dict[str, str]:
    return auth(make(Role.STAFF))


@pytest.fixture
def bookkeeper(make: Make, auth: Auth) -> dict[str, str]:
    return auth(make(Role.ACCOUNTANT))


@pytest.fixture
def approver(make: Make, auth: Auth) -> dict[str, str]:
    return auth(make(Role.APPROVER))


@pytest.fixture
def admin(make: Make, auth: Auth) -> dict[str, str]:
    return auth(make(Role.ADMIN))


def v(headers: dict[str, str], doc: dict[str, Any], **extra: str) -> dict[str, str]:
    return {**headers, "If-Match": str(doc["version"]), **extra}


def approved_expense(
    client: TestClient, author: dict[str, str], reviewer: dict[str, str], body: dict[str, Any]
) -> dict[str, Any]:
    expense = client.post("/api/v1/expenses", json=body, headers=author).json()
    expense = client.post(f"/api/v1/expenses/{expense['id']}/submit", headers=v(author, expense)).json()
    result: dict[str, Any] = client.post(
        f"/api/v1/expenses/{expense['id']}/approve", headers=v(reviewer, expense)
    ).json()
    assert result["status"] == "approved", result
    return result


def approved_purchase(
    client: TestClient, author: dict[str, str], reviewer: dict[str, str], body: dict[str, Any]
) -> dict[str, Any]:
    purchase = client.post("/api/v1/purchases", json=body, headers=author).json()
    purchase = client.post(f"/api/v1/purchases/{purchase['id']}/submit", headers=v(author, purchase)).json()
    result: dict[str, Any] = client.post(
        f"/api/v1/purchases/{purchase['id']}/approve", headers=v(reviewer, purchase)
    ).json()
    assert result["status"] == "approved", result
    return result


def generate_expense(client: TestClient, headers: dict[str, str], expense: dict[str, Any]) -> Any:
    return client.post(f"/api/v1/expenses/{expense['id']}/generate-voucher", headers=headers)


def generate_purchase(client: TestClient, headers: dict[str, str], purchase: dict[str, Any], **body: Any) -> Any:
    return client.post(
        f"/api/v1/purchases/{purchase['id']}/generate-voucher", json={"payment_method": "cash", **body}, headers=headers
    )


def shape(voucher: dict[str, Any]) -> list[tuple[str, str, str, int | None]]:
    return [(ln["account_code"], ln["debit"], ln["credit"], ln["cost_center_id"]) for ln in voucher["lines"]]


# E4: from an expense -------------------------------------------------------------------------------------------------


def test_e4_a_cash_expense_becomes_a_draft_payment_voucher_crediting_cash(
    client: TestClient,
    staff: dict[str, str],
    approver: dict[str, str],
    bookkeeper: dict[str, str],
    lookups: Lookups,
    ledger: Ledger,
) -> None:
    expense = approved_expense(
        client, staff, approver, direct_expense(lookups, amount="1500.00", payment_method="cash")
    )
    response = generate_expense(client, bookkeeper, expense)
    assert response.status_code == 201, response.text
    voucher = response.json()
    assert (voucher["voucher_type"], voucher["status"], voucher["number"], voucher["expense_id"]) == (
        "PV",
        "draft",
        None,
        expense["id"],
    )
    assert shape(voucher) == [("5100", "1500.00", "0.00", lookups.centres[0].id), ("1100", "0.00", "1500.00", None)]
    assert voucher["description"] == expense["description"]
    assert (voucher["total_debit"], voucher["total_credit"]) == ("1500.00", "1500.00")


@pytest.mark.parametrize("method", ["bank_transfer", "card", "cheque"])
def test_e4_every_other_payment_method_credits_the_bank(
    client: TestClient,
    staff: dict[str, str],
    approver: dict[str, str],
    bookkeeper: dict[str, str],
    lookups: Lookups,
    ledger: Ledger,
    method: str,
) -> None:
    expense = approved_expense(client, staff, approver, direct_expense(lookups, payment_method=method))
    voucher = generate_expense(client, bookkeeper, expense).json()
    assert voucher["lines"][-1]["account_code"] == "1200"


def test_e4_tax_is_a_separate_line_and_the_expense_gets_the_net(
    client: TestClient,
    staff: dict[str, str],
    approver: dict[str, str],
    bookkeeper: dict[str, str],
    lookups: Lookups,
    ledger: Ledger,
) -> None:
    expense = approved_expense(client, staff, approver, direct_expense(lookups, amount="1180.00", tax_amount="180.00"))
    voucher = generate_expense(client, bookkeeper, expense).json()
    assert [(ln["account_code"], ln["debit"], ln["credit"]) for ln in voucher["lines"]] == [
        ("5100", "1000.00", "0.00"),
        ("1300", "180.00", "0.00"),
        ("1100", "0.00", "1180.00"),
    ]


def test_e4_a_direct_expense_keeps_its_project_on_the_line(
    client: TestClient,
    staff: dict[str, str],
    approver: dict[str, str],
    bookkeeper: dict[str, str],
    lookups: Lookups,
    ledger: Ledger,
) -> None:
    body = direct_expense(lookups, project_id=lookups.project.id, cost_center_id=None)
    voucher = generate_expense(client, bookkeeper, approved_expense(client, staff, approver, body)).json()
    assert voucher["lines"][0]["project_id"] == lookups.project.id


def test_e4_an_indirect_expense_is_split_over_cost_centres_exactly_as_approved(
    client: TestClient,
    staff: dict[str, str],
    approver: dict[str, str],
    bookkeeper: dict[str, str],
    lookups: Lookups,
    ledger: Ledger,
) -> None:
    a, b, c = (centre.id for centre in lookups.centres)
    lines = [
        {"cost_center_id": a, "basis_points": 3333},
        {"cost_center_id": b, "basis_points": 3333},
        {"cost_center_id": c, "basis_points": 3334},
    ]
    expense = approved_expense(client, staff, approver, indirect_expense(lookups, lines))
    approved_split = [(row["cost_center_id"], row["amount"]) for row in expense["allocations"]]
    voucher = generate_expense(client, bookkeeper, expense).json()
    debits = [(ln["cost_center_id"], ln["debit"]) for ln in voucher["lines"] if ln["debit"] != "0.00"]
    assert debits == approved_split == [(a, "33.33"), (b, "33.33"), (c, "33.34")]


def test_e4_a_fixed_split_with_tax_shares_the_net_and_never_splits_the_tax(
    client: TestClient,
    staff: dict[str, str],
    approver: dict[str, str],
    bookkeeper: dict[str, str],
    lookups: Lookups,
    ledger: Ledger,
) -> None:
    a, b, _ = (centre.id for centre in lookups.centres)
    lines = [{"cost_center_id": a, "amount": "59.00"}, {"cost_center_id": b, "amount": "59.00"}]
    expense = approved_expense(
        client,
        staff,
        approver,
        indirect_expense(lookups, lines, method="fixed", amount="118.00", tax_amount="18.00", payment_method="cash"),
    )
    voucher = generate_expense(client, bookkeeper, expense).json()
    assert [(ln["account_code"], ln["cost_center_id"], ln["debit"], ln["credit"]) for ln in voucher["lines"]] == [
        ("5100", a, "50.00", "0.00"),
        ("5100", b, "50.00", "0.00"),
        ("1300", None, "18.00", "0.00"),
        ("1100", None, "0.00", "118.00"),
    ]
    assert Decimal(voucher["total_debit"]) == Decimal(voucher["total_credit"]) == Decimal("118.00")


def test_e4_only_an_approved_expense_and_only_once(
    client: TestClient,
    staff: dict[str, str],
    approver: dict[str, str],
    bookkeeper: dict[str, str],
    lookups: Lookups,
    ledger: Ledger,
) -> None:
    draft = client.post("/api/v1/expenses", json=direct_expense(lookups), headers=staff).json()
    early = generate_expense(client, bookkeeper, draft)
    assert (early.status_code, early.json()["code"]) == (409, "SOURCE_NOT_APPROVED")
    expense = approved_expense(client, staff, approver, direct_expense(lookups))
    first = generate_expense(client, bookkeeper, expense)
    again = generate_expense(client, bookkeeper, expense)
    assert (first.status_code, again.status_code, again.json()["code"]) == (201, 409, "ALREADY_GENERATED")
    assert str(first.json()["id"]) in again.json()["detail"]


def test_e4_only_bookkeepers_generate(
    client: TestClient,
    make: Make,
    auth: Auth,
    staff: dict[str, str],
    approver: dict[str, str],
    lookups: Lookups,
    ledger: Ledger,
) -> None:
    expense = approved_expense(client, staff, approver, direct_expense(lookups))
    for headers in (staff, approver):
        assert generate_expense(client, headers, expense).status_code == 403
    assert generate_expense(client, auth(make(Role.ADMIN)), expense).status_code == 201


def test_e4_a_missing_posting_account_is_explained(
    client: TestClient,
    staff: dict[str, str],
    approver: dict[str, str],
    bookkeeper: dict[str, str],
    lookups: Lookups,
    db_session: Session,
    make: Make,
) -> None:
    create_ledger(db_session, lookups, make(Role.ADMIN), skip=("cash",))
    expense = approved_expense(client, staff, approver, direct_expense(lookups, payment_method="cash"))
    response = generate_expense(client, bookkeeper, expense)
    assert (response.status_code, response.json()["code"]) == (422, "POSTING_ACCOUNT_MISSING")
    assert "'cash'" in response.json()["detail"]
    assert client.get("/api/v1/vouchers", headers=bookkeeper).json()["total"] == 0


def test_e4_the_tax_account_is_only_needed_when_there_is_tax(
    client: TestClient,
    staff: dict[str, str],
    approver: dict[str, str],
    bookkeeper: dict[str, str],
    lookups: Lookups,
    db_session: Session,
    make: Make,
) -> None:
    create_ledger(db_session, lookups, make(Role.ADMIN), skip=("input_sales_tax",))
    no_tax = approved_expense(client, staff, approver, direct_expense(lookups))
    assert generate_expense(client, bookkeeper, no_tax).status_code == 201
    with_tax = approved_expense(client, staff, approver, direct_expense(lookups, amount="118.00", tax_amount="18.00"))
    assert generate_expense(client, bookkeeper, with_tax).json()["code"] == "POSTING_ACCOUNT_MISSING"


def test_e4_the_generated_draft_can_be_edited_before_it_is_submitted(
    client: TestClient,
    staff: dict[str, str],
    approver: dict[str, str],
    bookkeeper: dict[str, str],
    lookups: Lookups,
    ledger: Ledger,
) -> None:
    voucher = generate_expense(
        client, bookkeeper, approved_expense(client, staff, approver, direct_expense(lookups))
    ).json()
    moved = [
        {"account_id": ledger.other_expense.id, "debit": "1500.00"},
        {"account_id": ledger.cash.id, "credit": "1500.00"},
    ]
    edited = client.patch(f"/api/v1/vouchers/{voucher['id']}", json={"lines": moved}, headers=v(bookkeeper, voucher))
    assert edited.status_code == 200
    assert edited.json()["lines"][0]["account_code"] == "5600"
    assert edited.json()["expense_id"] == voucher["expense_id"]  # still the voucher for that expense


# E4: from a purchase -------------------------------------------------------------------------------------------------


def test_e4_a_purchase_voucher_keeps_each_withholding_on_its_own_credit_line(
    client: TestClient, bookkeeper: dict[str, str], approver: dict[str, str], lookups: Lookups, ledger: Ledger
) -> None:
    line = purchase_line(quantity="3.500", rate="1200.00", sales_tax_bp=1800)
    purchase = approved_purchase(client, bookkeeper, approver, purchase_body(lookups.vendors["reg_filer"], [line]))
    response = generate_purchase(
        client, bookkeeper, purchase, category_id=lookups.category.id, payment_method="bank_transfer"
    )
    assert response.status_code == 201, response.text
    voucher = response.json()
    assert [(ln["account_code"], ln["debit"], ln["credit"]) for ln in voucher["lines"]] == [
        ("5100", "4200.00", "0.00"),  # the purchase
        ("1300", "756.00", "0.00"),  # sales tax, on its own line
        ("1200", "0.00", "4581.78"),  # what the vendor is paid, from the bank
        ("2200", "0.00", "151.20"),  # sales tax withheld
        ("2300", "0.00", "223.02"),  # income tax withheld
    ]
    assert (voucher["purchase_id"], voucher["voucher_type"], voucher["status"]) == (purchase["id"], "PV", "draft")
    assert "Ravi Stationers" in voucher["description"]
    assert "INV-2026-0042" in voucher["description"]


def test_e4_an_unregistered_purchase_has_no_sales_tax_line(
    client: TestClient, bookkeeper: dict[str, str], approver: dict[str, str], lookups: Lookups, ledger: Ledger
) -> None:
    purchase = approved_purchase(
        client,
        bookkeeper,
        approver,
        purchase_body(lookups.vendors["unreg_nonfiler"], [purchase_line(category="services")]),
    )
    voucher = generate_purchase(client, bookkeeper, purchase, category_id=lookups.category.id).json()
    assert [ln["account_code"] for ln in voucher["lines"]] == ["5100", "1100", "2200", "2300"]
    assert Decimal(voucher["total_debit"]) == Decimal(voucher["total_credit"])


def test_e4_a_purchase_needs_a_category_and_a_payment_method_and_an_approved_state(
    client: TestClient,
    bookkeeper: dict[str, str],
    approver: dict[str, str],
    lookups: Lookups,
    ledger: Ledger,
    db_session: Session,
) -> None:
    purchase = approved_purchase(client, bookkeeper, approver, purchase_body(lookups.vendors["unreg_nonfiler"]))
    url = f"/api/v1/purchases/{purchase['id']}/generate-voucher"
    assert client.post(url, json={}, headers=bookkeeper).status_code == 422
    assert client.post(url, json={"category_id": lookups.category.id}, headers=bookkeeper).status_code == 422
    assert (
        client.post(
            url, json={"category_id": lookups.category.id, "payment_method": "gold"}, headers=bookkeeper
        ).status_code
        == 422
    )
    assert (
        client.post(url, json={"category_id": 999_999, "payment_method": "cash"}, headers=bookkeeper).status_code == 422
    )
    lookups.other_category.is_active = False
    db_session.commit()
    inactive = client.post(
        url, json={"category_id": lookups.other_category.id, "payment_method": "cash"}, headers=bookkeeper
    )
    assert inactive.json()["errors"][0]["field"] == "category_id"
    draft = client.post(
        "/api/v1/purchases", json=purchase_body(lookups.vendors["unreg_nonfiler"]), headers=bookkeeper
    ).json()
    early = generate_purchase(client, bookkeeper, draft, category_id=lookups.category.id)
    assert early.json()["code"] == "SOURCE_NOT_APPROVED"
    assert generate_purchase(client, bookkeeper, purchase, category_id=lookups.category.id).status_code == 201
    assert (
        generate_purchase(client, bookkeeper, purchase, category_id=lookups.category.id).json()["code"]
        == "ALREADY_GENERATED"
    )


# C6 and D5: posting posts the source; links both ways ----------------------------------------------------------------


def walk_to_posted(
    client: TestClient, bookkeeper: dict[str, str], reviewer: dict[str, str], voucher: dict[str, Any]
) -> dict[str, Any]:
    submitted = client.post(f"/api/v1/vouchers/{voucher['id']}/submit", headers=v(bookkeeper, voucher)).json()
    ready = client.post(f"/api/v1/vouchers/{voucher['id']}/approve", headers=v(reviewer, submitted)).json()
    result: dict[str, Any] = client.post(
        f"/api/v1/vouchers/{voucher['id']}/post",
        headers=v(bookkeeper, ready, **{"Idempotency-Key": "post-" + str(voucher["id"]) + "-attempt"}),
    ).json()
    assert result["status"] == "posted", result
    return result


def test_c6_posting_the_voucher_posts_the_expense_and_locks_it(
    client: TestClient,
    staff: dict[str, str],
    approver: dict[str, str],
    bookkeeper: dict[str, str],
    lookups: Lookups,
    ledger: Ledger,
) -> None:
    expense = approved_expense(client, staff, approver, direct_expense(lookups))
    voucher = generate_expense(client, bookkeeper, expense).json()
    in_draft = client.get(f"/api/v1/expenses/{expense['id']}", headers=staff).json()
    assert in_draft["status"] == "approved"
    assert in_draft["voucher"] == {"id": voucher["id"], "voucher_type": "PV", "number": None, "status": "draft"}

    done = walk_to_posted(client, bookkeeper, approver, voucher)
    after = client.get(f"/api/v1/expenses/{expense['id']}", headers=staff).json()
    assert after["status"] == "posted"
    assert after["voucher"] == {"id": voucher["id"], "voucher_type": "PV", "number": done["number"], "status": "posted"}
    assert after["actions"] == []
    edit = client.patch(f"/api/v1/expenses/{expense['id']}", json={"description": "Changed"}, headers=v(staff, after))
    assert (edit.status_code, edit.json()["code"]) == (409, "DOCUMENT_LOCKED")
    history = client.get(f"/api/v1/expenses/{expense['id']}/history", headers=staff).json()
    assert [(h["action"], h["to_status"]) for h in history][-1] == ("posted", "posted")


def test_c6_the_expense_is_posted_in_the_same_transaction_as_the_voucher(
    client: TestClient,
    staff: dict[str, str],
    approver: dict[str, str],
    bookkeeper: dict[str, str],
    lookups: Lookups,
    ledger: Ledger,
    admin: dict[str, str],
) -> None:
    """A voucher that cannot post (here, a closed period) leaves its expense approved, not half posted."""
    expense = approved_expense(client, staff, approver, direct_expense(lookups))
    voucher = generate_expense(client, bookkeeper, expense).json()
    client.post("/api/v1/periods/close", json={"start_date": "2026-10-01", "end_date": "2026-10-31"}, headers=admin)
    submitted = client.post(f"/api/v1/vouchers/{voucher['id']}/submit", headers=v(bookkeeper, voucher)).json()
    ready = client.post(f"/api/v1/vouchers/{voucher['id']}/approve", headers=v(approver, submitted)).json()
    refused = client.post(
        f"/api/v1/vouchers/{voucher['id']}/post",
        headers=v(bookkeeper, ready, **{"Idempotency-Key": "closed-period-attempt"}),
    )
    assert refused.json()["code"] == "PERIOD_CLOSED"
    assert client.get(f"/api/v1/expenses/{expense['id']}", headers=staff).json()["status"] == "approved"


def test_d5_a_purchase_and_its_paying_voucher_link_both_ways(
    client: TestClient, bookkeeper: dict[str, str], approver: dict[str, str], lookups: Lookups, ledger: Ledger
) -> None:
    purchase = approved_purchase(client, bookkeeper, approver, purchase_body(lookups.vendors["reg_nonfiler"]))
    assert purchase["voucher"] is None
    voucher = generate_purchase(client, bookkeeper, purchase, category_id=lookups.category.id).json()
    shown = client.get(f"/api/v1/purchases/{purchase['id']}", headers=approver).json()
    assert shown["voucher"]["id"] == voucher["id"]
    assert client.get(f"/api/v1/vouchers/{voucher['id']}", headers=approver).json()["purchase_id"] == purchase["id"]

    done = walk_to_posted(client, bookkeeper, approver, voucher)
    final = client.get(f"/api/v1/purchases/{purchase['id']}", headers=approver).json()
    assert (final["status"], final["voucher"]["number"], final["voucher"]["status"]) == (
        "posted",
        done["number"],
        "posted",
    )
    listed = client.get("/api/v1/purchases", headers=approver).json()["items"][0]
    assert listed["voucher"]["number"] == done["number"]


def test_c6_voiding_the_voucher_does_not_reopen_its_source(
    client: TestClient,
    staff: dict[str, str],
    approver: dict[str, str],
    bookkeeper: dict[str, str],
    admin: dict[str, str],
    lookups: Lookups,
    ledger: Ledger,
) -> None:
    """Decision 33: posting is irreversible by rule, so the expense stays posted and the books carry the reversal."""
    expense = approved_expense(client, staff, approver, direct_expense(lookups))
    done = walk_to_posted(client, bookkeeper, approver, generate_expense(client, bookkeeper, expense).json())
    response = client.post(
        f"/api/v1/vouchers/{done['id']}/void",
        json={"reason": "Paid twice"},
        headers=v(admin, done, **{"Idempotency-Key": "void-for-source-1"}),
    )
    assert response.status_code == 200
    assert client.get(f"/api/v1/expenses/{expense['id']}", headers=staff).json()["status"] == "posted"
    assert generate_expense(client, bookkeeper, expense).json()["code"] == "SOURCE_NOT_APPROVED"


def test_the_expense_list_carries_each_vouchers_link_in_one_pass(
    client: TestClient,
    staff: dict[str, str],
    approver: dict[str, str],
    bookkeeper: dict[str, str],
    lookups: Lookups,
    ledger: Ledger,
) -> None:
    linked = approved_expense(client, staff, approver, direct_expense(lookups, description="Has a voucher"))
    generate_expense(client, bookkeeper, linked)
    approved_expense(client, staff, approver, direct_expense(lookups, description="Has none"))
    items = {e["description"]: e["voucher"] for e in client.get("/api/v1/expenses", headers=bookkeeper).json()["items"]}
    assert items["Has a voucher"]["status"] == "draft"
    assert items["Has none"] is None


def test_the_posting_keys_the_generator_uses_are_the_five_the_system_defines() -> None:
    assert {k.value for k in PostingKey} == {
        "cash",
        "bank",
        "input_sales_tax",
        "sales_tax_withheld",
        "income_tax_withheld",
    }
