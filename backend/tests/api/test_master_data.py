"""Stories B3 (chart of accounts), B4 (cost centres, projects, categories) and B5 (dated tax rules), plus periods
and posting accounts."""

from collections.abc import Callable
from datetime import date
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.enums import Role
from app.models.user import User
from app.repositories import master as master_repository
from tests.support.database import settle_constraints

Make = Callable[..., User]
Auth = Callable[[User], dict[str, str]]


def versioned(headers: dict[str, str], version: int) -> dict[str, str]:
    return {**headers, "If-Match": str(version)}


def account(
    client: TestClient, headers: dict[str, str], code: str, name: str, type_: str, **extra: Any
) -> dict[str, Any]:
    response = client.post(
        "/api/v1/accounts", json={"code": code, "name": name, "type": type_, **extra}, headers=headers
    )
    assert response.status_code == 201, response.text
    body: dict[str, Any] = response.json()
    return body


@pytest.fixture
def accountant_headers(make: Make, auth: Auth) -> dict[str, str]:
    return auth(make(Role.ACCOUNTANT))


@pytest.fixture
def admin_headers(make: Make, auth: Auth) -> dict[str, str]:
    return auth(make(Role.ADMIN))


# Chart of accounts (B3) ----------------------------------------------------------------------------------------------


def test_b3_a_child_makes_its_parent_unpostable(client: TestClient, accountant_headers: dict[str, str]) -> None:
    parent = account(client, accountant_headers, "1000", "Assets", "asset")
    assert parent["is_postable"] is True
    child = account(client, accountant_headers, "1100", "Cash in Hand", "asset", parent_id=parent["id"])
    assert child["is_postable"] is True
    refreshed = client.get(f"/api/v1/accounts/{parent['id']}", headers=accountant_headers).json()
    assert refreshed["is_postable"] is False
    assert refreshed["version"] == parent["version"] + 1


def test_b3_a_child_has_the_type_of_its_parent_and_an_active_parent(
    client: TestClient, accountant_headers: dict[str, str]
) -> None:
    parent = account(client, accountant_headers, "2000", "Liabilities", "liability")
    wrong_type = client.post(
        "/api/v1/accounts",
        json={"code": "2100", "name": "Payable", "type": "asset", "parent_id": parent["id"]},
        headers=accountant_headers,
    )
    assert wrong_type.status_code == 422
    assert wrong_type.json()["errors"][0]["field"] == "type"
    client.post(f"/api/v1/accounts/{parent['id']}/deactivate", headers=accountant_headers)
    inactive = client.post(
        "/api/v1/accounts",
        json={"code": "2100", "name": "Payable", "type": "liability", "parent_id": parent["id"]},
        headers=accountant_headers,
    )
    assert inactive.json()["errors"][0]["field"] == "parent_id"
    missing = client.post(
        "/api/v1/accounts",
        json={"code": "2100", "name": "Payable", "type": "liability", "parent_id": 99999},
        headers=accountant_headers,
    )
    assert missing.status_code == 422


def test_b3_codes_are_unique_and_tidy(client: TestClient, accountant_headers: dict[str, str]) -> None:
    account(client, accountant_headers, "5a00", "Rent", "expense")
    clash = client.post(
        "/api/v1/accounts", json={"code": "5A00", "name": "Rent again", "type": "expense"}, headers=accountant_headers
    )
    assert (clash.status_code, clash.json()["code"]) == (409, "DUPLICATE_VALUE")
    assert clash.json()["errors"][0]["field"] == "code"
    for bad in ("", "has space", "x" * 21, "a/b"):
        response = client.post(
            "/api/v1/accounts", json={"code": bad, "name": "X", "type": "asset"}, headers=accountant_headers
        )
        assert response.status_code == 422


def test_b3_an_account_with_sub_accounts_cannot_be_made_postable_again(
    client: TestClient, accountant_headers: dict[str, str]
) -> None:
    parent = account(client, accountant_headers, "1000", "Assets", "asset")
    account(client, accountant_headers, "1100", "Cash", "asset", parent_id=parent["id"])
    current = client.get(f"/api/v1/accounts/{parent['id']}", headers=accountant_headers).json()
    refused = client.patch(
        f"/api/v1/accounts/{parent['id']}",
        json={"is_postable": True},
        headers=versioned(accountant_headers, current["version"]),
    )
    assert (refused.status_code, refused.json()["code"]) == (422, "ACCOUNT_NOT_POSTABLE")


def test_b3_renaming_needs_the_current_version(client: TestClient, accountant_headers: dict[str, str]) -> None:
    created = account(client, accountant_headers, "5100", "Rent", "expense")
    renamed = client.patch(
        f"/api/v1/accounts/{created['id']}", json={"name": "  Office   Rent "}, headers=versioned(accountant_headers, 1)
    )
    assert (renamed.json()["name"], renamed.json()["version"]) == ("Office Rent", 2)
    stale = client.patch(
        f"/api/v1/accounts/{created['id']}", json={"name": "Again"}, headers=versioned(accountant_headers, 1)
    )
    assert stale.status_code == 409
    assert (
        client.patch(
            f"/api/v1/accounts/{created['id']}", json={"type": "asset"}, headers=versioned(accountant_headers, 2)
        ).status_code
        == 422
    )  # the type cannot change


def test_b3_a_parent_with_active_sub_accounts_cannot_be_deactivated_until_they_are(
    client: TestClient, accountant_headers: dict[str, str]
) -> None:
    parent = account(client, accountant_headers, "1000", "Assets", "asset")
    child = account(client, accountant_headers, "1100", "Cash", "asset", parent_id=parent["id"])
    assert client.post(f"/api/v1/accounts/{parent['id']}/deactivate", headers=accountant_headers).status_code == 409
    assert client.post(f"/api/v1/accounts/{child['id']}/deactivate", headers=accountant_headers).status_code == 200
    assert client.post(f"/api/v1/accounts/{parent['id']}/deactivate", headers=accountant_headers).status_code == 200
    # Inactive accounts stay readable, so old documents still show them.
    assert client.get(f"/api/v1/accounts/{child['id']}", headers=accountant_headers).json()["is_active"] is False


def test_b3_the_list_filters(client: TestClient, accountant_headers: dict[str, str]) -> None:
    assets = account(client, accountant_headers, "1000", "Assets", "asset")
    account(client, accountant_headers, "1100", "Cash in Hand", "asset", parent_id=assets["id"])
    account(client, accountant_headers, "5100", "Rent", "expense")
    listing = client.get("/api/v1/accounts?sort=code", headers=accountant_headers).json()
    assert [a["code"] for a in listing["items"]] == ["1000", "1100", "5100"]
    assert client.get("/api/v1/accounts?type=expense", headers=accountant_headers).json()["total"] == 1
    assert client.get(f"/api/v1/accounts?parent_id={assets['id']}", headers=accountant_headers).json()["total"] == 1
    assert client.get("/api/v1/accounts?is_postable=false", headers=accountant_headers).json()["total"] == 1
    assert client.get("/api/v1/accounts?q=cash", headers=accountant_headers).json()["total"] == 1
    assert client.get("/api/v1/accounts?type=banana", headers=accountant_headers).status_code == 422


def test_b3_the_database_refuses_a_postable_parent_by_any_route(db_session: Session, make: Make) -> None:
    """The deferred trigger, reached past the service."""
    db_session.execute(text("INSERT INTO accounts (code, name, type) VALUES ('1000', 'Assets', 'asset')"))
    parent_id = db_session.execute(text("SELECT id FROM accounts WHERE code = '1000'")).scalar_one()
    db_session.execute(
        text("INSERT INTO accounts (code, name, type, parent_id) VALUES ('1100', 'Cash', 'asset', :p)"),
        {"p": parent_id},
    )
    with pytest.raises(IntegrityError, match="accounts_parent_not_postable"):
        settle_constraints(db_session)


def test_b3_the_database_allows_a_parent_once_it_is_switched_off_in_the_same_transaction(db_session: Session) -> None:
    db_session.execute(text("INSERT INTO accounts (code, name, type) VALUES ('1000', 'Assets', 'asset')"))
    parent_id = db_session.execute(text("SELECT id FROM accounts WHERE code = '1000'")).scalar_one()
    db_session.execute(
        text("INSERT INTO accounts (code, name, type, parent_id) VALUES ('1100', 'Cash', 'asset', :p)"),
        {"p": parent_id},
    )
    db_session.execute(text("UPDATE accounts SET is_postable = false WHERE id = :p"), {"p": parent_id})
    settle_constraints(db_session)


def test_b3_the_database_refuses_to_make_a_parent_postable_again(db_session: Session) -> None:
    db_session.execute(
        text("INSERT INTO accounts (code, name, type, is_postable) VALUES ('1000', 'Assets', 'asset', false)")
    )
    parent_id = db_session.execute(text("SELECT id FROM accounts WHERE code = '1000'")).scalar_one()
    db_session.execute(
        text("INSERT INTO accounts (code, name, type, parent_id) VALUES ('1100', 'Cash', 'asset', :p)"),
        {"p": parent_id},
    )
    settle_constraints(db_session)
    # Constraints stay immediate for the rest of this transaction, so the change itself is refused.
    with pytest.raises(IntegrityError, match="accounts_parent_not_postable"):
        db_session.execute(text("UPDATE accounts SET is_postable = true WHERE id = :p"), {"p": parent_id})


def test_b3_who_may_read_and_who_may_edit_accounts(client: TestClient, make: Make, auth: Auth) -> None:
    created = account(client, auth(make(Role.ACCOUNTANT)), "5100", "Rent", "expense")
    path = f"/api/v1/accounts/{created['id']}"
    assert client.get(path, headers=auth(make(Role.APPROVER))).status_code == 200
    assert client.get(path, headers=auth(make(Role.STAFF))).status_code == 403
    assert (
        client.post(
            "/api/v1/accounts", json={"code": "1", "name": "X", "type": "asset"}, headers=auth(make(Role.APPROVER))
        ).status_code
        == 403
    )
    assert client.post(f"{path}/deactivate", headers=auth(make(Role.STAFF))).status_code == 403


# Cost centres, projects and categories (B4) --------------------------------------------------------------------------


def test_b4_cost_centres_are_created_renamed_and_deactivated(
    client: TestClient, accountant_headers: dict[str, str]
) -> None:
    created = client.post(
        "/api/v1/cost-centers", json={"code": "ho", "name": "Head Office"}, headers=accountant_headers
    )
    assert created.status_code == 201
    body = created.json()
    assert (body["code"], body["is_active"], body["version"]) == ("HO", True, 1)
    renamed = client.patch(
        f"/api/v1/cost-centers/{body['id']}", json={"name": "Head  Office"}, headers=versioned(accountant_headers, 1)
    )
    assert renamed.json()["name"] == "Head Office"
    client.post(f"/api/v1/cost-centers/{body['id']}/deactivate", headers=accountant_headers)
    assert client.get("/api/v1/cost-centers?is_active=true", headers=accountant_headers).json()["total"] == 0
    # An inactive centre vanishes from pickers (the filter) but still reads by id, for historical documents.
    assert client.get(f"/api/v1/cost-centers/{body['id']}", headers=accountant_headers).json()["is_active"] is False
    clash = client.post("/api/v1/cost-centers", json={"code": "HO", "name": "Another"}, headers=accountant_headers)
    assert (clash.status_code, clash.json()["code"]) == (409, "DUPLICATE_VALUE")


def test_b4_projects_and_products_share_one_list_told_apart_by_kind(
    client: TestClient, accountant_headers: dict[str, str]
) -> None:
    client.post(
        "/api/v1/projects",
        json={"code": "PRJ-001", "name": "Gulberg Fit-out", "kind": "project"},
        headers=accountant_headers,
    )
    product = client.post(
        "/api/v1/projects", json={"code": "SKU-9", "name": "Cable drum", "kind": "product"}, headers=accountant_headers
    ).json()
    assert client.get("/api/v1/projects?kind=product", headers=accountant_headers).json()["total"] == 1
    assert client.get("/api/v1/projects", headers=accountant_headers).json()["total"] == 2
    kind_change = client.patch(
        f"/api/v1/projects/{product['id']}", json={"kind": "project"}, headers=versioned(accountant_headers, 1)
    )
    assert kind_change.status_code == 422  # the kind is fixed once created
    assert (
        client.post(
            "/api/v1/projects", json={"code": "X", "name": "Bad", "kind": "service"}, headers=accountant_headers
        ).status_code
        == 422
    )


def test_b4_every_role_may_read_cost_centres_projects_and_categories_but_only_editors_write(
    client: TestClient, make: Make, auth: Auth
) -> None:
    editor = auth(make(Role.ACCOUNTANT))
    client.post("/api/v1/cost-centers", json={"code": "OPS", "name": "Operations"}, headers=editor)
    client.post("/api/v1/projects", json={"code": "P1", "name": "Rollout", "kind": "project"}, headers=editor)
    for role in (Role.STAFF, Role.APPROVER):
        headers = auth(make(role))
        for path in ("/api/v1/cost-centers", "/api/v1/projects", "/api/v1/categories"):
            assert client.get(path, headers=headers).status_code == 200
        assert client.post("/api/v1/cost-centers", json={"code": "Z", "name": "Z"}, headers=headers).status_code == 403
        assert (
            client.post(
                "/api/v1/projects", json={"code": "Z", "name": "Z", "kind": "project"}, headers=headers
            ).status_code
            == 403
        )


def test_b4_a_category_posts_to_an_active_postable_expense_account(
    client: TestClient, accountant_headers: dict[str, str]
) -> None:
    rent = account(client, accountant_headers, "5100", "Rent", "expense")
    cash = account(client, accountant_headers, "1100", "Cash", "asset")
    ok = client.post(
        "/api/v1/categories", json={"name": "Office rent", "account_id": rent["id"]}, headers=accountant_headers
    )
    assert ok.status_code == 201
    wrong_type = client.post(
        "/api/v1/categories", json={"name": "Odd", "account_id": cash["id"]}, headers=accountant_headers
    )
    assert wrong_type.status_code == 422
    assert wrong_type.json()["errors"][0]["field"] == "account_id"
    group = account(client, accountant_headers, "5000", "Expenses", "expense")
    account(client, accountant_headers, "5200", "Utilities", "expense", parent_id=group["id"])
    parent = client.post(
        "/api/v1/categories", json={"name": "Group", "account_id": group["id"]}, headers=accountant_headers
    )
    assert (parent.status_code, parent.json()["code"]) == (422, "ACCOUNT_NOT_POSTABLE")
    assert (
        client.post(
            "/api/v1/categories", json={"name": "Ghost", "account_id": 99999}, headers=accountant_headers
        ).status_code
        == 422
    )
    clash = client.post(
        "/api/v1/categories", json={"name": " OFFICE   rent", "account_id": rent["id"]}, headers=accountant_headers
    )
    assert clash.status_code == 409


def test_b4_a_category_can_be_pointed_at_another_account_and_deactivated(
    client: TestClient, accountant_headers: dict[str, str]
) -> None:
    rent = account(client, accountant_headers, "5100", "Rent", "expense")
    utilities = account(client, accountant_headers, "5200", "Utilities", "expense")
    category = client.post(
        "/api/v1/categories", json={"name": "Premises", "account_id": rent["id"]}, headers=accountant_headers
    ).json()
    moved = client.patch(
        f"/api/v1/categories/{category['id']}",
        json={"account_id": utilities["id"]},
        headers=versioned(accountant_headers, 1),
    )
    assert moved.json()["account_id"] == utilities["id"]
    assert (
        client.post(f"/api/v1/categories/{category['id']}/deactivate", headers=accountant_headers).json()["is_active"]
        is False
    )
    assert client.get("/api/v1/categories?is_active=true", headers=accountant_headers).json()["total"] == 0
    assert client.get(f"/api/v1/categories/{category['id']}", headers=accountant_headers).status_code == 200


def test_b4_changes_to_master_data_are_audited(
    client: TestClient, accountant_headers: dict[str, str], db_session: Session
) -> None:
    centre = client.post("/api/v1/cost-centers", json={"code": "IT", "name": "IT"}, headers=accountant_headers).json()
    client.patch(
        f"/api/v1/cost-centers/{centre['id']}",
        json={"name": "Information Technology"},
        headers=versioned(accountant_headers, 1),
    )
    client.post(f"/api/v1/cost-centers/{centre['id']}/deactivate", headers=accountant_headers)
    rows = db_session.execute(
        text("SELECT action, before, after FROM audit_events WHERE entity_type = 'cost_center' ORDER BY id")
    ).all()
    assert [r.action for r in rows] == ["cost_center.created", "cost_center.updated", "cost_center.deactivated"]
    assert (rows[1].before, rows[1].after) == ({"name": "IT"}, {"name": "Information Technology"})
    assert (rows[2].before, rows[2].after) == ({"is_active": True}, {"is_active": False})


def test_b4_rows_in_every_master_table_are_never_deleted(
    client: TestClient, accountant_headers: dict[str, str], admin_headers: dict[str, str], db_session: Session
) -> None:
    rent = account(client, accountant_headers, "5100", "Rent", "expense")
    client.post("/api/v1/categories", json={"name": "Rent", "account_id": rent["id"]}, headers=accountant_headers)
    client.post("/api/v1/cost-centers", json={"code": "HO", "name": "Head Office"}, headers=accountant_headers)
    client.post(
        "/api/v1/projects", json={"code": "P1", "name": "Rollout", "kind": "project"}, headers=accountant_headers
    )
    cash = account(client, accountant_headers, "1100", "Cash", "asset")
    client.put("/api/v1/posting-accounts/cash", json={"account_id": cash["id"]}, headers=admin_headers)
    client.post(
        "/api/v1/periods/close", json={"start_date": "2026-08-01", "end_date": "2026-08-31"}, headers=admin_headers
    )
    for table in (
        "accounts",
        "categories",
        "cost_centers",
        "projects",
        "posting_accounts",
        "closed_periods",
        "tax_rules",
    ):
        db_session.execute(text("SAVEPOINT s"))
        with pytest.raises(Exception, match="never deleted"):
            db_session.execute(text(f"DELETE FROM {table}"))
        db_session.execute(text("ROLLBACK TO SAVEPOINT s"))


# Tax rules (B5) ------------------------------------------------------------------------------------------------------


def resolve(client: TestClient, headers: dict[str, str], **params: Any) -> Any:
    return client.get("/api/v1/tax-rules/resolve", params=params, headers=headers)


def test_b5_the_seeded_rules_each_cite_a_source_and_say_they_must_be_verified(
    client: TestClient, accountant_headers: dict[str, str]
) -> None:
    listing = client.get("/api/v1/tax-rules?limit=100", headers=accountant_headers).json()
    assert listing["total"] == 8  # two for sales tax, three categories by filer status for income tax
    for rule in listing["items"]:
        assert rule["source"].startswith("UNVERIFIED")
        assert "http" in rule["source"]


@pytest.mark.parametrize(
    ("params", "rate"),
    [
        ({"tax_type": "sales_tax_withholding", "supplier_registered": True}, 2000),
        ({"tax_type": "sales_tax_withholding", "supplier_registered": False}, 1800),
        ({"tax_type": "income_tax_withholding", "supplier_filer": True, "category": "goods"}, 450),
        ({"tax_type": "income_tax_withholding", "supplier_filer": False, "category": "goods"}, 900),
        ({"tax_type": "income_tax_withholding", "supplier_filer": True, "category": "services"}, 900),
        ({"tax_type": "income_tax_withholding", "supplier_filer": False, "category": "contracts"}, 1400),
    ],
)
def test_b5_each_kind_of_supplier_resolves_to_its_own_rate(
    client: TestClient, accountant_headers: dict[str, str], params: dict[str, Any], rate: int
) -> None:
    found = resolve(client, accountant_headers, on="2026-09-15", **params)
    assert found.status_code == 200
    assert found.json()["rate_bp"] == rate


def test_b5_registration_and_filer_status_drive_different_taxes(
    client: TestClient, accountant_headers: dict[str, str]
) -> None:
    """Registered but not a filer, and filer but not registered, get different answers for the two taxes."""
    registered_non_filer = {"supplier_registered": True, "supplier_filer": False}
    unregistered_filer = {"supplier_registered": False, "supplier_filer": True}
    on = "2026-09-15"
    sales_a = resolve(
        client, accountant_headers, tax_type="sales_tax_withholding", on=on, **registered_non_filer
    ).json()
    sales_b = resolve(client, accountant_headers, tax_type="sales_tax_withholding", on=on, **unregistered_filer).json()
    income_a = resolve(
        client, accountant_headers, tax_type="income_tax_withholding", category="goods", on=on, **registered_non_filer
    ).json()
    income_b = resolve(
        client, accountant_headers, tax_type="income_tax_withholding", category="goods", on=on, **unregistered_filer
    ).json()
    assert (sales_a["rate_bp"], sales_b["rate_bp"]) == (2000, 1800)  # sales tax follows registration only
    assert (income_a["rate_bp"], income_b["rate_bp"]) == (900, 450)  # income tax follows filer status only


def test_b5_a_rule_for_the_exact_category_beats_one_for_any(
    client: TestClient, accountant_headers: dict[str, str], admin_headers: dict[str, str]
) -> None:
    fallback = client.post(
        "/api/v1/tax-rules",
        json={
            "tax_type": "income_tax_withholding",
            "supplier_filer": True,
            "category": "any",
            "rate_bp": 1000,
            "effective_from": "2025-07-01",
            "source": "Test fallback",
        },
        headers=admin_headers,
    )
    assert fallback.status_code == 201
    on = "2026-09-15"
    base = {"tax_type": "income_tax_withholding", "supplier_filer": True, "on": on}
    assert resolve(client, accountant_headers, category="goods", **base).json()["rate_bp"] == 450  # specific wins
    assert resolve(client, accountant_headers, category="any", **base).json()["rate_bp"] == 1000
    assert resolve(client, accountant_headers, **base).json()["rate_bp"] == 1000


def test_b5_nothing_applies_before_the_first_rule_starts(
    client: TestClient, accountant_headers: dict[str, str]
) -> None:
    missing = resolve(
        client, accountant_headers, tax_type="sales_tax_withholding", supplier_registered=True, on="2025-06-30"
    )
    assert missing.status_code == 404


def test_b5_a_new_rate_takes_over_on_its_start_date_and_the_old_one_still_answers_for_earlier_dates(
    client: TestClient, admin_headers: dict[str, str]
) -> None:
    old = resolve(
        client, admin_headers, tax_type="income_tax_withholding", supplier_filer=True, category="goods", on="2026-06-30"
    ).json()
    ended = client.patch(
        f"/api/v1/tax-rules/{old['id']}",
        json={"effective_to": "2026-06-30"},
        headers=versioned(admin_headers, old["version"]),
    )
    assert ended.json()["effective_to"] == "2026-06-30"
    new = client.post(
        "/api/v1/tax-rules",
        json={
            "tax_type": "income_tax_withholding",
            "supplier_filer": True,
            "category": "goods",
            "rate_bp": 500,
            "effective_from": "2026-07-01",
            "source": "Finance Act, test",
        },
        headers=admin_headers,
    )
    assert new.status_code == 201
    params = {"tax_type": "income_tax_withholding", "supplier_filer": True, "category": "goods"}
    assert resolve(client, admin_headers, on="2026-06-30", **params).json()["id"] == old["id"]
    assert resolve(client, admin_headers, on="2026-07-01", **params).json()["id"] == new.json()["id"]
    assert resolve(client, admin_headers, on="2026-07-01", **params).json()["rate_bp"] == 500


def test_b5_overlapping_rules_are_refused(client: TestClient, admin_headers: dict[str, str]) -> None:
    body = {
        "tax_type": "income_tax_withholding",
        "supplier_filer": True,
        "category": "goods",
        "rate_bp": 500,
        "effective_from": "2026-01-01",
        "source": "Overlaps the seeded rule",
    }
    refused = client.post("/api/v1/tax-rules", json=body, headers=admin_headers)
    assert (refused.status_code, refused.json()["code"]) == (409, "TAX_RULE_OVERLAP")


def test_b5_the_database_refuses_overlapping_rules_by_any_route(db_session: Session) -> None:
    db_session.execute(text("SAVEPOINT s"))
    with pytest.raises(IntegrityError, match="no_overlapping_rules"):
        db_session.execute(
            text(
                "INSERT INTO tax_rules (tax_type, supplier_registered, supplier_filer, category, rate_bp,"
                " effective_from,"
                " source) VALUES ('income_tax_withholding', false, true, 'goods', 1, '2026-01-01', 'bypass')"
            )
        )
    db_session.execute(text("ROLLBACK TO SAVEPOINT s"))


def test_b5_a_rule_not_covering_the_same_category_or_flag_may_share_dates(db_session: Session) -> None:
    db_session.execute(
        text(
            "INSERT INTO tax_rules (tax_type, supplier_registered, supplier_filer, category, rate_bp,"
            " effective_from, source)"
            " VALUES ('income_tax_withholding', false, true, 'any', 1, '2026-01-01', 'different category')"
        )
    )


def test_b5_the_database_stores_only_the_flag_a_tax_depends_on(db_session: Session) -> None:
    db_session.execute(text("SAVEPOINT s"))
    with pytest.raises(IntegrityError, match="ck_tax_rules_only_the_relevant_flag"):
        db_session.execute(
            text(
                "INSERT INTO tax_rules (tax_type, supplier_registered, supplier_filer, category, rate_bp,"
                " effective_from,"
                " source) VALUES ('sales_tax_withholding', true, true, 'any', 1, '2020-01-01', 'bypass')"
            )
        )
    db_session.execute(text("ROLLBACK TO SAVEPOINT s"))


def test_b5_creating_a_rule_keeps_only_the_relevant_flag(client: TestClient, admin_headers: dict[str, str]) -> None:
    created = client.post(
        "/api/v1/tax-rules",
        json={
            "tax_type": "sales_tax_withholding",
            "supplier_registered": True,
            "category": "goods",
            "rate_bp": 100,
            "effective_from": "2020-01-01",
            "effective_to": "2020-12-31",
            "source": "Historic",
        },
        headers=admin_headers,
    )
    assert created.status_code == 201
    assert (created.json()["supplier_registered"], created.json()["supplier_filer"]) == (True, False)


@pytest.mark.parametrize(
    "body",
    [
        {"tax_type": "sales_tax_withholding", "rate_bp": 100},
        {"tax_type": "sales_tax_withholding", "supplier_registered": True, "supplier_filer": True, "rate_bp": 100},
        {"tax_type": "income_tax_withholding", "rate_bp": 100},
        {"tax_type": "income_tax_withholding", "supplier_filer": True, "supplier_registered": True, "rate_bp": 100},
        {"tax_type": "income_tax_withholding", "supplier_filer": True, "rate_bp": 10_001},
        {"tax_type": "income_tax_withholding", "supplier_filer": True, "rate_bp": -1},
        {"tax_type": "income_tax_withholding", "supplier_filer": True, "rate_bp": 100.5},
        {"tax_type": "income_tax_withholding", "supplier_filer": True, "rate_bp": 100, "effective_to": "2019-01-01"},
        {"tax_type": "income_tax_withholding", "supplier_filer": True, "rate_bp": 100, "source": ""},
        {"tax_type": "income_tax_withholding", "supplier_filer": True, "rate_bp": 100, "extra": 1},
    ],
)
def test_b5_a_rule_must_be_complete_and_sensible(
    client: TestClient, admin_headers: dict[str, str], body: dict[str, Any]
) -> None:
    payload = {"effective_from": "2020-01-01", "source": "Test", **body}
    assert client.post("/api/v1/tax-rules", json=payload, headers=admin_headers).status_code == 422


def test_b5_editing_a_rule_is_audited_and_cannot_change_who_it_applies_to(
    client: TestClient, admin_headers: dict[str, str], db_session: Session
) -> None:
    rule = resolve(
        client, admin_headers, tax_type="sales_tax_withholding", supplier_registered=True, on="2026-09-15"
    ).json()
    changed = client.patch(
        f"/api/v1/tax-rules/{rule['id']}", json={"rate_bp": 1900}, headers=versioned(admin_headers, rule["version"])
    )
    assert (changed.json()["rate_bp"], changed.json()["version"]) == (1900, rule["version"] + 1)
    stale = client.patch(
        f"/api/v1/tax-rules/{rule['id']}", json={"rate_bp": 1}, headers=versioned(admin_headers, rule["version"])
    )
    assert stale.status_code == 409
    assert (
        client.patch(
            f"/api/v1/tax-rules/{rule['id']}",
            json={"category": "goods"},
            headers=versioned(admin_headers, rule["version"] + 1),
        ).status_code
        == 422
    )
    row = db_session.execute(text("SELECT before, after FROM audit_events WHERE action = 'tax_rule.updated'")).one()
    assert (row.before, row.after) == ({"rate_bp": 2000}, {"rate_bp": 1900})


def test_b5_an_end_date_before_the_start_is_refused(client: TestClient, admin_headers: dict[str, str]) -> None:
    rule = resolve(
        client, admin_headers, tax_type="sales_tax_withholding", supplier_registered=True, on="2026-09-15"
    ).json()
    response = client.patch(
        f"/api/v1/tax-rules/{rule['id']}",
        json={"effective_to": "2025-01-01"},
        headers=versioned(admin_headers, rule["version"]),
    )
    assert response.status_code == 422


def test_b5_only_admins_edit_rates_and_the_office_reads_them(client: TestClient, make: Make, auth: Auth) -> None:
    body = {
        "tax_type": "sales_tax_withholding",
        "supplier_registered": True,
        "rate_bp": 1,
        "effective_from": "2020-01-01",
        "effective_to": "2020-12-31",
        "source": "x",
    }
    for role in (Role.APPROVER, Role.STAFF):
        assert client.post("/api/v1/tax-rules", json=body, headers=auth(make(role))).status_code == 403
        assert (
            client.patch("/api/v1/tax-rules/1", json={"rate_bp": 1}, headers=versioned(auth(make(role)), 1)).status_code
            == 403
        )
    assert client.get("/api/v1/tax-rules", headers=auth(make(Role.APPROVER))).status_code == 200
    assert client.get("/api/v1/tax-rules", headers=auth(make(Role.STAFF))).status_code == 403
    assert (
        resolve(client, auth(make(Role.APPROVER)), tax_type="sales_tax_withholding", on="2026-09-15").status_code == 403
    )


def test_b5_the_list_filters_by_type_category_and_date(client: TestClient, accountant_headers: dict[str, str]) -> None:
    assert (
        client.get("/api/v1/tax-rules?tax_type=sales_tax_withholding", headers=accountant_headers).json()["total"] == 2
    )
    assert client.get("/api/v1/tax-rules?category=goods", headers=accountant_headers).json()["total"] == 2
    assert client.get("/api/v1/tax-rules?active_on=2025-06-30", headers=accountant_headers).json()["total"] == 0
    assert client.get("/api/v1/tax-rules?active_on=2026-01-01", headers=accountant_headers).json()["total"] == 8


# Periods -------------------------------------------------------------------------------------------------------------


def test_closing_and_reopening_a_period_is_audited(
    client: TestClient, admin_headers: dict[str, str], db_session: Session
) -> None:
    closed = client.post(
        "/api/v1/periods/close", json={"start_date": "2026-08-01", "end_date": "2026-08-31"}, headers=admin_headers
    )
    assert closed.status_code == 201
    assert closed.json()["status"] == "closed"
    reopened = client.post(f"/api/v1/periods/{closed.json()['id']}/reopen", headers=admin_headers)
    assert (reopened.json()["status"], reopened.json()["reopened_at"] is not None) == ("reopened", True)
    assert client.post(f"/api/v1/periods/{closed.json()['id']}/reopen", headers=admin_headers).status_code == 409
    actions = [
        r[0]
        for r in db_session.execute(text("SELECT action FROM audit_events WHERE entity_type = 'period' ORDER BY id"))
    ]
    assert actions == ["period.closed", "period.reopened"]
    # The same range can be closed again once reopened.
    assert (
        client.post(
            "/api/v1/periods/close", json={"start_date": "2026-08-01", "end_date": "2026-08-31"}, headers=admin_headers
        ).status_code
        == 201
    )


def test_overlapping_closed_periods_are_refused_by_the_service_and_by_the_database(
    client: TestClient, admin_headers: dict[str, str], db_session: Session
) -> None:
    client.post(
        "/api/v1/periods/close", json={"start_date": "2026-08-01", "end_date": "2026-08-31"}, headers=admin_headers
    )
    overlap = client.post(
        "/api/v1/periods/close", json={"start_date": "2026-08-31", "end_date": "2026-09-30"}, headers=admin_headers
    )
    assert (overlap.status_code, overlap.json()["code"]) == (409, "PERIOD_OVERLAP")
    adjacent = client.post(
        "/api/v1/periods/close", json={"start_date": "2026-09-01", "end_date": "2026-09-30"}, headers=admin_headers
    )
    assert adjacent.status_code == 201
    closer = db_session.execute(text("SELECT id FROM users LIMIT 1")).scalar_one()
    db_session.execute(text("SAVEPOINT s"))
    with pytest.raises(IntegrityError, match="no_overlapping_closed_ranges"):
        db_session.execute(
            text(
                "INSERT INTO closed_periods (start_date, end_date, closed_by, closed_at)"
                " VALUES ('2026-08-10', '2026-08-12', :u, now())"
            ),
            {"u": closer},
        )
    db_session.execute(text("ROLLBACK TO SAVEPOINT s"))


def test_a_period_must_have_its_dates_in_order_and_only_admins_manage_periods(
    client: TestClient, admin_headers: dict[str, str], make: Make, auth: Auth
) -> None:
    backwards = client.post(
        "/api/v1/periods/close", json={"start_date": "2026-09-30", "end_date": "2026-09-01"}, headers=admin_headers
    )
    assert backwards.status_code == 422
    body = {"start_date": "2026-09-01", "end_date": "2026-09-30"}
    for role in (Role.ACCOUNTANT, Role.APPROVER, Role.STAFF):
        assert client.post("/api/v1/periods/close", json=body, headers=auth(make(role))).status_code == 403
        assert client.post("/api/v1/periods/1/reopen", headers=auth(make(role))).status_code == 403
    assert client.get("/api/v1/periods", headers=auth(make(Role.ACCOUNTANT))).status_code == 200
    assert client.get("/api/v1/periods", headers=auth(make(Role.STAFF))).status_code == 403
    assert client.post("/api/v1/periods/99999/reopen", headers=admin_headers).status_code == 404


def test_the_closed_period_lookup_is_inclusive_and_ignores_reopened_periods(
    client: TestClient, admin_headers: dict[str, str], db_session: Session
) -> None:
    created = client.post(
        "/api/v1/periods/close", json={"start_date": "2026-08-01", "end_date": "2026-08-31"}, headers=admin_headers
    ).json()
    found = master_repository.closed_period_containing
    assert found(db_session, date(2026, 8, 1)) is not None
    assert found(db_session, date(2026, 8, 31)) is not None
    assert found(db_session, date(2026, 7, 31)) is None
    assert found(db_session, date(2026, 9, 1)) is None
    client.post(f"/api/v1/periods/{created['id']}/reopen", headers=admin_headers)
    assert found(db_session, date(2026, 8, 15)) is None


# Posting accounts ----------------------------------------------------------------------------------------------------


def test_posting_accounts_are_set_replaced_and_audited(
    client: TestClient, accountant_headers: dict[str, str], admin_headers: dict[str, str], db_session: Session
) -> None:
    cash = account(client, accountant_headers, "1100", "Cash in Hand", "asset")
    bank = account(client, accountant_headers, "1200", "Meezan Current", "asset")
    first = client.put("/api/v1/posting-accounts/cash", json={"account_id": cash["id"]}, headers=admin_headers)
    assert (first.status_code, first.json()["account_id"]) == (200, cash["id"])
    second = client.put("/api/v1/posting-accounts/cash", json={"account_id": bank["id"]}, headers=admin_headers)
    assert second.json()["account_id"] == bank["id"]
    listing = client.get("/api/v1/posting-accounts", headers=accountant_headers).json()
    assert [(row["key"], row["account_id"]) for row in listing] == [("cash", bank["id"])]
    rows = db_session.execute(
        text("SELECT before, after FROM audit_events WHERE action = 'posting_account.set' ORDER BY id")
    ).all()
    assert rows[0].before is None
    assert rows[1].before == {"account_id": cash["id"]}


def test_a_posting_key_needs_the_right_kind_of_active_postable_account(
    client: TestClient, accountant_headers: dict[str, str], admin_headers: dict[str, str]
) -> None:
    liability = account(client, accountant_headers, "2200", "Sales Tax Payable", "liability")
    asset = account(client, accountant_headers, "1100", "Cash", "asset")
    group = account(client, accountant_headers, "1000", "Assets", "asset")
    account(client, accountant_headers, "1300", "Advance Tax", "asset", parent_id=group["id"])
    assert (
        client.put(
            "/api/v1/posting-accounts/sales_tax_withheld", json={"account_id": liability["id"]}, headers=admin_headers
        ).status_code
        == 200
    )
    assert (
        client.put(
            "/api/v1/posting-accounts/cash", json={"account_id": liability["id"]}, headers=admin_headers
        ).status_code
        == 422
    )
    assert (
        client.put(
            "/api/v1/posting-accounts/sales_tax_withheld", json={"account_id": asset["id"]}, headers=admin_headers
        ).status_code
        == 422
    )
    assert (
        client.put("/api/v1/posting-accounts/cash", json={"account_id": group["id"]}, headers=admin_headers).status_code
        == 422
    )
    client.post(f"/api/v1/accounts/{asset['id']}/deactivate", headers=admin_headers)
    assert (
        client.put("/api/v1/posting-accounts/cash", json={"account_id": asset["id"]}, headers=admin_headers).status_code
        == 422
    )
    assert (
        client.put("/api/v1/posting-accounts/cash", json={"account_id": 99999}, headers=admin_headers).status_code
        == 422
    )
    assert (
        client.put("/api/v1/posting-accounts/petty_cash", json={"account_id": 1}, headers=admin_headers).status_code
        == 422
    )


def test_b5_an_accountant_sets_the_rates_and_corrects_them(
    client: TestClient, accountant_headers: dict[str, str]
) -> None:
    body = {
        "tax_type": "income_tax_withholding",
        "supplier_filer": True,
        "category": "any",
        "rate_bp": 1000,
        "effective_from": "2025-07-01",
        "source": "Set by the accountant in charge",
    }
    created = client.post("/api/v1/tax-rules", json=body, headers=accountant_headers)
    assert created.status_code == 201, created.text
    rule = created.json()
    corrected = client.patch(
        f"/api/v1/tax-rules/{rule['id']}",
        json={"rate_bp": 1100, "source": "Corrected against the latest Finance Act"},
        headers=versioned(accountant_headers, rule["version"]),
    )
    assert corrected.status_code == 200
    assert corrected.json()["rate_bp"] == 1100


def test_a_bookkeeper_sets_posting_accounts_and_nobody_else_does(
    client: TestClient, make: Make, auth: Auth, accountant_headers: dict[str, str]
) -> None:
    bank = client.post(
        "/api/v1/accounts", json={"code": "1250", "name": "Bank - Another", "type": "asset"}, headers=accountant_headers
    ).json()
    done = client.put("/api/v1/posting-accounts/bank", json={"account_id": bank["id"]}, headers=accountant_headers)
    assert done.status_code == 200, done.text
    assert done.json()["account_id"] == bank["id"]
    for role in (Role.APPROVER, Role.STAFF):
        assert (
            client.put("/api/v1/posting-accounts/cash", json={"account_id": 1}, headers=auth(make(role))).status_code
            == 403
        )
