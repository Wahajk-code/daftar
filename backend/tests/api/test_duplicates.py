"""Duplicate warnings (domain rules section 8): a document that resembles another is flagged, never blocked. Same vendor
and invoice number, about the same amount close in date, or a receipt with identical content."""

from collections.abc import Callable
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.enums import Role
from app.models.user import User
from tests.support.documents import Lookups, create_lookups, direct_expense, image_bytes, purchase_body, purchase_line

Make = Callable[..., User]
Auth = Callable[[User], dict[str, str]]


@pytest.fixture
def lookups(db_session: Session, make: Make) -> Lookups:
    return create_lookups(db_session, make(Role.ADMIN, active=False))


@pytest.fixture
def bookkeeper(make: Make, auth: Auth) -> dict[str, str]:
    return auth(make(Role.ACCOUNTANT))


@pytest.fixture
def approver(make: Make, auth: Auth) -> dict[str, str]:
    return auth(make(Role.APPROVER))


def new_purchase(client: TestClient, headers: dict[str, str], vendor: Any, **overrides: Any) -> dict[str, Any]:
    rate = overrides.pop("rate", "1000.00")
    body = purchase_body(vendor, [purchase_line(rate=rate)], **overrides)
    created: dict[str, Any] = client.post("/api/v1/purchases", json=body, headers=headers).json()
    assert "id" in created, created
    return created


def duplicates_of(client: TestClient, kind: str, headers: dict[str, str], doc: dict[str, Any]) -> list[dict[str, Any]]:
    response = client.get(f"/api/v1/{kind}/{doc['id']}/duplicates", headers=headers)
    assert response.status_code == 200, response.text
    found: list[dict[str, Any]] = response.json()
    return found


def kinds(found: list[dict[str, Any]]) -> list[tuple[str, str, int]]:
    return [(w["kind"], w["document_type"], w["document_id"]) for w in found]


def reject(
    client: TestClient, kind: str, author: dict[str, str], reviewer: dict[str, str], doc: dict[str, Any]
) -> None:
    submitted = client.post(
        f"/api/v1/{kind}/{doc['id']}/submit", headers={**author, "If-Match": str(doc["version"])}
    ).json()
    response = client.post(
        f"/api/v1/{kind}/{doc['id']}/reject",
        json={"comment": "Not right"},
        headers={**reviewer, "If-Match": str(submitted["version"])},
    )
    assert response.status_code == 200


def attach(client: TestClient, kind: str, headers: dict[str, str], doc: dict[str, Any], data: bytes) -> None:
    response = client.post(
        f"/api/v1/{kind}/{doc['id']}/attachments", files={"file": ("receipt.jpg", data, "image/jpeg")}, headers=headers
    )
    assert response.status_code == 201, response.text


# Purchases -----------------------------------------------------------------------------------------------------------


def test_the_same_vendor_and_invoice_number_is_flagged_ignoring_case_and_spaces(
    client: TestClient, bookkeeper: dict[str, str], lookups: Lookups
) -> None:
    vendor = lookups.vendors["reg_filer"]
    first = new_purchase(client, bookkeeper, vendor, invoice_number="INV-77", document_date="2026-01-05")
    second = new_purchase(
        client, bookkeeper, vendor, invoice_number="  inv-77 ", document_date="2026-09-20", rate="50.00"
    )
    found = duplicates_of(client, "purchases", bookkeeper, second)
    assert kinds(found) == [("same_invoice", "purchase", first["id"])]
    assert found[0]["reason"] == f"Purchase {first['id']} from the same vendor already uses invoice number inv-77."
    assert duplicates_of(client, "purchases", bookkeeper, first)[0]["document_id"] == second["id"]  # both ways


def test_the_same_invoice_number_from_another_vendor_is_not_a_duplicate(
    client: TestClient, bookkeeper: dict[str, str], lookups: Lookups
) -> None:
    first = new_purchase(client, bookkeeper, lookups.vendors["reg_filer"], invoice_number="INV-9", rate="10.00")
    second = new_purchase(client, bookkeeper, lookups.vendors["reg_nonfiler"], invoice_number="INV-9", rate="999.00")
    assert duplicates_of(client, "purchases", bookkeeper, second) == []
    assert duplicates_of(client, "purchases", bookkeeper, first) == []


@pytest.mark.parametrize(
    ("rate", "date", "flagged"),
    [
        ("1000.00", "2026-10-12", True),  # identical
        ("1009.00", "2026-10-12", True),  # 0.9 per cent away
        ("1010.00", "2026-10-12", True),  # exactly 1 per cent: inside the limit
        ("1011.00", "2026-10-12", False),  # 1.1 per cent: outside
        ("1000.00", "2026-10-19", True),  # 7 days later
        ("1000.00", "2026-10-05", True),  # 7 days earlier
        ("1000.00", "2026-10-20", False),  # 8 days later
        ("1000.00", "2026-10-04", False),  # 8 days earlier
    ],
)
def test_a_similar_amount_close_in_date_from_the_same_vendor_is_flagged(
    client: TestClient, bookkeeper: dict[str, str], lookups: Lookups, rate: str, date: str, flagged: bool
) -> None:
    vendor = lookups.vendors["unreg_nonfiler"]
    original = new_purchase(client, bookkeeper, vendor, document_date="2026-10-12")
    candidate = new_purchase(client, bookkeeper, vendor, document_date=date, rate=rate)
    found = duplicates_of(client, "purchases", bookkeeper, candidate)
    assert kinds(found) == ([("similar", "purchase", original["id"])] if flagged else [])


def test_a_similar_amount_from_a_different_vendor_is_not_flagged(
    client: TestClient, bookkeeper: dict[str, str], lookups: Lookups
) -> None:
    new_purchase(client, bookkeeper, lookups.vendors["unreg_nonfiler"])
    other = new_purchase(client, bookkeeper, lookups.vendors["unreg_filer"])
    assert duplicates_of(client, "purchases", bookkeeper, other) == []


def test_a_rejected_document_does_not_make_a_new_one_a_duplicate(
    client: TestClient, bookkeeper: dict[str, str], approver: dict[str, str], lookups: Lookups
) -> None:
    vendor = lookups.vendors["unreg_nonfiler"]
    sent_back = new_purchase(client, bookkeeper, vendor)
    reject(client, "purchases", bookkeeper, approver, sent_back)
    again = new_purchase(client, bookkeeper, vendor)
    assert duplicates_of(client, "purchases", bookkeeper, again) == []


def test_a_warning_never_blocks_saving_submitting_or_approving(
    client: TestClient, bookkeeper: dict[str, str], approver: dict[str, str], lookups: Lookups
) -> None:
    vendor = lookups.vendors["reg_filer"]
    new_purchase(client, bookkeeper, vendor, invoice_number="INV-1")
    twin = new_purchase(client, bookkeeper, vendor, invoice_number="INV-1")
    assert duplicates_of(client, "purchases", bookkeeper, twin)
    submitted = client.post(
        f"/api/v1/purchases/{twin['id']}/submit", headers={**bookkeeper, "If-Match": str(twin["version"])}
    )
    assert submitted.status_code == 200
    approved = client.post(
        f"/api/v1/purchases/{twin['id']}/approve", headers={**approver, "If-Match": str(submitted.json()["version"])}
    )
    assert approved.status_code == 200
    assert approved.json()["status"] == "approved"


def test_staff_cannot_ask_about_purchases(
    client: TestClient, make: Make, auth: Auth, bookkeeper: dict[str, str], lookups: Lookups
) -> None:
    purchase = new_purchase(client, bookkeeper, lookups.vendors["unreg_nonfiler"])
    response = client.get(f"/api/v1/purchases/{purchase['id']}/duplicates", headers=auth(make(Role.STAFF)))
    assert response.status_code == 403


# Receipts ------------------------------------------------------------------------------------------------------------


def test_an_identical_receipt_on_a_purchase_and_an_expense_is_flagged_both_ways(
    client: TestClient, make: Make, auth: Auth, bookkeeper: dict[str, str], lookups: Lookups
) -> None:
    photo = image_bytes("JPEG", (80, 60))
    purchase = new_purchase(client, bookkeeper, lookups.vendors["unreg_nonfiler"])
    attach(client, "purchases", bookkeeper, purchase, photo)
    expense = client.post("/api/v1/expenses", json=direct_expense(lookups), headers=bookkeeper).json()
    attach(client, "expenses", bookkeeper, expense, photo)
    assert ("same_receipt", "expense", expense["id"]) in kinds(duplicates_of(client, "purchases", bookkeeper, purchase))
    assert kinds(duplicates_of(client, "expenses", bookkeeper, expense)) == [
        ("same_receipt", "purchase", purchase["id"])
    ]


def test_a_different_receipt_is_not_a_duplicate(
    client: TestClient, bookkeeper: dict[str, str], lookups: Lookups
) -> None:
    first = client.post("/api/v1/expenses", json=direct_expense(lookups, amount="10.00"), headers=bookkeeper).json()
    second = client.post("/api/v1/expenses", json=direct_expense(lookups, amount="9000.00"), headers=bookkeeper).json()
    attach(client, "expenses", bookkeeper, first, image_bytes("JPEG", (80, 60)))
    attach(client, "expenses", bookkeeper, second, image_bytes("JPEG", (90, 70)))
    assert duplicates_of(client, "expenses", bookkeeper, second) == []


# Expenses ------------------------------------------------------------------------------------------------------------


def test_the_same_author_category_and_amount_close_in_date_is_flagged(
    client: TestClient, make: Make, auth: Auth, lookups: Lookups
) -> None:
    author = auth(make(Role.STAFF))
    first = client.post(
        "/api/v1/expenses", json=direct_expense(lookups, document_date="2026-10-10"), headers=author
    ).json()
    second = client.post(
        "/api/v1/expenses", json=direct_expense(lookups, document_date="2026-10-12"), headers=author
    ).json()
    assert kinds(duplicates_of(client, "expenses", author, second)) == [("similar", "expense", first["id"])]


def test_another_authors_similar_expense_is_not_a_duplicate(
    client: TestClient, make: Make, auth: Auth, lookups: Lookups
) -> None:
    mine, theirs = auth(make(Role.STAFF)), auth(make(Role.STAFF))
    client.post("/api/v1/expenses", json=direct_expense(lookups), headers=theirs)
    expense = client.post("/api/v1/expenses", json=direct_expense(lookups), headers=mine).json()
    assert duplicates_of(client, "expenses", mine, expense) == []


def test_staff_are_never_told_about_documents_they_cannot_see(
    client: TestClient, make: Make, auth: Auth, bookkeeper: dict[str, str], lookups: Lookups
) -> None:
    """An identical receipt on someone else's expense, or on a purchase, is for the office to know, not for Staff."""
    photo = image_bytes("JPEG", (77, 55))
    staff = auth(make(Role.STAFF))
    mine = client.post("/api/v1/expenses", json=direct_expense(lookups), headers=staff).json()
    attach(client, "expenses", staff, mine, photo)
    theirs = client.post("/api/v1/expenses", json=direct_expense(lookups, amount="42.00"), headers=bookkeeper).json()
    attach(client, "expenses", bookkeeper, theirs, photo)
    purchase = new_purchase(client, bookkeeper, lookups.vendors["unreg_nonfiler"])
    attach(client, "purchases", bookkeeper, purchase, photo)
    assert duplicates_of(client, "expenses", staff, mine) == []
    office = kinds(duplicates_of(client, "expenses", bookkeeper, mine))
    assert ("same_receipt", "expense", theirs["id"]) in office
    assert ("same_receipt", "purchase", purchase["id"]) in office


def test_staff_cannot_ask_about_an_expense_that_is_not_theirs(
    client: TestClient, make: Make, auth: Auth, bookkeeper: dict[str, str], lookups: Lookups
) -> None:
    theirs = client.post("/api/v1/expenses", json=direct_expense(lookups), headers=bookkeeper).json()
    response = client.get(f"/api/v1/expenses/{theirs['id']}/duplicates", headers=auth(make(Role.STAFF)))
    assert response.status_code == 404
