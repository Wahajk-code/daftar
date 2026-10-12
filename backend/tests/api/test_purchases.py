"""Stories D1 (server-side totals), D2 (registered vendor), D3 (unregistered vendor), D4 (same lifecycle)."""

from collections.abc import Callable
from decimal import Decimal
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.enums import Role
from app.models.user import User
from tests.support.documents import Lookups, create_lookups, purchase_body, purchase_line

Make = Callable[..., User]
Auth = Callable[[User], dict[str, str]]


@pytest.fixture
def lookups(db_session: Session, make: Make) -> Lookups:
    return create_lookups(db_session, make(Role.ADMIN))


@pytest.fixture
def accountant(make: Make, auth: Auth) -> dict[str, str]:
    return auth(make(Role.ACCOUNTANT))


def create(client: TestClient, headers: dict[str, str], body: dict[str, Any]) -> Any:
    return client.post("/api/v1/purchases", json=body, headers=headers)


def act(client: TestClient, headers: dict[str, str], purchase: dict[str, Any], action: str, **body: Any) -> Any:
    return client.post(
        f"/api/v1/purchases/{purchase['id']}/{action}",
        json=body or None,
        headers={**headers, "If-Match": str(purchase["version"])},
    )


# D1: server-side totals ----------------------------------------------------------------------------------------------


def test_d1_every_figure_is_computed_on_the_server(
    client: TestClient, accountant: dict[str, str], lookups: Lookups
) -> None:
    line = purchase_line(quantity="3.500", rate="1200.00", sales_tax_bp=1800)
    body = create(client, accountant, purchase_body(lookups.vendors["reg_filer"], [line])).json()
    (priced,) = body["lines"]
    assert (priced["subtotal"], priced["sales_tax"], priced["gross"]) == ("4200.00", "756.00", "4956.00")
    assert (priced["sales_tax_withheld"], priced["income_tax_withheld"], priced["payable"]) == (
        "151.20",
        "223.02",
        "4581.78",
    )
    assert (body["subtotal"], body["sales_tax_total"], body["gross_total"]) == ("4200.00", "756.00", "4956.00")
    assert (body["sales_tax_withheld"], body["income_tax_withheld"], body["payable"]) == ("151.20", "223.02", "4581.78")
    assert body["lines"][0]["quantity"] == "3.500"


def test_d1_the_header_is_the_exact_sum_of_the_lines(
    client: TestClient, accountant: dict[str, str], lookups: Lookups
) -> None:
    lines = [
        purchase_line(item="Cable", category="goods", quantity="3", rate="33.33", sales_tax_bp=1800),
        purchase_line(item="Fitting", category="services", quantity="1.5", rate="66.67", sales_tax_bp=1800),
        purchase_line(item="Haulage", category="contracts", quantity="7", rate="0.35", sales_tax_bp=500),
    ]
    body = create(client, accountant, purchase_body(lookups.vendors["reg_nonfiler"], lines)).json()
    for figure in ("subtotal", "sales_tax", "gross", "sales_tax_withheld", "income_tax_withheld", "payable"):
        header = "sales_tax_total" if figure == "sales_tax" else "gross_total" if figure == "gross" else figure
        assert Decimal(body[header]) == sum(Decimal(line[figure]) for line in body["lines"])
    assert [line["line_no"] for line in body["lines"]] == [1, 2, 3]


@pytest.mark.parametrize(
    "field", ["subtotal", "gross_total", "payable", "sales_tax_withheld", "document_kind", "vendor_registered"]
)
def test_d1_the_client_cannot_supply_any_computed_figure(
    client: TestClient, accountant: dict[str, str], lookups: Lookups, field: str
) -> None:
    body = purchase_body(lookups.vendors["reg_filer"]) | {field: "1.00"}
    assert create(client, accountant, body).status_code == 422
    line = purchase_line() | {"gross": "1.00"}
    assert create(client, accountant, purchase_body(lookups.vendors["reg_filer"], [line])).status_code == 422


@pytest.mark.parametrize(
    "override",
    [
        {"quantity": 2.5},
        {"quantity": "2.5555"},
        {"quantity": "0"},
        {"quantity": "-1"},
        {"rate": "0.00"},
        {"rate": "-5.00"},
        {"rate": 10.5},
        {"rate": "10.005"},
        {"sales_tax_bp": -1},
        {"sales_tax_bp": 10_001},
        {"category": "luxuries"},
        {"item": ""},
        {"quantity": "0.001", "rate": "1.00"},
    ],
)
def test_d1_bad_lines_are_refused(
    client: TestClient, accountant: dict[str, str], lookups: Lookups, override: dict[str, Any]
) -> None:
    response = create(client, accountant, purchase_body(lookups.vendors["reg_filer"], [purchase_line(**override)]))
    assert response.status_code == 422, response.text


def test_d1_a_purchase_needs_at_least_one_line_and_no_more_than_a_hundred(
    client: TestClient, accountant: dict[str, str], lookups: Lookups
) -> None:
    vendor = lookups.vendors["unreg_nonfiler"]
    assert create(client, accountant, purchase_body(vendor, lines=[])).status_code == 422
    body = purchase_body(vendor, [purchase_line(quantity="1", rate="1.00")] * 101)
    assert create(client, accountant, body).status_code == 422


def test_d1_a_total_too_large_to_hold_is_refused(
    client: TestClient, accountant: dict[str, str], lookups: Lookups
) -> None:
    huge = purchase_line(quantity="99999999", rate="99999999.99", sales_tax_bp=0)
    response = create(client, accountant, purchase_body(lookups.vendors["unreg_nonfiler"], [huge]))
    assert response.status_code == 422


def test_d1_the_preview_prices_exactly_as_saving_would_and_saves_nothing(
    client: TestClient, accountant: dict[str, str], lookups: Lookups
) -> None:
    vendor = lookups.vendors["reg_filer"]
    lines = [
        purchase_line(quantity="3.500", rate="1200.00", sales_tax_bp=1800),
        purchase_line(item="Ink", category="services", rate="75.50"),
    ]
    preview = client.post(
        "/api/v1/purchases/preview", json={"vendor_id": vendor.id, "lines": lines}, headers=accountant
    )
    assert preview.status_code == 200
    saved = create(client, accountant, purchase_body(vendor, lines)).json()
    assert preview.json()["lines"] == saved["lines"]
    assert preview.json()["totals"] == {k: saved[k] for k in preview.json()["totals"]}
    assert preview.json()["document_kind"] == saved["document_kind"] == "tax_invoice"
    assert client.get("/api/v1/purchases", headers=accountant).json()["total"] == 1  # only the saved one


# D2: registered vendors ----------------------------------------------------------------------------------------------


def test_d2_a_registered_vendors_purchase_is_a_tax_invoice_with_a_number(
    client: TestClient, accountant: dict[str, str], lookups: Lookups
) -> None:
    vendor = lookups.vendors["reg_filer"]
    body = create(client, accountant, purchase_body(vendor, invoice_number="  INV-77 ")).json()
    assert (body["document_kind"], body["invoice_number"]) == ("tax_invoice", "INV-77")
    assert (body["vendor_registered"], body["vendor_filer"], body["vendor_name"]) == (True, True, "Ravi Stationers")
    no_number = purchase_body(vendor)
    del no_number["invoice_number"]
    refused = create(client, accountant, no_number)
    assert refused.status_code == 422
    assert refused.json()["errors"][0]["field"] == "invoice_number"
    assert create(client, accountant, purchase_body(vendor, invoice_number="   ")).status_code == 422


def test_d2_sales_tax_is_captured_and_both_withholdings_come_from_the_rate_table(
    client: TestClient, accountant: dict[str, str], lookups: Lookups
) -> None:
    line = purchase_line(category="services", quantity="1", rate="10000.00", sales_tax_bp=1800)
    body = create(client, accountant, purchase_body(lookups.vendors["reg_nonfiler"], [line])).json()
    (priced,) = body["lines"]
    assert priced["sales_tax"] == "1800.00"
    assert (priced["sales_withholding_bp"], priced["sales_tax_withheld"]) == (
        2000,
        "360.00",
    )  # a fifth of the sales tax
    assert (priced["income_withholding_bp"], priced["income_tax_withheld"]) == (1800, "2124.00")  # non-filer, services
    assert body["payable"] == "9316.00"
    assert body["sales_tax_withheld"] == "360.00"
    assert body["income_tax_withheld"] == "2124.00"


# D3: unregistered vendors --------------------------------------------------------------------------------------------


def test_d3_an_unregistered_vendors_purchase_is_a_memo_withheld_on_the_gross_value(
    client: TestClient, accountant: dict[str, str], lookups: Lookups
) -> None:
    line = purchase_line(category="services", quantity="1", rate="10000.00")
    body = create(client, accountant, purchase_body(lookups.vendors["unreg_nonfiler"], [line])).json()
    assert (body["document_kind"], body["invoice_number"]) == ("purchase_memo", None)
    (priced,) = body["lines"]
    assert priced["sales_tax"] == "0.00"
    assert (priced["sales_withholding_bp"], priced["sales_tax_withheld"]) == (1800, "1800.00")  # on the gross value
    assert (priced["income_withholding_bp"], priced["income_tax_withheld"]) == (1800, "1800.00")
    assert body["payable"] == "6400.00"


def test_d3_an_unregistered_vendor_cannot_have_charged_sales_tax(
    client: TestClient, accountant: dict[str, str], lookups: Lookups
) -> None:
    response = create(
        client, accountant, purchase_body(lookups.vendors["unreg_filer"], [purchase_line(sales_tax_bp=1800)])
    )
    assert response.status_code == 422


def test_d3_a_memo_may_still_carry_a_reference_number(
    client: TestClient, accountant: dict[str, str], lookups: Lookups
) -> None:
    body = create(
        client, accountant, purchase_body(lookups.vendors["unreg_filer"], invoice_number="CASH-MEMO-9")
    ).json()
    assert (body["document_kind"], body["invoice_number"]) == ("purchase_memo", "CASH-MEMO-9")


# B2 and B5 at work: every vendor combination gets its own rates -----------------------------------------------------


def test_every_vendor_combination_gives_a_different_pair_of_rates(
    client: TestClient, accountant: dict[str, str], lookups: Lookups
) -> None:
    seen: dict[str, tuple[int, int]] = {}
    for key, vendor in lookups.vendors.items():
        body = create(client, accountant, purchase_body(vendor, [purchase_line(category="goods")])).json()
        line = body["lines"][0]
        seen[key] = (line["sales_withholding_bp"], line["income_withholding_bp"])
    assert seen == {
        "reg_filer": (2000, 450),
        "reg_nonfiler": (2000, 900),
        "unreg_filer": (1800, 450),
        "unreg_nonfiler": (1800, 900),
    }
    assert len(set(seen.values())) == 4


def test_the_rate_and_rule_are_copied_onto_the_line_and_later_changes_do_not_touch_it(
    client: TestClient, make: Make, auth: Auth, lookups: Lookups
) -> None:
    accountant, admin = auth(make(Role.ACCOUNTANT)), auth(make(Role.ADMIN))
    vendor = lookups.vendors["reg_filer"]
    saved = create(
        client, accountant, purchase_body(vendor, [purchase_line(category="goods", rate="10000.00", quantity="1")])
    ).json()
    line = saved["lines"][0]
    rule = client.get(f"/api/v1/tax-rules/{line['income_withholding_rule_id']}", headers=admin).json()
    assert rule["rate_bp"] == line["income_withholding_bp"] == 450

    client.patch(
        f"/api/v1/tax-rules/{rule['id']}", json={"rate_bp": 900}, headers={**admin, "If-Match": str(rule["version"])}
    )
    vendor_row = lookups.vendors["reg_filer"]
    vendor_row.is_filer = False
    vendor_row.is_sales_tax_registered = False
    unchanged = client.get(f"/api/v1/purchases/{saved['id']}", headers=accountant).json()
    assert unchanged["lines"] == saved["lines"]
    assert (unchanged["vendor_registered"], unchanged["vendor_filer"]) == (True, True)
    assert unchanged["income_tax_withheld"] == saved["income_tax_withheld"] == "450.00"


def test_a_payment_with_no_withholding_rate_is_refused_with_a_reason(
    client: TestClient, accountant: dict[str, str], lookups: Lookups
) -> None:
    any_category = create(
        client, accountant, purchase_body(lookups.vendors["reg_filer"], [purchase_line(category="any")])
    )
    assert (any_category.status_code, any_category.json()["code"]) == (422, "TAX_RULE_MISSING")
    assert any_category.json()["errors"][0]["field"] == "lines.0.category"
    before_rates = create(client, accountant, purchase_body(lookups.vendors["reg_filer"], document_date="2025-06-30"))
    assert before_rates.json()["code"] == "TAX_RULE_MISSING"


def test_a_negative_payable_is_refused(client: TestClient, make: Make, auth: Auth, lookups: Lookups) -> None:
    admin, accountant = auth(make(Role.ADMIN)), auth(make(Role.ACCOUNTANT))
    rules = client.get("/api/v1/tax-rules?limit=100", headers=admin).json()["items"]
    for rule in rules:
        client.patch(
            f"/api/v1/tax-rules/{rule['id']}",
            json={"rate_bp": 10_000},
            headers={**admin, "If-Match": str(rule["version"])},
        )
    response = create(
        client, accountant, purchase_body(lookups.vendors["reg_filer"], [purchase_line(sales_tax_bp=1800)])
    )
    assert (response.status_code, response.json()["code"]) == (422, "PAYABLE_NEGATIVE")


def test_a_purchase_needs_an_active_vendor(
    client: TestClient, accountant: dict[str, str], lookups: Lookups, db_session: Session
) -> None:
    vendor = lookups.vendors["unreg_nonfiler"]
    vendor.is_active = False
    db_session.commit()
    response = create(client, accountant, purchase_body(vendor))
    assert (response.status_code, response.json()["errors"][0]["field"]) == (422, "vendor_id")
    assert create(client, accountant, purchase_body(vendor) | {"vendor_id": 999_999}).status_code == 422


# Editing a draft -----------------------------------------------------------------------------------------------------


def test_editing_a_draft_prices_it_again(client: TestClient, accountant: dict[str, str], lookups: Lookups) -> None:
    saved = create(
        client, accountant, purchase_body(lookups.vendors["reg_filer"], [purchase_line(rate="1000.00", quantity="1")])
    ).json()
    headers = {**accountant, "If-Match": str(saved["version"])}
    new_lines = [purchase_line(item="Toner", rate="2000.00", quantity="2", sales_tax_bp=1800)]
    edited = client.patch(
        f"/api/v1/purchases/{saved['id']}", json={"lines": new_lines, "description": "Revised"}, headers=headers
    ).json()
    assert (edited["subtotal"], edited["sales_tax_total"], edited["description"]) == ("4000.00", "720.00", "Revised")
    assert edited["version"] > saved["version"]
    assert [line["item"] for line in edited["lines"]] == ["Toner"]


def test_changing_the_vendor_takes_the_new_vendors_flags_and_kind(
    client: TestClient, accountant: dict[str, str], lookups: Lookups
) -> None:
    saved = create(
        client, accountant, purchase_body(lookups.vendors["reg_filer"], [purchase_line(category="goods")])
    ).json()
    headers = {**accountant, "If-Match": str(saved["version"])}
    edited = client.patch(
        f"/api/v1/purchases/{saved['id']}", json={"vendor_id": lookups.vendors["unreg_nonfiler"].id}, headers=headers
    )
    body = edited.json()
    assert (body["document_kind"], body["vendor_registered"], body["vendor_filer"]) == ("purchase_memo", False, False)
    assert (body["lines"][0]["sales_withholding_bp"], body["lines"][0]["income_withholding_bp"]) == (1800, 900)


def test_only_the_author_edits_and_only_while_draft(
    client: TestClient, make: Make, auth: Auth, lookups: Lookups
) -> None:
    author = auth(make(Role.ACCOUNTANT))
    saved = create(client, author, purchase_body(lookups.vendors["unreg_nonfiler"])).json()
    stranger = {**auth(make(Role.ADMIN)), "If-Match": "1"}
    assert (
        client.patch(f"/api/v1/purchases/{saved['id']}", json={"description": "x"}, headers=stranger).status_code == 403
    )
    submitted = act(client, author, saved, "submit").json()
    locked = client.patch(
        f"/api/v1/purchases/{saved['id']}",
        json={"description": "x"},
        headers={**author, "If-Match": str(submitted["version"])},
    )
    assert (locked.status_code, locked.json()["code"]) == (409, "DOCUMENT_LOCKED")


# D4: the same lifecycle ----------------------------------------------------------------------------------------------


def test_d4_a_purchase_goes_through_the_same_steps_as_an_expense(
    client: TestClient, make: Make, auth: Auth, lookups: Lookups
) -> None:
    author, approver = auth(make(Role.ACCOUNTANT)), auth(make(Role.APPROVER))
    saved = create(client, author, purchase_body(lookups.vendors["unreg_nonfiler"])).json()
    assert saved["actions"] == ["submit"]
    submitted = act(client, author, saved, "submit").json()
    assert submitted["status"] == "submitted"
    rejected = act(client, approver, submitted, "reject", comment="Wrong vendor").json()
    assert act(client, approver, submitted, "reject", comment="again").status_code == 409
    reopened = act(client, author, rejected, "reopen").json()
    assert reopened["status"] == "draft"
    resubmitted = act(client, author, reopened, "submit").json()
    approved = act(client, approver, resubmitted, "approve", comment="Good").json()
    assert approved["status"] == "approved"
    history = client.get(f"/api/v1/purchases/{saved['id']}/history", headers=approver).json()
    assert [(h["action"], h["comment"]) for h in history] == [
        ("created", None),
        ("submitted", None),
        ("rejected", "Wrong vendor"),
        ("reopened", None),
        ("submitted", None),
        ("approved", "Good"),
    ]
    assert {h["document_type"] for h in history} == {"purchase"}


def test_d4_rejecting_needs_a_comment_and_nobody_approves_their_own_purchase(
    client: TestClient, make: Make, auth: Auth, lookups: Lookups
) -> None:
    admin = auth(make(Role.ADMIN))
    own = act(
        client, admin, create(client, admin, purchase_body(lookups.vendors["unreg_nonfiler"])).json(), "submit"
    ).json()
    self_approval = act(client, admin, own, "approve")
    assert (self_approval.status_code, self_approval.json()["code"]) == (403, "SELF_APPROVAL_FORBIDDEN")
    blank = client.post(
        f"/api/v1/purchases/{own['id']}/reject",
        json={"comment": " "},
        headers={**auth(make(Role.APPROVER)), "If-Match": str(own["version"])},
    )
    assert blank.json()["code"] == "COMMENT_REQUIRED"


def test_purchases_are_for_the_office_only(client: TestClient, make: Make, auth: Auth, lookups: Lookups) -> None:
    saved = create(client, auth(make(Role.ACCOUNTANT)), purchase_body(lookups.vendors["unreg_nonfiler"])).json()
    staff, approver = auth(make(Role.STAFF)), auth(make(Role.APPROVER))
    for path in ("/api/v1/purchases", f"/api/v1/purchases/{saved['id']}", f"/api/v1/purchases/{saved['id']}/history"):
        assert client.get(path, headers=staff).status_code == 403
        assert client.get(path, headers=approver).status_code == 200
    assert create(client, staff, purchase_body(lookups.vendors["unreg_nonfiler"])).status_code == 403
    assert create(client, approver, purchase_body(lookups.vendors["unreg_nonfiler"])).status_code == 403


def test_the_purchase_list_filters_sorts_and_paginates(
    client: TestClient, accountant: dict[str, str], lookups: Lookups
) -> None:
    registered, unregistered = lookups.vendors["reg_filer"], lookups.vendors["unreg_nonfiler"]
    create(client, accountant, purchase_body(registered, document_date="2026-09-01", description="Paper run"))
    create(client, accountant, purchase_body(unregistered, document_date="2026-09-20", description="Haulage"))
    create(
        client,
        accountant,
        purchase_body(unregistered, document_date="2026-10-02", description="Cartage", invoice_number="MEMO-1"),
    )

    def names(query: str) -> list[str]:
        return [p["description"] for p in client.get(f"/api/v1/purchases?{query}", headers=accountant).json()["items"]]

    assert names("sort=document_date") == ["Paper run", "Haulage", "Cartage"]
    assert names("registered=false&sort=document_date") == ["Haulage", "Cartage"]
    assert names(f"vendor_id={registered.id}") == ["Paper run"]
    assert names("q=memo-1") == ["Cartage"]
    assert names("date_from=2026-09-10&date_to=2026-09-30") == ["Haulage"]
    assert client.get("/api/v1/purchases?limit=1&offset=2&sort=document_date", headers=accountant).json()["total"] == 3
    assert client.get("/api/v1/purchases?sort=vendor_registered", headers=accountant).status_code == 422


def test_purchase_changes_are_audited(
    client: TestClient, make: Make, auth: Auth, lookups: Lookups, db_session: Session
) -> None:
    author = auth(make(Role.ACCOUNTANT))
    saved = create(client, author, purchase_body(lookups.vendors["unreg_nonfiler"])).json()
    client.patch(
        f"/api/v1/purchases/{saved['id']}", json={"description": "Changed"}, headers={**author, "If-Match": "1"}
    )
    actions = [
        r[0]
        for r in db_session.execute(text("SELECT action FROM audit_events WHERE entity_type = 'purchase' ORDER BY id"))
    ]
    assert actions == ["purchase.created", "purchase.updated"]
