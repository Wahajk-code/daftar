"""A draft is its author's work in hand: an approver cannot see it, anywhere, until its author submits it. Admins and
accountants keep their view of drafts."""

from collections.abc import Callable
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.enums import Role
from app.models.user import User
from tests.support.documents import (
    Ledger,
    Lookups,
    create_ledger,
    create_lookups,
    direct_expense,
    purchase_body,
    voucher_body,
)

Make = Callable[..., User]
Auth = Callable[[User], dict[str, str]]


@pytest.fixture
def lookups(db_session: Session, make: Make) -> Lookups:
    return create_lookups(db_session, make(Role.ADMIN, active=False))


@pytest.fixture
def ledger(db_session: Session, make: Make, lookups: Lookups) -> Ledger:
    return create_ledger(db_session, lookups, make(Role.ADMIN, active=False))


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


@pytest.fixture
def drafts(
    client: TestClient, staff: dict[str, str], bookkeeper: dict[str, str], lookups: Lookups, ledger: Ledger
) -> dict[str, dict[str, Any]]:
    expense = client.post("/api/v1/expenses", json=direct_expense(lookups, description="Draft lunch"), headers=staff)
    purchase = client.post(
        "/api/v1/purchases",
        json=purchase_body(lookups.vendors["reg_filer"], description="Draft stock"),
        headers=bookkeeper,
    )
    voucher = client.post("/api/v1/vouchers", json=voucher_body(ledger, description="Draft entry"), headers=bookkeeper)
    made = {"expenses": expense.json(), "purchases": purchase.json(), "vouchers": voucher.json()}
    assert all("id" in doc for doc in made.values()), made
    return made


KINDS = ("expenses", "purchases", "vouchers")


@pytest.mark.parametrize("kind", KINDS)
def test_an_approver_does_not_see_a_draft_in_lists_or_by_its_address(
    client: TestClient, approver: dict[str, str], drafts: dict[str, dict[str, Any]], kind: str
) -> None:
    listed = client.get(f"/api/v1/{kind}", headers=approver).json()
    assert listed["total"] == 0
    asked_for_drafts = client.get(f"/api/v1/{kind}?status=draft", headers=approver).json()
    assert asked_for_drafts["total"] == 0
    doc_id = drafts[kind]["id"]
    for path in ("", "/history"):
        response = client.get(f"/api/v1/{kind}/{doc_id}{path}", headers=approver)
        assert (response.status_code, response.json()["code"]) == (404, "NOT_FOUND")
    if kind != "vouchers":
        assert client.get(f"/api/v1/{kind}/{doc_id}/duplicates", headers=approver).status_code == 404


@pytest.mark.parametrize("kind", KINDS)
def test_admins_and_accountants_still_see_drafts(
    client: TestClient, admin: dict[str, str], bookkeeper: dict[str, str], drafts: dict[str, dict[str, Any]], kind: str
) -> None:
    for headers in (admin, bookkeeper):
        assert client.get(f"/api/v1/{kind}", headers=headers).json()["total"] == 1
        assert client.get(f"/api/v1/{kind}/{drafts[kind]['id']}", headers=headers).status_code == 200


def test_the_document_appears_for_the_approver_once_its_author_submits_it(
    client: TestClient, staff: dict[str, str], approver: dict[str, str], drafts: dict[str, dict[str, Any]]
) -> None:
    expense = drafts["expenses"]
    hidden = client.get(f"/api/v1/expenses/{expense['id']}", headers=approver)
    assert hidden.status_code == 404
    sent = client.post(
        f"/api/v1/expenses/{expense['id']}/submit", headers={**staff, "If-Match": str(expense["version"])}
    )
    assert sent.status_code == 200, sent.text
    assert client.get(f"/api/v1/expenses/{expense['id']}", headers=approver).status_code == 200
    assert [e["description"] for e in client.get("/api/v1/expenses", headers=approver).json()["items"]] == [
        "Draft lunch"
    ]


def test_reports_and_exports_never_count_drafts_for_an_approver(
    client: TestClient, approver: dict[str, str], admin: dict[str, str], drafts: dict[str, dict[str, Any]]
) -> None:
    for path in ("expenses", "purchases"):
        report = client.get(f"/api/v1/reports/{path}?statuses=draft", headers=approver).json()
        assert report["scope"]["statuses"] == []
        assert client.get(f"/api/v1/reports/{path}?statuses=draft", headers=admin).json()["scope"]["statuses"] == [
            "draft"
        ]
    register = client.get("/api/v1/reports/vouchers?statuses=draft", headers=approver).json()
    assert register["total"] == 0
    for path in ("expenses", "purchases"):
        exported = client.get(f"/api/v1/reports/export/{path}?status=draft", headers=approver)
        assert exported.status_code == 200
        assert exported.content.decode("utf-8-sig").strip().count("\n") == 0  # the header row only


def test_the_overview_hides_the_draft_count_from_an_approver(
    client: TestClient, approver: dict[str, str], admin: dict[str, str], drafts: dict[str, dict[str, Any]]
) -> None:
    def draft_counts(headers: dict[str, str]) -> dict[str, int]:
        overview = client.get("/api/v1/reports/overview", headers=headers).json()
        return {
            kind: next(row["count"] for row in overview[f"{kind}_statuses"] if row["status"] == "draft")
            for kind in ("expense", "purchase", "voucher")
        }

    assert draft_counts(approver) == {"expense": 0, "purchase": 0, "voucher": 0}
    assert draft_counts(admin) == {"expense": 1, "purchase": 1, "voucher": 1}
