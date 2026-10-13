"""List endpoints ask the database a fixed number of questions, however many rows they return.

Each test measures a list with a few rows, adds many more rows of the richest kind (splits, lines, attachments,
vouchers), measures again, and requires the same number of statements. A list that loaded each row's parents or
children one at a time (N+1) would grow with the data and fail here."""

from collections.abc import Callable
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from app.core.enums import Role
from app.models.user import User
from tests.support.documents import (
    Ledger,
    Lookups,
    create_ledger,
    create_lookups,
    direct_expense,
    image_bytes,
    indirect_expense,
    purchase_body,
    purchase_line,
    voucher_body,
)
from tests.support.querycount import count_statements

Make = Callable[..., User]
Auth = Callable[[User], dict[str, str]]

FEW, MANY = 2, 12
MOST_STATEMENTS = 12  # a ceiling as well: authentication, the page, its total and the eager loads, and no more


@pytest.fixture
def lookups(db_session: Session, make: Make) -> Lookups:
    return create_lookups(db_session, make(Role.ADMIN, active=False))


@pytest.fixture
def office(make: Make, auth: Auth) -> dict[str, str]:
    return auth(make(Role.ADMIN))


def statements_for(client: TestClient, engine: Engine, path: str, headers: dict[str, str], **params: Any) -> int:
    with count_statements(engine) as seen:
        response = client.get(path, params={"limit": 100, **params}, headers=headers)
    assert response.status_code == 200, response.text
    return len(seen)


def check(client: TestClient, engine: Engine, path: str, headers: dict[str, str], grow: Callable[[int], None]) -> None:
    grow(FEW)
    few = statements_for(client, engine, path, headers)
    grow(MANY)
    many = statements_for(client, engine, path, headers)
    assert many == few, f"{path} sent {few} statements for {FEW} rows but {many} for {FEW + MANY}"
    assert many <= MOST_STATEMENTS, f"{path} sent {many} statements"


def test_the_expense_list_does_not_ask_once_per_expense(
    client: TestClient, app_engine: Engine, office: dict[str, str], lookups: Lookups
) -> None:
    a, b, _ = (centre.id for centre in lookups.centres)
    split = [{"cost_center_id": a, "basis_points": 5000}, {"cost_center_id": b, "basis_points": 5000}]

    def grow(count: int) -> None:
        for n in range(count):
            body = indirect_expense(lookups, split) if n % 2 else direct_expense(lookups, project_id=None)
            created = client.post("/api/v1/expenses", json=body, headers=office).json()
            client.post(
                f"/api/v1/expenses/{created['id']}/attachments",
                files={"file": ("r.jpg", image_bytes("JPEG", (40 + n + count, 30)), "image/jpeg")},
                headers=office,
            )

    check(client, app_engine, "/api/v1/expenses", office, grow)


def test_the_purchase_list_does_not_ask_once_per_purchase(
    client: TestClient, app_engine: Engine, office: dict[str, str], lookups: Lookups
) -> None:
    def grow(count: int) -> None:
        for n in range(count):
            lines = [purchase_line(item=f"Item {n}-{k}") for k in range(3)]
            vendor = lookups.vendors["unreg_nonfiler" if n % 2 else "reg_filer"]
            client.post("/api/v1/purchases", json=purchase_body(vendor, lines), headers=office)

    check(client, app_engine, "/api/v1/purchases", office, grow)


def test_the_voucher_list_and_the_register_do_not_ask_once_per_voucher(
    client: TestClient, app_engine: Engine, office: dict[str, str], lookups: Lookups, db_session: Session, make: Make
) -> None:
    ledger: Ledger = create_ledger(db_session, lookups, make(Role.ADMIN, active=False))

    def grow(count: int) -> None:
        for _ in range(count):
            client.post("/api/v1/vouchers", json=voucher_body(ledger), headers=office)

    check(client, app_engine, "/api/v1/vouchers", office, grow)
    few = statements_for(client, app_engine, "/api/v1/reports/vouchers", office, statuses="draft")
    grow(MANY)
    assert statements_for(client, app_engine, "/api/v1/reports/vouchers", office, statuses="draft") == few


def test_the_master_data_and_user_lists_do_not_ask_once_per_row(
    client: TestClient, app_engine: Engine, office: dict[str, str], make: Make
) -> None:
    counter = iter(range(1000))

    def grow(count: int) -> None:
        for _ in range(count):
            n = next(counter)
            make(Role.STAFF)
            client.post(
                "/api/v1/vendors", json={"name": f"Vendor {n}", "is_sales_tax_registered": False}, headers=office
            )
            client.post("/api/v1/cost-centers", json={"code": f"CC{n}", "name": f"Centre {n}"}, headers=office)

    for path in ("/api/v1/users", "/api/v1/vendors", "/api/v1/cost-centers"):
        grow(FEW)
        few = statements_for(client, app_engine, path, office)
        grow(MANY)
        many = statements_for(client, app_engine, path, office)
        assert many == few, f"{path} sent {few} statements for few rows but {many} for many"
        assert many <= MOST_STATEMENTS


def test_the_counter_does_see_a_loop_that_asks_once_per_row(
    app_engine: Engine, db_session: Session, make: Make
) -> None:
    """Proof that the checks above can fail: a deliberate N+1 grows with the number of rows."""
    from sqlalchemy import select

    for _ in range(5):
        make(Role.STAFF)
    ids = list(db_session.scalars(select(User.id)))
    with count_statements(app_engine) as seen:
        for user_id in ids:
            db_session.get(User, user_id, populate_existing=True)
    assert len(seen) == len(ids) >= 5
