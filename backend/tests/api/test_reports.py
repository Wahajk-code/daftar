"""Reports (expenses by type and cost centre, purchases by vendor, the voucher register) and their CSV downloads:
who may read them, what they add up to, and that every export is limited, neutralised and audited."""

import csv
import io
from collections.abc import Callable
from decimal import Decimal
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.enums import Role
from app.models.user import User
from app.models.vendor import Vendor
from tests.support.documents import (
    Ledger,
    Lookups,
    create_ledger,
    create_lookups,
    direct_expense,
    indirect_expense,
    purchase_body,
    purchase_line,
    voucher_body,
)

Make = Callable[..., User]
Auth = Callable[[User], dict[str, str]]
D = Decimal


@pytest.fixture
def lookups(db_session: Session, make: Make) -> Lookups:
    return create_lookups(db_session, make(Role.ADMIN, active=False))


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


def approve(
    client: TestClient, kind: str, author: dict[str, str], reviewer: dict[str, str], doc: dict[str, Any]
) -> dict[str, Any]:
    submitted = client.post(f"/api/v1/{kind}/{doc['id']}/submit", headers=v(author, doc)).json()
    result: dict[str, Any] = client.post(f"/api/v1/{kind}/{doc['id']}/approve", headers=v(reviewer, submitted)).json()
    assert result["status"] == "approved", result
    return result


def add_expense(
    client: TestClient, author: dict[str, str], reviewer: dict[str, str] | None, body: dict[str, Any]
) -> dict[str, Any]:
    created: dict[str, Any] = client.post("/api/v1/expenses", json=body, headers=author).json()
    assert "id" in created, created
    return approve(client, "expenses", author, reviewer, created) if reviewer else created


def rows_of(response: Any) -> list[list[str]]:
    assert response.status_code == 200, response.text
    return list(csv.reader(io.StringIO(response.content.decode("utf-8-sig"))))


# Expenses by type and cost centre ------------------------------------------------------------------------------------


@pytest.fixture
def spending(
    client: TestClient, staff: dict[str, str], approver: dict[str, str], lookups: Lookups
) -> dict[str, dict[str, Any]]:
    head, ops, it = (c.id for c in lookups.centres)
    split = [
        {"cost_center_id": head, "basis_points": 3333},
        {"cost_center_id": ops, "basis_points": 3333},
        {"cost_center_id": it, "basis_points": 3334},
    ]
    return {
        "rent": add_expense(client, staff, approver, direct_expense(lookups, amount="1500.00", tax_amount="100.00")),
        "september": add_expense(
            client, staff, approver, direct_expense(lookups, amount="500.00", document_date="2026-09-15")
        ),
        "shared": add_expense(client, staff, approver, indirect_expense(lookups, split)),
        "project": add_expense(
            client,
            staff,
            approver,
            direct_expense(lookups, amount="200.00", cost_center_id=None, project_id=lookups.project.id),
        ),
        "draft": add_expense(client, staff, None, direct_expense(lookups, amount="9999.00")),
    }


def test_g1_the_expense_report_groups_by_type_and_cost_centre_and_counts_each_expense_once(
    client: TestClient, bookkeeper: dict[str, str], spending: dict[str, dict[str, Any]], lookups: Lookups
) -> None:
    report = client.get("/api/v1/reports/expenses", headers=bookkeeper).json()
    found = {(r["expense_type"], r["cost_center_code"]): (r["expenses"], r["amount"]) for r in report["rows"]}
    assert found == {
        ("direct", "HO"): (2, "2000.00"),
        ("direct", None): (1, "200.00"),
        ("indirect", "HO"): (1, "33.33"),
        ("indirect", "OPS"): (1, "33.33"),
        ("indirect", "IT"): (1, "33.34"),
    }
    # The draft is not counted; the shared expense is counted once even though it shows under three cost centres.
    assert report["totals"] == {"expenses": 4, "amount": "2300.00", "tax_amount": "100.00"}
    assert report["scope"]["statuses"] == ["approved", "posted"]


def test_g1_the_rows_of_an_indirect_expense_add_up_to_its_amount(
    client: TestClient, bookkeeper: dict[str, str], spending: dict[str, dict[str, Any]]
) -> None:
    report = client.get("/api/v1/reports/expenses", headers=bookkeeper).json()
    indirect = sum(D(r["amount"]) for r in report["rows"] if r["expense_type"] == "indirect")
    assert indirect == D(spending["shared"]["amount"])


def test_g1_the_expense_report_filters_by_date_and_status(
    client: TestClient, bookkeeper: dict[str, str], spending: dict[str, dict[str, Any]]
) -> None:
    october = client.get(
        "/api/v1/reports/expenses", params={"date_from": "2026-10-01", "date_to": "2026-10-31"}, headers=bookkeeper
    ).json()
    assert october["totals"]["expenses"] == 3  # the September one is out
    only_september = client.get("/api/v1/reports/expenses", params={"date_to": "2026-09-30"}, headers=bookkeeper).json()
    assert (only_september["totals"]["expenses"], only_september["totals"]["amount"]) == (1, "500.00")
    drafts = client.get("/api/v1/reports/expenses", params={"statuses": "draft"}, headers=bookkeeper).json()
    assert (drafts["totals"]["expenses"], drafts["totals"]["amount"]) == (1, "9999.00")


def test_g1_a_backwards_date_range_is_refused(client: TestClient, bookkeeper: dict[str, str]) -> None:
    response = client.get(
        "/api/v1/reports/expenses", params={"date_from": "2026-10-31", "date_to": "2026-10-01"}, headers=bookkeeper
    )
    assert response.status_code == 422
    assert response.json()["errors"][0]["field"] == "date_from"


def test_g1_an_empty_report_is_empty_not_an_error(client: TestClient, bookkeeper: dict[str, str]) -> None:
    report = client.get("/api/v1/reports/expenses", headers=bookkeeper).json()
    assert report["rows"] == []
    assert report["totals"] == {"expenses": 0, "amount": "0.00", "tax_amount": "0.00"}


# The overview behind the home screen's charts -----------------------------------------------------------------------


def test_the_overview_gives_a_zero_filled_run_of_months_and_the_spread_over_statuses(
    client: TestClient, bookkeeper: dict[str, str], spending: dict[str, dict[str, Any]]
) -> None:
    overview = client.get("/api/v1/reports/overview?months=3", headers=bookkeeper).json()
    months = {m["month"]: m for m in overview["months"]}
    # Oldest first, ending with the current month (the fake clock says 12 October 2026); a month with nothing is zero.
    assert [m["month"] for m in overview["months"]] == ["2026-08", "2026-09", "2026-10"]
    assert months["2026-08"] == {
        "month": "2026-08",
        "expenses": "0.00",
        "purchases": "0.00",
        "expense_count": 0,
        "purchase_count": 0,
    }
    assert (months["2026-09"]["expenses"], months["2026-09"]["expense_count"]) == ("500.00", 1)
    # Rent, the shared bill and the project expense; the draft is not decided money.
    assert (months["2026-10"]["expenses"], months["2026-10"]["expense_count"]) == ("1800.00", 3)
    spread = {row["status"]: row["count"] for row in overview["expense_statuses"]}
    assert spread == {"draft": 1, "submitted": 0, "approved": 4, "rejected": 0, "posted": 0, "void": 0}
    assert [row["status"] for row in overview["voucher_statuses"]] == [
        "draft",
        "submitted",
        "approved",
        "rejected",
        "posted",
        "void",
    ]


def test_the_overview_counts_purchases_at_their_gross_amount(
    client: TestClient, bookkeeper: dict[str, str], approver: dict[str, str], lookups: Lookups
) -> None:
    vendor = lookups.vendors["reg_filer"]
    saved = client.post(
        "/api/v1/purchases", json=purchase_body(vendor, document_date="2026-10-02"), headers=bookkeeper
    ).json()
    approve(client, "purchases", bookkeeper, approver, saved)
    overview = client.get("/api/v1/reports/overview", headers=bookkeeper).json()
    assert len(overview["months"]) == 6
    current = overview["months"][-1]
    assert (current["month"], current["purchase_count"], current["purchases"]) == ("2026-10", 1, saved["gross_total"])


def test_the_overview_is_for_the_office_and_months_are_bounded(
    client: TestClient, staff: dict[str, str], bookkeeper: dict[str, str]
) -> None:
    response = client.get("/api/v1/reports/overview", headers=staff)
    assert (response.status_code, response.json()["code"]) == (403, "FORBIDDEN")
    assert client.get("/api/v1/reports/overview?months=0", headers=bookkeeper).status_code == 422
    assert client.get("/api/v1/reports/overview?months=13", headers=bookkeeper).status_code == 422


# Purchases by vendor -------------------------------------------------------------------------------------------------


def test_g2_the_purchase_report_splits_registered_and_unregistered_vendors_and_matches_the_documents(
    client: TestClient, bookkeeper: dict[str, str], approver: dict[str, str], lookups: Lookups
) -> None:
    made = [
        approve(
            client,
            "purchases",
            bookkeeper,
            approver,
            client.post("/api/v1/purchases", json=body, headers=bookkeeper).json(),
        )
        for body in (
            purchase_body(
                lookups.vendors["reg_filer"], [purchase_line(quantity="3.500", rate="1200.00", sales_tax_bp=1800)]
            ),
            purchase_body(lookups.vendors["reg_filer"], [purchase_line(rate="250.00")], invoice_number="INV-2"),
            purchase_body(lookups.vendors["unreg_nonfiler"], [purchase_line(category="services")]),
        )
    ]
    report = client.get("/api/v1/reports/purchases", headers=bookkeeper).json()
    by_vendor = {r["vendor_name"]: r for r in report["rows"]}
    assert set(by_vendor) == {"Ravi Stationers", "Haji Noor Transport"}
    assert by_vendor["Ravi Stationers"]["purchases"] == 2
    assert by_vendor["Ravi Stationers"]["registered"] is True
    assert by_vendor["Haji Noor Transport"]["registered"] is False
    for key, source in (
        ("subtotal", "subtotal"),
        ("sales_tax", "sales_tax_total"),
        ("gross", "gross_total"),
        ("payable", "payable"),
        ("sales_tax_withheld", "sales_tax_withheld"),
        ("income_tax_withheld", "income_tax_withheld"),
    ):
        assert D(report["totals"][key]) == sum(D(p[source]) for p in made), key
        assert D(report["registered"][key]) == sum(D(p[source]) for p in made[:2]), key
        assert D(report["unregistered"][key]) == D(made[2][source]), key
    assert report["registered"]["purchases"] == 2
    assert report["unregistered"]["purchases"] == 1
    assert [r["registered"] for r in report["rows"]] == [True, False]  # registered vendors first


def test_g2_the_purchase_report_can_be_limited_to_one_kind_of_vendor(
    client: TestClient, bookkeeper: dict[str, str], approver: dict[str, str], lookups: Lookups
) -> None:
    for vendor in ("reg_filer", "unreg_filer"):
        created = client.post(
            "/api/v1/purchases", json=purchase_body(lookups.vendors[vendor]), headers=bookkeeper
        ).json()
        approve(client, "purchases", bookkeeper, approver, created)
    only = client.get("/api/v1/reports/purchases", params={"registered": "false"}, headers=bookkeeper).json()
    assert [r["vendor_name"] for r in only["rows"]] == ["Al-Madina Printers"]
    assert only["registered"]["purchases"] == 0


# The voucher register ------------------------------------------------------------------------------------------------


@pytest.fixture
def register(
    client: TestClient,
    bookkeeper: dict[str, str],
    approver: dict[str, str],
    admin: dict[str, str],
    lookups: Lookups,
    db_session: Session,
    make: Make,
) -> dict[str, dict[str, Any]]:
    ledger: Ledger = create_ledger(db_session, lookups, make(Role.ADMIN, active=False))
    made: dict[str, dict[str, Any]] = {}
    for name, amount in (("first", "100.00"), ("second", "250.00")):
        voucher = client.post("/api/v1/vouchers", json=voucher_body(ledger, amount), headers=bookkeeper).json()
        approved = approve(client, "vouchers", bookkeeper, approver, voucher)
        made[name] = client.post(
            f"/api/v1/vouchers/{voucher['id']}/post",
            headers=v(bookkeeper, approved, **{"Idempotency-Key": f"register-{name}-1"}),
        ).json()
    client.post(
        "/api/v1/vouchers", json=voucher_body(ledger, "999.00"), headers=bookkeeper
    )  # a draft: not on the register
    voided = client.post(
        f"/api/v1/vouchers/{made['first']['id']}/void",
        json={"reason": "Entered twice"},
        headers=v(admin, made["first"], **{"Idempotency-Key": "register-void-first"}),
    )
    assert voided.status_code == 200, voided.text
    return made


def test_g3_the_register_lists_numbered_vouchers_in_order_with_a_void_beside_its_reversal(
    client: TestClient, approver: dict[str, str], register: dict[str, dict[str, Any]]
) -> None:
    page = client.get("/api/v1/reports/vouchers", headers=approver).json()
    assert page["total"] == 3
    assert [(r["number"][-4:], r["status"], r["total"], r["reversal_of_number"]) for r in page["items"]] == [
        ("0001", "void", "100.00", None),
        ("0002", "posted", "250.00", None),
        ("0003", "posted", "100.00", register["first"]["number"]),
    ]


def test_g3_the_register_pages_and_filters(
    client: TestClient, approver: dict[str, str], register: dict[str, dict[str, Any]]
) -> None:
    second_page = client.get("/api/v1/reports/vouchers", params={"limit": 2, "offset": 2}, headers=approver).json()
    assert (second_page["total"], len(second_page["items"])) == (3, 1)
    only_void = client.get("/api/v1/reports/vouchers", params={"statuses": "void"}, headers=approver).json()
    assert only_void["total"] == 1
    receipts = client.get("/api/v1/reports/vouchers", params={"voucher_type": "RV"}, headers=approver).json()
    assert receipts["total"] == 0


# Who may read, and the CSV rules -------------------------------------------------------------------------------------


@pytest.mark.parametrize("path", ["expenses", "purchases", "vouchers"])
def test_g1_staff_see_no_reports_and_no_exports(client: TestClient, staff: dict[str, str], path: str) -> None:
    for url in (f"/api/v1/reports/{path}", f"/api/v1/reports/{path}/csv"):
        response = client.get(url, headers=staff)
        assert (response.status_code, response.json()["code"]) == (403, "FORBIDDEN")


@pytest.mark.parametrize("role", [Role.ADMIN, Role.ACCOUNTANT, Role.APPROVER])
def test_g1_the_office_roles_can_read_and_export(client: TestClient, make: Make, auth: Auth, role: Role) -> None:
    headers = auth(make(role))
    for path in ("expenses", "purchases", "vouchers"):
        assert client.get(f"/api/v1/reports/{path}", headers=headers).status_code == 200
        assert client.get(f"/api/v1/reports/{path}/csv", headers=headers).status_code == 200


def test_g4_the_expense_csv_has_a_byte_order_mark_a_filename_and_plain_amounts(
    client: TestClient, bookkeeper: dict[str, str], spending: dict[str, dict[str, Any]]
) -> None:
    response = client.get("/api/v1/reports/expenses/csv", headers=bookkeeper)
    assert response.headers["content-type"].startswith("text/csv")
    assert response.headers["content-disposition"] == 'attachment; filename="daftar-expenses-2026-10-12.csv"'
    assert response.headers["cache-control"] == "no-store"
    assert response.content.startswith(b"\xef\xbb\xbf")
    rows = rows_of(response)
    assert rows[0] == ["Type", "Cost centre code", "Cost centre", "Expenses", "Amount"]
    assert ["direct", "HO", "Head Office", "2", "2000.00"] in rows
    assert ["direct", "", "", "1", "200.00"] in rows
    assert all("," not in cell for row in rows[1:] for cell in row[-1:])  # no thousands separators


def test_g4_a_vendor_name_that_looks_like_a_formula_is_neutralised_in_the_csv(
    client: TestClient, bookkeeper: dict[str, str], approver: dict[str, str], lookups: Lookups, db_session: Session
) -> None:
    sneaky = Vendor(
        name='=HYPERLINK("http://evil.test","pay")',
        is_sales_tax_registered=False,
        is_filer=True,
        created_by=lookups.vendors["reg_filer"].created_by,
    )
    db_session.add(sneaky)
    db_session.commit()
    created = client.post("/api/v1/purchases", json=purchase_body(sneaky), headers=bookkeeper).json()
    approve(client, "purchases", bookkeeper, approver, created)
    rows = rows_of(client.get("/api/v1/reports/purchases/csv", headers=bookkeeper))
    assert rows[1][0] == '\'=HYPERLINK("http://evil.test","pay")'
    assert rows[1][1] == "unregistered"


def test_g4_the_voucher_register_csv_follows_the_register(
    client: TestClient, approver: dict[str, str], register: dict[str, dict[str, Any]]
) -> None:
    rows = rows_of(client.get("/api/v1/reports/vouchers/csv", headers=approver))
    assert rows[0][:6] == ["Number", "Type", "Date", "Status", "Narration", "Total"]
    assert [(r[0][-4:], r[3], r[5], r[8]) for r in rows[1:]] == [
        ("0001", "void", "100.00", ""),
        ("0002", "posted", "250.00", ""),
        ("0003", "posted", "100.00", register["first"]["number"]),
    ]
    assert rows[1][2] == "2026-10-12"


def test_g4_every_export_is_audited_with_its_filter_and_row_count(
    client: TestClient, make: Make, auth: Auth, spending: dict[str, dict[str, Any]], db_session: Session
) -> None:
    user = make(Role.ACCOUNTANT)
    client.get(
        "/api/v1/reports/expenses/csv",
        params={"date_from": "2026-10-01", "date_to": "2026-10-31", "statuses": ["approved"]},
        headers=auth(user),
    )
    row = db_session.execute(
        text("SELECT actor_id, entity_type, after FROM audit_events WHERE action = 'report.exported'")
    ).one()
    assert row.actor_id == user.id
    assert row.entity_type == "report"
    assert row.after == {
        "report": "expenses",
        "date_from": "2026-10-01",
        "date_to": "2026-10-31",
        "statuses": ["approved"],
        "rows": 5,
    }


def test_g4_reading_a_report_on_screen_is_not_an_export_and_is_not_limited(
    client: TestClient, bookkeeper: dict[str, str], db_session: Session
) -> None:
    for _ in range(15):
        assert client.get("/api/v1/reports/expenses", headers=bookkeeper).status_code == 200
    assert (
        db_session.execute(text("SELECT count(*) FROM audit_events WHERE action = 'report.exported'")).scalar_one() == 0
    )


def test_g4_exports_are_limited_per_user_and_the_limit_is_not_shared(
    client: TestClient, make: Make, auth: Auth, db_session: Session
) -> None:
    first, second = auth(make(Role.ACCOUNTANT)), auth(make(Role.APPROVER))
    for _ in range(10):
        assert client.get("/api/v1/reports/expenses/csv", headers=first).status_code == 200
    blocked = client.get("/api/v1/reports/expenses/csv", headers=first)
    assert blocked.status_code == 429
    assert "Retry-After" in blocked.headers
    assert client.get("/api/v1/reports/expenses/csv", headers=second).status_code == 200
    audited = db_session.execute(
        text("SELECT count(*) FROM audit_events WHERE action = 'report.exported'")
    ).scalar_one()
    assert audited == 11  # a refused export leaves no audit row: nothing was exported


def test_g4_a_bad_filter_does_not_use_up_an_export_or_leave_an_audit_row(
    client: TestClient, bookkeeper: dict[str, str], db_session: Session
) -> None:
    response = client.get(
        "/api/v1/reports/expenses/csv", params={"date_from": "2026-10-31", "date_to": "2026-10-01"}, headers=bookkeeper
    )
    assert response.status_code == 422
    assert (
        db_session.execute(text("SELECT count(*) FROM audit_events WHERE action = 'report.exported'")).scalar_one() == 0
    )
