"""Story F3, the reading side: an Admin can read the audit log, newest first, filter it, and nobody else can."""

from collections.abc import Callable
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.enums import Role
from app.models.user import User
from tests.support.documents import Lookups, create_lookups, direct_expense

Make = Callable[..., User]
Auth = Callable[[User], dict[str, str]]


@pytest.fixture
def lookups(db_session: Session, make: Make) -> Lookups:
    return create_lookups(db_session, make(Role.ADMIN, active=False))


@pytest.fixture
def activity(client: TestClient, make: Make, auth: Auth, lookups: Lookups) -> dict[str, Any]:
    """Two people each make an expense and one of them changes it, so the log has something to filter."""
    first, second = make(Role.STAFF, full_name="Bilal Ahmed"), make(Role.STAFF, full_name="Sana Malik")
    one = client.post("/api/v1/expenses", json=direct_expense(lookups, description="First"), headers=auth(first)).json()
    two = client.post(
        "/api/v1/expenses", json=direct_expense(lookups, description="Second"), headers=auth(second)
    ).json()
    client.patch(
        f"/api/v1/expenses/{one['id']}",
        json={"description": "First, corrected"},
        headers={**auth(first), "If-Match": str(one["version"])},
    )
    return {"first": first, "second": second, "one": one, "two": two}


def log(client: TestClient, admin: dict[str, str], **params: Any) -> dict[str, Any]:
    response = client.get("/api/v1/audit", params=params, headers=admin)
    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    return body


def test_f3_the_log_lists_newest_first_with_who_did_it(
    client: TestClient, make: Make, auth: Auth, activity: dict[str, Any]
) -> None:
    admin = auth(make(Role.ADMIN))
    page = log(client, admin, entity_type="expense")
    assert [(e["action"], e["actor_name"]) for e in page["items"]] == [
        ("expense.updated", "Bilal Ahmed"),
        ("expense.created", "Sana Malik"),
        ("expense.created", "Bilal Ahmed"),
    ]
    ids = [e["id"] for e in page["items"]]
    assert ids == sorted(ids, reverse=True)


def test_f3_an_update_shows_what_changed(client: TestClient, make: Make, auth: Auth, activity: dict[str, Any]) -> None:
    admin = auth(make(Role.ADMIN))
    update = log(client, admin, action="updated")["items"][0]
    assert update["before"] == {"description": "First"}
    assert update["after"] == {"description": "First, corrected"}
    assert update["entity_id"] == activity["one"]["id"]
    assert update["correlation_id"]


def test_f3_the_log_can_be_narrowed(client: TestClient, make: Make, auth: Auth, activity: dict[str, Any]) -> None:
    admin = auth(make(Role.ADMIN))
    by_person = log(client, admin, actor_id=activity["second"].id, entity_type="expense")
    assert [e["entity_id"] for e in by_person["items"]] == [activity["two"]["id"]]
    one_record = log(client, admin, entity_type="expense", entity_id=activity["one"]["id"])
    assert one_record["total"] == 2
    assert log(client, admin, action="CREATED", entity_type="expense")["total"] == 2  # case does not matter


def test_f3_the_dates_are_days_in_the_display_zone(
    client: TestClient, make: Make, auth: Auth, activity: dict[str, Any]
) -> None:
    admin = auth(make(Role.ADMIN))
    assert log(client, admin, entity_type="expense", date_from="2026-10-12", date_to="2026-10-12")["total"] == 3
    assert log(client, admin, entity_type="expense", date_from="2026-10-13")["total"] == 0
    assert log(client, admin, entity_type="expense", date_to="2026-10-11")["total"] == 0
    backwards = client.get("/api/v1/audit", params={"date_from": "2026-10-31", "date_to": "2026-10-01"}, headers=admin)
    assert backwards.status_code == 422


def test_f3_the_log_is_paged(client: TestClient, make: Make, auth: Auth, activity: dict[str, Any]) -> None:
    admin = auth(make(Role.ADMIN))
    second_page = log(client, admin, entity_type="expense", limit=2, offset=2)
    assert (second_page["total"], len(second_page["items"])) == (3, 1)


@pytest.mark.parametrize("role", [Role.ACCOUNTANT, Role.APPROVER, Role.STAFF])
def test_f3_only_admins_read_the_log(client: TestClient, make: Make, auth: Auth, role: Role) -> None:
    response = client.get("/api/v1/audit", headers=auth(make(role)))
    assert (response.status_code, response.json()["code"]) == (403, "FORBIDDEN")


def test_f3_there_is_no_way_to_change_or_delete_an_entry(
    client: TestClient, make: Make, auth: Auth, activity: dict[str, Any]
) -> None:
    admin = auth(make(Role.ADMIN))
    entry = log(client, admin)["items"][0]
    for method in ("PUT", "PATCH", "DELETE", "POST"):
        assert client.request(method, f"/api/v1/audit/{entry['id']}", headers=admin).status_code in (404, 405)
