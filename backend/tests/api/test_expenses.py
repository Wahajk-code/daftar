"""Stories C1 (direct), C2 (indirect and allocation), C4 (submit), C5 (approve or reject), C7 (reopen), F2 (history),
A3 (Staff see only their own, as a 404) and A4 (nobody approves their own)."""

from collections.abc import Callable
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.enums import Role
from app.models.user import User
from tests.support.clock import FakeClock
from tests.support.documents import Lookups, create_lookups, direct_expense, indirect_expense

Make = Callable[..., User]
Auth = Callable[[User], dict[str, str]]


@pytest.fixture
def lookups(db_session: Session, make: Make) -> Lookups:
    return create_lookups(db_session, make(Role.ADMIN))


def create(client: TestClient, headers: dict[str, str], body: dict[str, Any]) -> Any:
    return client.post("/api/v1/expenses", json=body, headers=headers)


def with_version(headers: dict[str, str], expense: dict[str, Any]) -> dict[str, str]:
    return {**headers, "If-Match": str(expense["version"])}


def act(client: TestClient, headers: dict[str, str], expense: dict[str, Any], action: str, **body: Any) -> Any:
    return client.post(
        f"/api/v1/expenses/{expense['id']}/{action}", json=body or None, headers=with_version(headers, expense)
    )


def reload(client: TestClient, headers: dict[str, str], expense: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = client.get(f"/api/v1/expenses/{expense['id']}", headers=headers).json()
    return result


def centres(lookups: Lookups) -> tuple[int, int, int]:
    first, second, third = (c.id for c in lookups.centres)
    return first, second, third


# C1: direct expenses -------------------------------------------------------------------------------------------------


def test_c1_a_direct_expense_against_a_cost_centre_a_project_or_a_product(
    client: TestClient, make: Make, auth: Auth, lookups: Lookups
) -> None:
    headers = auth(make(Role.STAFF))
    for attribution in (
        {"cost_center_id": lookups.centres[0].id},
        {"project_id": lookups.project.id, "cost_center_id": None},
        {"project_id": lookups.product.id, "cost_center_id": None},
        {"project_id": lookups.project.id, "cost_center_id": lookups.centres[1].id},
    ):
        response = create(client, headers, direct_expense(lookups, **attribution))
        assert response.status_code == 201, response.text
        body = response.json()
        assert (body["expense_type"], body["status"]) == ("direct", "draft")
        assert (body["amount"], body["tax_amount"], body["currency"]) == ("1500.00", "0.00", "PKR")
        assert body["allocations"] == []
        assert body["category_name"] == "Office rent"


def test_c1_the_author_and_the_defaults_are_set_by_the_server(
    client: TestClient, make: Make, auth: Auth, lookups: Lookups, clock: FakeClock
) -> None:
    user = make(Role.ACCOUNTANT, full_name="Usman Tariq")
    body = create(client, auth(user), direct_expense(lookups)).json()
    assert (body["created_by"], body["created_by_name"], body["version"]) == (user.id, "Usman Tariq", 1)
    assert body["document_date"] == "2026-10-12"
    assert body["created_at"].endswith("Z")
    # 00:30 on the 13th in Karachi is still 19:30 on the 12th in UTC; the document belongs to the 13th.
    clock.set(datetime(2026, 10, 12, 19, 30, tzinfo=UTC))
    late = create(client, auth(user), direct_expense(lookups)).json()
    assert late["document_date"] == "2026-10-13"
    back_dated = create(client, auth(user), direct_expense(lookups, document_date="2026-09-30")).json()
    assert back_dated["document_date"] == "2026-09-30"  # a plain date, never moved by a zone


def test_c1_a_direct_expense_must_say_where_the_money_went(
    client: TestClient, make: Make, auth: Auth, lookups: Lookups
) -> None:
    headers = auth(make(Role.STAFF))
    body = direct_expense(lookups)
    del body["cost_center_id"]
    response = create(client, headers, body)
    assert response.status_code == 422
    assert response.json()["errors"][0]["field"] == "project_id"


def test_c1_an_indirect_expense_cannot_name_a_destination_and_a_direct_one_cannot_be_split(
    client: TestClient, make: Make, auth: Auth, lookups: Lookups
) -> None:
    headers = auth(make(Role.STAFF))
    first, *_ = centres(lookups)
    lines = [{"cost_center_id": first, "basis_points": 10_000}]
    assert create(client, headers, indirect_expense(lookups, lines, project_id=lookups.project.id)).status_code == 422
    split_direct = direct_expense(lookups, allocation={"method": "percentage", "lines": lines})
    assert create(client, headers, split_direct).status_code == 422


@pytest.mark.parametrize(
    ("override", "field"),
    [
        ({"amount": "0.00"}, "amount"),
        ({"amount": "-5.00"}, "amount"),
        ({"amount": "10.005"}, "amount"),
        ({"amount": 10.5}, "amount"),
        ({"amount": "1000000000000.00"}, "amount"),
        ({"tax_amount": "1500.01"}, "tax_amount"),
        ({"tax_amount": "-1.00"}, "tax_amount"),
        ({"payment_method": "bitcoin"}, "payment_method"),
        ({"description": "x" * 1001}, "description"),
        ({"category_id": 999_999}, "category_id"),
        ({"cost_center_id": 999_999}, "cost_center_id"),
        ({"project_id": 999_999}, "project_id"),
        ({"status": "approved"}, "status"),
        ({"created_by": 1}, "created_by"),
    ],
)
def test_c1_bad_values_are_refused_with_the_field_named(
    client: TestClient, make: Make, auth: Auth, lookups: Lookups, override: dict[str, Any], field: str
) -> None:
    response = create(client, auth(make(Role.STAFF)), direct_expense(lookups, **override))
    assert response.status_code == 422, response.text
    assert field in {e["field"] for e in response.json()["errors"]}


def test_c1_an_inactive_category_or_cost_centre_cannot_be_used_on_a_new_expense(
    client: TestClient, make: Make, auth: Auth, lookups: Lookups, db_session: Session
) -> None:
    lookups.category.is_active = False
    lookups.centres[0].is_active = False
    db_session.commit()
    headers = auth(make(Role.STAFF))
    assert create(client, headers, direct_expense(lookups)).status_code == 422
    lookups.category.is_active = True
    db_session.commit()
    assert create(client, headers, direct_expense(lookups)).status_code == 422  # the cost centre is still inactive


def test_c1_the_amount_is_gross_and_the_tax_is_only_recorded(
    client: TestClient, make: Make, auth: Auth, lookups: Lookups
) -> None:
    body = create(client, auth(make(Role.STAFF)), direct_expense(lookups, amount="1180.00", tax_amount="180.00")).json()
    assert (body["amount"], body["tax_amount"]) == ("1180.00", "180.00")


def test_c1_an_approver_cannot_create_an_expense(client: TestClient, make: Make, auth: Auth, lookups: Lookups) -> None:
    assert create(client, auth(make(Role.APPROVER)), direct_expense(lookups)).status_code == 403


def test_c1_a_draft_is_edited_by_its_author_with_the_current_version(
    client: TestClient, make: Make, auth: Auth, lookups: Lookups
) -> None:
    headers = auth(make(Role.STAFF))
    expense = create(client, headers, direct_expense(lookups)).json()
    url = f"/api/v1/expenses/{expense['id']}"
    missing = client.patch(url, json={"description": "New"}, headers=headers)
    assert (missing.status_code, missing.json()["errors"][0]["field"]) == (422, "If-Match")
    edited = client.patch(
        url, json={"description": "  New   words ", "amount": "2000.00"}, headers=with_version(headers, expense)
    )
    assert (edited.json()["description"], edited.json()["amount"], edited.json()["version"]) == (
        "New   words",
        "2000.00",
        2,
    )
    stale = client.patch(url, json={"description": "Again"}, headers=with_version(headers, expense))
    assert (stale.status_code, stale.json()["code"]) == (409, "VERSION_CONFLICT")


def test_c1_only_the_author_edits_a_draft(client: TestClient, make: Make, auth: Auth, lookups: Lookups) -> None:
    expense = create(client, auth(make(Role.ACCOUNTANT)), direct_expense(lookups)).json()
    other = client.patch(
        f"/api/v1/expenses/{expense['id']}",
        json={"description": "Mine now"},
        headers=with_version(auth(make(Role.ADMIN)), expense),
    )
    assert (other.status_code, other.json()["code"]) == (403, "FORBIDDEN")


# C2: indirect expenses and allocation --------------------------------------------------------------------------------


def split(lookups: Lookups, *bps: int) -> list[dict[str, Any]]:
    return [{"cost_center_id": c.id, "basis_points": value} for c, value in zip(lookups.centres, bps, strict=False)]


def test_c2_a_percentage_split_adds_up_to_the_paisa(
    client: TestClient, make: Make, auth: Auth, lookups: Lookups
) -> None:
    body = create(client, auth(make(Role.STAFF)), indirect_expense(lookups, split(lookups, 3333, 3333, 3334))).json()
    assert body["allocation_method"] == "percentage"
    assert [(a["cost_center_code"], a["basis_points"], a["amount"]) for a in body["allocations"]] == [
        ("HO", 3333, "33.33"),
        ("OPS", 3333, "33.33"),
        ("IT", 3334, "33.34"),
    ]
    assert sum(Decimal(a["amount"]) for a in body["allocations"]) == Decimal("100.00")


def test_c2_the_leftover_paisa_goes_to_the_largest_remainder_then_the_lowest_id(
    client: TestClient, make: Make, auth: Auth, lookups: Lookups
) -> None:
    headers = auth(make(Role.STAFF))
    expense = create(client, headers, indirect_expense(lookups, split(lookups, 5000, 5000), amount="0.05")).json()
    amounts = {a["cost_center_code"]: a["amount"] for a in expense["allocations"]}
    assert amounts == {"HO": "0.03", "OPS": "0.02"}  # equal remainders: the lower cost centre id takes the extra paisa
    # Recalculated at a new amount, the same cost centre still receives it.
    again = client.patch(
        f"/api/v1/expenses/{expense['id']}", json={"amount": "0.07"}, headers=with_version(headers, expense)
    ).json()
    assert {a["cost_center_code"]: a["amount"] for a in again["allocations"]} == {"HO": "0.04", "OPS": "0.03"}


def test_c2_uneven_shares_follow_the_largest_remainder(
    client: TestClient, make: Make, auth: Auth, lookups: Lookups
) -> None:
    body = create(
        client, auth(make(Role.STAFF)), indirect_expense(lookups, split(lookups, 6000, 3000, 1000), amount="10000.00")
    ).json()
    assert [a["amount"] for a in body["allocations"]] == ["6000.00", "3000.00", "1000.00"]
    seven_five = create(
        client, auth(make(Role.STAFF)), indirect_expense(lookups, split(lookups, 3300, 3300, 3400), amount="7500.00")
    ).json()
    assert [a["amount"] for a in seven_five["allocations"]] == ["2475.00", "2475.00", "2550.00"]


@pytest.mark.parametrize("total", [9999, 10_001, 5000])
def test_c2_percentages_that_do_not_total_ten_thousand_are_refused(
    client: TestClient, make: Make, auth: Auth, lookups: Lookups, total: int
) -> None:
    lines = split(lookups, total - 5000, 5000)
    response = create(client, auth(make(Role.STAFF)), indirect_expense(lookups, lines))
    assert (response.status_code, response.json()["code"]) == (422, "ALLOCATION_MISMATCH")
    assert str(total) in response.json()["detail"]


def test_c2_fixed_amounts_must_total_exactly_the_expense(
    client: TestClient, make: Make, auth: Auth, lookups: Lookups
) -> None:
    headers = auth(make(Role.STAFF))
    first, second, _ = centres(lookups)
    good = [{"cost_center_id": first, "amount": "60.10"}, {"cost_center_id": second, "amount": "39.90"}]
    ok = create(client, headers, indirect_expense(lookups, good, method="fixed"))
    assert ok.status_code == 201
    assert [(a["basis_points"], a["amount"]) for a in ok.json()["allocations"]] == [(None, "60.10"), (None, "39.90")]
    for total in ("99.99", "100.01"):
        lines = [
            {"cost_center_id": first, "amount": "60.00"},
            {"cost_center_id": second, "amount": str(Decimal(total) - 60)},
        ]
        bad = create(client, headers, indirect_expense(lookups, lines, method="fixed"))
        assert (bad.status_code, bad.json()["code"]) == (422, "ALLOCATION_MISMATCH")


@pytest.mark.parametrize(
    "allocation",
    [
        {"method": "percentage", "lines": []},
        {"method": "percentage", "lines": [{"cost_center_id": 1, "amount": "5.00"}]},
        {"method": "fixed", "lines": [{"cost_center_id": 1, "basis_points": 10000}]},
        {
            "method": "percentage",
            "lines": [{"cost_center_id": 1, "basis_points": 5000}, {"cost_center_id": 1, "basis_points": 5000}],
        },
        {"method": "percentage", "lines": [{"cost_center_id": 1, "basis_points": 10001}]},
        {"method": "percentage", "lines": [{"cost_center_id": 1, "basis_points": 99.5}]},
        {"method": "weighted", "lines": [{"cost_center_id": 1, "basis_points": 10000}]},
    ],
)
def test_c2_a_malformed_split_is_refused(
    client: TestClient, make: Make, auth: Auth, lookups: Lookups, allocation: dict[str, Any]
) -> None:
    body = indirect_expense(lookups, [], allocation=allocation)
    assert create(client, auth(make(Role.STAFF)), body).status_code == 422


def test_c2_a_split_can_only_use_active_cost_centres(
    client: TestClient, make: Make, auth: Auth, lookups: Lookups
) -> None:
    lines = [{"cost_center_id": 999_999, "basis_points": 10_000}]
    response = create(client, auth(make(Role.STAFF)), indirect_expense(lookups, lines))
    assert response.status_code == 422
    assert response.json()["errors"][0]["field"] == "allocation.lines.0.cost_center_id"


def test_c2_changing_the_amount_recalculates_a_percentage_split_and_a_fixed_split_must_be_resent(
    client: TestClient, make: Make, auth: Auth, lookups: Lookups
) -> None:
    headers = auth(make(Role.STAFF))
    first, second, _ = centres(lookups)
    percent = create(client, headers, indirect_expense(lookups, split(lookups, 3333, 3333, 3334))).json()
    changed = client.patch(
        f"/api/v1/expenses/{percent['id']}", json={"amount": "250.00"}, headers=with_version(headers, percent)
    ).json()
    assert sum(Decimal(a["amount"]) for a in changed["allocations"]) == Decimal("250.00")
    assert [a["basis_points"] for a in changed["allocations"]] == [3333, 3333, 3334]

    fixed_lines = [{"cost_center_id": first, "amount": "60.00"}, {"cost_center_id": second, "amount": "40.00"}]
    fixed = create(client, headers, indirect_expense(lookups, fixed_lines, method="fixed")).json()
    refused = client.patch(
        f"/api/v1/expenses/{fixed['id']}", json={"amount": "250.00"}, headers=with_version(headers, fixed)
    )
    assert (refused.status_code, refused.json()["code"]) == (422, "ALLOCATION_MISMATCH")
    resent = client.patch(
        f"/api/v1/expenses/{fixed['id']}",
        json={
            "amount": "250.00",
            "allocation": {
                "method": "fixed",
                "lines": [
                    {"cost_center_id": first, "amount": "100.00"},
                    {"cost_center_id": second, "amount": "150.00"},
                ],
            },
        },
        headers=with_version(headers, fixed),
    )
    assert resent.status_code == 200
    assert [a["amount"] for a in resent.json()["allocations"]] == ["100.00", "150.00"]


def test_c2_the_split_can_be_replaced_and_may_switch_method(
    client: TestClient, make: Make, auth: Auth, lookups: Lookups
) -> None:
    headers = auth(make(Role.STAFF))
    first, second, third = centres(lookups)
    expense = create(client, headers, indirect_expense(lookups, split(lookups, 5000, 5000))).json()
    replaced = client.patch(
        f"/api/v1/expenses/{expense['id']}",
        json={"allocation": {"method": "fixed", "lines": [{"cost_center_id": third, "amount": "100.00"}]}},
        headers=with_version(headers, expense),
    ).json()
    assert (replaced["allocation_method"], [a["cost_center_code"] for a in replaced["allocations"]]) == (
        "fixed",
        ["IT"],
    )
    assert {first, second} == {lookups.centres[0].id, lookups.centres[1].id}


def test_c2_the_type_can_change_only_while_draft_and_clears_what_no_longer_applies(
    client: TestClient, make: Make, auth: Auth, lookups: Lookups
) -> None:
    headers = auth(make(Role.STAFF))
    indirect = create(client, headers, indirect_expense(lookups, split(lookups, 5000, 5000))).json()
    # Indirect to direct needs a destination, and drops the split.
    no_destination = client.patch(
        f"/api/v1/expenses/{indirect['id']}", json={"expense_type": "direct"}, headers=with_version(headers, indirect)
    )
    assert no_destination.status_code == 422
    direct = client.patch(
        f"/api/v1/expenses/{indirect['id']}",
        json={"expense_type": "direct", "project_id": lookups.project.id},
        headers=with_version(headers, indirect),
    ).json()
    assert (direct["expense_type"], direct["project_id"], direct["allocations"], direct["allocation_method"]) == (
        "direct",
        lookups.project.id,
        [],
        None,
    )
    # Direct to indirect drops the destination; the split can follow.
    back = client.patch(
        f"/api/v1/expenses/{indirect['id']}",
        json={"expense_type": "indirect", "allocation": {"method": "percentage", "lines": split(lookups, 10_000)}},
        headers=with_version(headers, direct),
    ).json()
    assert (back["expense_type"], back["project_id"], back["cost_center_id"], len(back["allocations"])) == (
        "indirect",
        None,
        None,
        1,
    )
    # Once submitted the type is locked.
    submitted = act(client, headers, back, "submit").json()
    locked = client.patch(
        f"/api/v1/expenses/{indirect['id']}",
        json={"expense_type": "direct", "cost_center_id": lookups.centres[0].id},
        headers=with_version(headers, submitted),
    )
    assert (locked.status_code, locked.json()["code"]) == (409, "DOCUMENT_LOCKED")


def test_c2_the_preview_reports_a_shortfall_instead_of_failing(
    client: TestClient, make: Make, auth: Auth, lookups: Lookups
) -> None:
    headers = auth(make(Role.STAFF))
    first, second, _ = centres(lookups)

    def preview(allocation: dict[str, Any], amount: str = "100.00") -> dict[str, Any]:
        response = client.post(
            "/api/v1/expenses/preview-allocation", json={"amount": amount, "allocation": allocation}, headers=headers
        )
        assert response.status_code == 200, response.text
        body: dict[str, Any] = response.json()
        return body

    short = preview(
        {
            "method": "percentage",
            "lines": [
                {"cost_center_id": first, "basis_points": 4000},
                {"cost_center_id": second, "basis_points": 3000},
            ],
        }
    )
    assert (short["complete"], short["remaining_basis_points"], short["allocated"], short["remaining"]) == (
        False,
        3000,
        "70.00",
        "30.00",
    )
    assert [(ln["cost_center_code"], ln["amount"]) for ln in short["lines"]] == [("HO", "40.00"), ("OPS", "30.00")]
    exact = preview({"method": "percentage", "lines": split(lookups, 3333, 3333, 3334)})
    assert (exact["complete"], exact["remaining"], exact["allocated"]) == (True, "0.00", "100.00")
    over = preview(
        {
            "method": "fixed",
            "lines": [{"cost_center_id": first, "amount": "70.00"}, {"cost_center_id": second, "amount": "50.00"}],
        }
    )
    assert (over["complete"], over["remaining"]) == (False, "-20.00")
    nothing_saved = client.get("/api/v1/expenses", headers=headers).json()
    assert nothing_saved["total"] == 0


# C4: submitting ------------------------------------------------------------------------------------------------------


def test_c4_submitting_makes_the_expense_read_only_to_its_author(
    client: TestClient, make: Make, auth: Auth, lookups: Lookups
) -> None:
    headers = auth(make(Role.STAFF))
    expense = create(client, headers, direct_expense(lookups)).json()
    assert expense["actions"] == ["submit"]
    submitted = act(client, headers, expense, "submit")
    assert submitted.status_code == 200
    assert (submitted.json()["status"], submitted.json()["actions"]) == ("submitted", [])
    locked = client.patch(
        f"/api/v1/expenses/{expense['id']}",
        json={"description": "Too late"},
        headers=with_version(headers, submitted.json()),
    )
    assert (locked.status_code, locked.json()["code"]) == (409, "DOCUMENT_LOCKED")
    again = act(client, headers, submitted.json(), "submit")
    assert (again.status_code, again.json()["code"]) == (409, "INVALID_TRANSITION")


def test_c4_an_incomplete_expense_says_what_is_missing(
    client: TestClient, make: Make, auth: Auth, lookups: Lookups
) -> None:
    headers = auth(make(Role.STAFF))
    blank = create(client, headers, direct_expense(lookups, description="  ")).json()
    refused = act(client, headers, blank, "submit")
    assert (refused.status_code, refused.json()["code"]) == (422, "DOCUMENT_INCOMPLETE")
    assert refused.json()["errors"][0]["field"] == "description"
    no_split = create(client, headers, {**indirect_expense(lookups, []), "allocation": None}).json()
    refused_split = act(client, headers, no_split, "submit")
    assert refused_split.json()["code"] == "DOCUMENT_INCOMPLETE"
    assert refused_split.json()["errors"][0]["field"] == "allocation"
    assert reload(client, headers, blank)["status"] == "draft"


def test_c4_only_the_author_submits_and_submitting_needs_the_current_version(
    client: TestClient, make: Make, auth: Auth, lookups: Lookups
) -> None:
    author = auth(make(Role.ACCOUNTANT))
    expense = create(client, author, direct_expense(lookups)).json()
    assert act(client, auth(make(Role.ADMIN)), expense, "submit").status_code == 403
    assert act(client, auth(make(Role.APPROVER)), expense, "submit").status_code == 403
    stale = client.post(f"/api/v1/expenses/{expense['id']}/submit", headers={**author, "If-Match": "99"})
    assert (stale.status_code, stale.json()["code"]) == (409, "VERSION_CONFLICT")
    assert client.post(f"/api/v1/expenses/{expense['id']}/submit", headers=author).status_code == 422  # no If-Match


# C5: approving and rejecting -----------------------------------------------------------------------------------------


def submitted_expense(client: TestClient, author: dict[str, str], lookups: Lookups, **overrides: Any) -> dict[str, Any]:
    expense = create(client, author, direct_expense(lookups, **overrides)).json()
    result: dict[str, Any] = act(client, author, expense, "submit").json()
    return result


def test_c5_an_approver_approves_with_or_without_a_comment(
    client: TestClient, make: Make, auth: Auth, lookups: Lookups
) -> None:
    author = auth(make(Role.STAFF))
    approver = make(Role.APPROVER, full_name="Ayesha Siddiqui")
    plain = submitted_expense(client, author, lookups)
    assert plain["actions"] == []
    approved = act(client, auth(approver), plain, "approve")
    assert (approved.status_code, approved.json()["status"]) == (200, "approved")
    commented = submitted_expense(client, author, lookups)
    assert act(client, auth(approver), commented, "approve", comment="Receipt checked").status_code == 200
    history = client.get(f"/api/v1/expenses/{commented['id']}/history", headers=author).json()
    last = history[-1]
    assert (last["action"], last["actor_name"], last["comment"], last["to_status"]) == (
        "approved",
        "Ayesha Siddiqui",
        "Receipt checked",
        "approved",
    )


def test_c5_rejecting_needs_a_comment(client: TestClient, make: Make, auth: Auth, lookups: Lookups) -> None:
    expense = submitted_expense(client, auth(make(Role.STAFF)), lookups)
    approver = auth(make(Role.APPROVER))
    for body in ({}, {"comment": ""}, {"comment": "   \n"}):
        response = client.post(
            f"/api/v1/expenses/{expense['id']}/reject", json=body, headers=with_version(approver, expense)
        )
        assert (response.status_code, response.json()["code"]) == (422, "COMMENT_REQUIRED")
    rejected = act(client, approver, expense, "reject", comment="The receipt is for another month")
    assert (rejected.status_code, rejected.json()["status"]) == (200, "rejected")


def test_c5_staff_and_accountants_cannot_approve_or_reject(
    client: TestClient, make: Make, auth: Auth, lookups: Lookups
) -> None:
    expense = submitted_expense(client, auth(make(Role.STAFF)), lookups)
    for role in (Role.STAFF, Role.ACCOUNTANT):
        headers = auth(make(role))
        assert act(client, headers, expense, "approve").status_code in (403, 404)
        assert act(client, headers, expense, "reject", comment="no").status_code in (403, 404)


def test_c5_a_draft_cannot_be_approved_and_a_decision_is_made_once(
    client: TestClient, make: Make, auth: Auth, lookups: Lookups
) -> None:
    author = auth(make(Role.STAFF))
    approver = auth(make(Role.APPROVER))
    draft = create(client, author, direct_expense(lookups)).json()
    early = act(client, approver, draft, "approve")
    assert (early.status_code, early.json()["code"]) == (409, "INVALID_TRANSITION")
    expense = submitted_expense(client, author, lookups)
    approved = act(client, approver, expense, "approve").json()
    for action, body in (("approve", {}), ("reject", {"comment": "changed my mind"})):
        again = act(client, approver, approved, action, **body)
        assert (again.status_code, again.json()["code"]) == (409, "INVALID_TRANSITION")


def test_a4_nobody_approves_the_expense_they_created(
    client: TestClient, make: Make, auth: Auth, lookups: Lookups
) -> None:
    admin = auth(make(Role.ADMIN))
    own = submitted_expense(client, admin, lookups)
    refused = act(client, admin, own, "approve")
    assert (refused.status_code, refused.json()["code"]) == (403, "SELF_APPROVAL_FORBIDDEN")
    assert "approve" not in own["actions"]
    # Another approver can.
    assert act(client, auth(make(Role.APPROVER)), own, "approve").status_code == 200


# C7: reopening -------------------------------------------------------------------------------------------------------


def test_c7_a_rejected_expense_returns_to_draft_for_its_author_and_the_comment_stays(
    client: TestClient, make: Make, auth: Auth, lookups: Lookups
) -> None:
    author = auth(make(Role.STAFF))
    approver = auth(make(Role.APPROVER))
    expense = submitted_expense(client, author, lookups)
    rejected = act(client, approver, expense, "reject", comment="Wrong category").json()
    assert reload(client, author, rejected)["actions"] == ["reopen"]
    reopened = act(client, author, rejected, "reopen")
    assert (reopened.status_code, reopened.json()["status"]) == (200, "draft")
    fixed = client.patch(
        f"/api/v1/expenses/{expense['id']}",
        json={"category_id": lookups.other_category.id},
        headers=with_version(author, reopened.json()),
    ).json()
    resubmitted = act(client, author, fixed, "submit")
    assert resubmitted.json()["status"] == "submitted"
    history = client.get(f"/api/v1/expenses/{expense['id']}/history", headers=author).json()
    assert [(h["action"], h["comment"]) for h in history] == [
        ("created", None),
        ("submitted", None),
        ("rejected", "Wrong category"),
        ("reopened", None),
        ("submitted", None),
    ]


def test_c7_only_the_author_reopens(client: TestClient, make: Make, auth: Auth, lookups: Lookups) -> None:
    author = auth(make(Role.ACCOUNTANT))
    approver = auth(make(Role.APPROVER))
    expense = submitted_expense(client, author, lookups)
    rejected = act(client, approver, expense, "reject", comment="No").json()
    other = act(client, auth(make(Role.ADMIN)), rejected, "reopen")
    assert (other.status_code, other.json()["code"]) == (403, "FORBIDDEN")
    assert act(client, approver, rejected, "reopen").status_code == 403
    not_rejected = create(client, author, direct_expense(lookups)).json()
    assert act(client, author, not_rejected, "reopen").status_code == 409


# F2: history ---------------------------------------------------------------------------------------------------------


def test_f2_the_history_is_chronological_with_actor_action_comment_and_time(
    client: TestClient, make: Make, auth: Auth, lookups: Lookups, clock: FakeClock
) -> None:
    author = make(Role.STAFF, full_name="Bilal Ahmed")
    approver = make(Role.APPROVER, full_name="Ayesha Siddiqui")
    expense = create(client, auth(author), direct_expense(lookups)).json()
    clock.advance(minutes=5)
    expense = act(client, auth(author), expense, "submit").json()
    clock.advance(minutes=10)
    act(client, auth(approver), expense, "reject", comment="Missing receipt")
    history = client.get(f"/api/v1/expenses/{expense['id']}/history", headers=auth(approver)).json()
    assert [(h["action"], h["actor_name"], h["from_status"], h["to_status"]) for h in history] == [
        ("created", "Bilal Ahmed", None, "draft"),
        ("submitted", "Bilal Ahmed", "draft", "submitted"),
        ("rejected", "Ayesha Siddiqui", "submitted", "rejected"),
    ]
    assert [h["created_at"] for h in history] == [
        "2026-10-12T14:05:00Z",
        "2026-10-12T14:10:00Z",
        "2026-10-12T14:20:00Z",
    ]
    assert history[2]["comment"] == "Missing receipt"
    assert history[0]["document_type"] == "expense"


# A3: visibility ------------------------------------------------------------------------------------------------------


def test_a3_staff_asking_for_another_users_expense_get_a_404_everywhere(
    client: TestClient, make: Make, auth: Auth, lookups: Lookups
) -> None:
    owner = make(Role.STAFF)
    expense = create(client, auth(owner), direct_expense(lookups)).json()
    intruder = auth(make(Role.STAFF))
    base = f"/api/v1/expenses/{expense['id']}"
    for method, path, kwargs in (
        ("GET", base, {}),
        ("GET", f"{base}/history", {}),
        ("GET", f"{base}/attachments", {}),
        ("PATCH", base, {"json": {"description": "mine"}}),
        ("POST", f"{base}/submit", {}),
        ("POST", f"{base}/reopen", {}),
    ):
        response = client.request(method, path, headers={**intruder, "If-Match": "1"}, json=kwargs.get("json"))
        assert (response.status_code, response.json()["code"]) == (404, "NOT_FOUND"), f"{method} {path}"
    assert client.get(base, headers=auth(owner)).status_code == 200


def test_a3_staff_lists_show_only_their_own_and_everyone_else_sees_all(
    client: TestClient, make: Make, auth: Auth, lookups: Lookups
) -> None:
    mine, theirs = make(Role.STAFF), make(Role.STAFF)
    create(client, auth(mine), direct_expense(lookups, description="Mine"))
    create(client, auth(theirs), direct_expense(lookups, description="Theirs"))
    assert [e["description"] for e in client.get("/api/v1/expenses", headers=auth(mine)).json()["items"]] == ["Mine"]
    assert client.get("/api/v1/expenses?mine=false", headers=auth(mine)).json()["total"] == 1
    for role in (Role.ACCOUNTANT, Role.APPROVER, Role.ADMIN):
        assert client.get("/api/v1/expenses", headers=auth(make(role))).json()["total"] == 2
    assert client.get("/api/v1/expenses?mine=true", headers=auth(make(Role.ADMIN))).json()["total"] == 0


# Lists ---------------------------------------------------------------------------------------------------------------


def test_search_works_by_words_in_any_order_and_each_word_narrows_the_list(
    client: TestClient, make: Make, auth: Auth, lookups: Lookups
) -> None:
    headers = auth(make(Role.ADMIN))
    for title in ("Printer toner cartridge", "Paper and ink", "Office tea and ink"):
        create(client, headers, direct_expense(lookups, description=title))

    def found(query: str) -> list[str]:
        response = client.get(f"/api/v1/expenses?q={query}", headers=headers)
        return sorted(e["description"] for e in response.json()["items"])

    assert found("ink") == ["Office tea and ink", "Paper and ink"]
    assert found("ink pap") == ["Paper and ink"]  # one more word narrows it, and part of a word is enough
    assert found("pap%20ink") == ["Paper and ink"]
    assert found("ink%20printer") == []  # every word has to be found
    assert found("CARTRIDGE%20toner") == ["Printer toner cartridge"]  # any order, any case
    assert found("%25") == []  # a percent sign is text, not a wildcard
    everything = ["Office tea and ink", "Paper and ink", "Printer toner cartridge"]
    assert found("%20%20") == everything  # blank is no search


def test_the_expense_list_filters_sorts_and_paginates(
    client: TestClient, make: Make, auth: Auth, lookups: Lookups
) -> None:
    headers = auth(make(Role.ADMIN))
    create(client, headers, direct_expense(lookups, document_date="2026-09-01", amount="100.00", description="Paper"))
    create(client, headers, direct_expense(lookups, document_date="2026-09-15", amount="300.00", description="Ink"))
    third = create(
        client, headers, direct_expense(lookups, document_date="2026-10-01", amount="200.00", description="Toner")
    ).json()
    act(client, headers, third, "submit")
    create(client, headers, indirect_expense(lookups, split(lookups, 10_000), document_date="2026-10-02"))

    def ids(query: str) -> list[str]:
        return [e["description"] for e in client.get(f"/api/v1/expenses?{query}", headers=headers).json()["items"]]

    assert ids("sort=document_date")[:3] == ["Paper", "Ink", "Toner"]
    assert ids("sort=-amount")[:2] == ["Ink", "Toner"]
    assert ids("status=submitted") == ["Toner"]
    assert ids("expense_type=indirect") == ["Shared electricity bill"]
    assert ids("date_from=2026-09-10&date_to=2026-09-30") == ["Ink"]
    assert ids("q=TONER") == ["Toner"]
    assert ids("amount_min=150&amount_max=300&sort=amount") == ["Toner", "Ink"]
    assert ids("amount_min=300&amount_max=300") == ["Ink"]
    assert ids("amount_max=99.99") == []
    assert client.get("/api/v1/expenses?amount_min=-1", headers=headers).status_code == 422
    page = client.get("/api/v1/expenses?sort=document_date&limit=2&offset=1", headers=headers).json()
    assert (page["total"], page["limit"], page["offset"], [e["description"] for e in page["items"]]) == (
        4,
        2,
        1,
        ["Ink", "Toner"],
    )
    assert client.get("/api/v1/expenses?sort=created_by", headers=headers).status_code == 422
    assert client.get("/api/v1/expenses?status=bogus", headers=headers).status_code == 422


# Audit ---------------------------------------------------------------------------------------------------------------


def test_every_change_and_move_is_audited_in_the_same_transaction(
    client: TestClient, make: Make, auth: Auth, lookups: Lookups, db_session: Session
) -> None:
    author, approver = make(Role.STAFF), make(Role.APPROVER)
    expense = create(client, auth(author), direct_expense(lookups)).json()
    edited = client.patch(
        f"/api/v1/expenses/{expense['id']}", json={"amount": "1600.00"}, headers=with_version(auth(author), expense)
    ).json()
    submitted = act(client, auth(author), edited, "submit").json()
    act(client, auth(approver), submitted, "approve", comment="Fine")
    rows = db_session.execute(
        text("SELECT action, actor_id, before, after FROM audit_events WHERE entity_type = 'expense' ORDER BY id")
    ).all()
    assert [r.action for r in rows] == ["expense.created", "expense.updated", "expense.submitted", "expense.approved"]
    assert (rows[1].before["amount"], rows[1].after["amount"]) == ("1500.00", "1600.00")
    assert rows[2].before == {"status": "draft"}
    assert rows[3].after == {"status": "approved", "comment": "Fine"}
    assert rows[3].actor_id == approver.id
