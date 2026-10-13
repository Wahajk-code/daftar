"""The activity report: what each person did in a period, so a manager can see how the work is going. Counted from the
approval history, so a rejected, voided or re-entered document leaves its trace against the person who did it."""

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.enums import Role
from app.models.user import User
from tests.support.clock import FakeClock
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


def v(headers: dict[str, str], doc: dict[str, Any], **extra: str) -> dict[str, str]:
    return {**headers, "If-Match": str(doc["version"]), **extra}


def by_name(report: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {row["full_name"]: row for row in report["rows"]}


def counts(row: dict[str, Any]) -> dict[str, int]:
    return {key: value for key, value in row.items() if isinstance(value, int) and key != "user_id"}


@pytest.fixture
def team(make: Make, auth: Auth) -> dict[str, Any]:
    people = {
        "staff": make(Role.STAFF, full_name="Bilal Ahmed"),
        "accountant": make(Role.ACCOUNTANT, full_name="Usman Tariq"),
        "approver": make(Role.APPROVER, full_name="Ayesha Siddiqui"),
        "quiet": make(Role.STAFF, full_name="Zeeshan Quiet"),
    }
    return {**people, "h": {name: auth(user) for name, user in people.items()}}


@pytest.fixture
def busy_day(client: TestClient, team: dict[str, Any], lookups: Lookups, ledger: Ledger) -> None:
    """Bilal writes two expenses and sends both in; one is rejected. Usman writes a purchase and two vouchers, posts one
    and voids it. Ayesha decides three things."""
    staff, accountant, approver = team["h"]["staff"], team["h"]["accountant"], team["h"]["approver"]
    for description in ("Good one", "Needs fixing"):
        expense = client.post(
            "/api/v1/expenses", json=direct_expense(lookups, description=description), headers=staff
        ).json()
        client.post(f"/api/v1/expenses/{expense['id']}/submit", headers=v(staff, expense))
        expense = client.get(f"/api/v1/expenses/{expense['id']}", headers=staff).json()
        if description == "Good one":
            client.post(f"/api/v1/expenses/{expense['id']}/approve", headers=v(approver, expense))
        else:
            client.post(
                f"/api/v1/expenses/{expense['id']}/reject", json={"comment": "No"}, headers=v(approver, expense)
            )
    purchase = client.post(
        "/api/v1/purchases", json=purchase_body(lookups.vendors["unreg_nonfiler"]), headers=accountant
    ).json()
    submitted = client.post(f"/api/v1/purchases/{purchase['id']}/submit", headers=v(accountant, purchase)).json()
    client.post(f"/api/v1/purchases/{purchase['id']}/approve", headers=v(approver, submitted))
    first = client.post("/api/v1/vouchers", json=voucher_body(ledger), headers=accountant).json()
    client.post("/api/v1/vouchers", json=voucher_body(ledger, "50.00"), headers=accountant)  # left as a draft
    submitted = client.post(f"/api/v1/vouchers/{first['id']}/submit", headers=v(accountant, first)).json()
    ready = client.post(f"/api/v1/vouchers/{first['id']}/approve", headers=v(approver, submitted)).json()
    posted = client.post(
        f"/api/v1/vouchers/{first['id']}/post", headers=v(accountant, ready, **{"Idempotency-Key": "activity-post-1"})
    ).json()
    client.post(
        f"/api/v1/vouchers/{first['id']}/void",
        json={"reason": "Wrong account"},
        headers=v(accountant, posted, **{"Idempotency-Key": "activity-void-1"}),
    )


def test_g5_each_person_has_their_own_counts(client: TestClient, team: dict[str, Any], busy_day: None) -> None:
    report = client.get("/api/v1/reports/activity", headers=team["h"]["approver"]).json()
    rows = by_name(report)
    assert counts(rows["Bilal Ahmed"]) == {
        "expenses_created": 2,
        "purchases_created": 0,
        "vouchers_created": 0,
        "submitted": 2,
        "rejected_received": 1,
        "approved": 0,
        "rejected_given": 0,
        "posted": 0,
        "voided": 0,
    }
    assert counts(rows["Usman Tariq"]) == {
        "expenses_created": 0,
        "purchases_created": 1,
        "vouchers_created": 2,
        "submitted": 2,
        "rejected_received": 0,
        "approved": 0,
        "rejected_given": 0,
        "posted": 1,
        "voided": 1,
    }
    assert counts(rows["Ayesha Siddiqui"]) == {
        "expenses_created": 0,
        "purchases_created": 0,
        "vouchers_created": 0,
        "submitted": 0,
        "rejected_received": 0,
        "approved": 3,  # one expense, one purchase, one voucher
        "rejected_given": 1,
        "posted": 0,
        "voided": 0,
    }


def test_g5_someone_who_did_nothing_still_appears_with_zeros(
    client: TestClient, team: dict[str, Any], busy_day: None
) -> None:
    rows = by_name(client.get("/api/v1/reports/activity", headers=team["h"]["approver"]).json())
    assert set(counts(rows["Zeeshan Quiet"]).values()) == {0}


def test_g5_a_deactivated_person_is_not_listed(
    client: TestClient, make: Make, auth: Auth, team: dict[str, Any]
) -> None:
    make(Role.STAFF, full_name="Left The Company", active=False)
    rows = by_name(client.get("/api/v1/reports/activity", headers=team["h"]["approver"]).json())
    assert "Left The Company" not in rows


def test_g5_the_period_is_in_the_display_zone_not_utc(
    client: TestClient, team: dict[str, Any], lookups: Lookups, clock: FakeClock, auth: Auth
) -> None:
    """20:30 UTC on 12 October is 01:30 on 13 October in Karachi, so that is the day the work belongs to."""
    clock.set(datetime(2026, 10, 12, 20, 30, tzinfo=UTC))
    staff, approver = auth(team["staff"]), auth(team["approver"])  # fresh tokens: the clock has moved past the old ones
    client.post("/api/v1/expenses", json=direct_expense(lookups), headers=staff)

    def created(**params: str) -> int:
        report = client.get("/api/v1/reports/activity", params=params, headers=approver).json()
        return int(by_name(report)["Bilal Ahmed"]["expenses_created"])

    assert created(date_from="2026-10-13", date_to="2026-10-13") == 1
    assert created(date_from="2026-10-12", date_to="2026-10-12") == 0
    assert created(date_to="2026-10-12") == 0
    assert created(date_from="2026-10-13") == 1
    assert created() == 1


def test_g5_a_backwards_range_is_refused(client: TestClient, team: dict[str, Any]) -> None:
    response = client.get(
        "/api/v1/reports/activity",
        params={"date_from": "2026-10-31", "date_to": "2026-10-01"},
        headers=team["h"]["approver"],
    )
    assert response.status_code == 422


def test_g5_staff_cannot_see_how_everyone_is_doing(client: TestClient, team: dict[str, Any]) -> None:
    for path in ("/api/v1/reports/activity", "/api/v1/reports/activity/csv"):
        assert client.get(path, headers=team["h"]["staff"]).status_code == 403


def test_g5_the_csv_matches_and_is_audited(
    client: TestClient, team: dict[str, Any], busy_day: None, db_session: Session
) -> None:
    response = client.get("/api/v1/reports/activity/csv", headers=team["h"]["accountant"])
    assert response.status_code == 200
    assert response.content.startswith(b"\xef\xbb\xbf")
    lines = response.content.decode("utf-8-sig").splitlines()
    assert lines[0].split(",")[:2] == ["Person", "Role"]
    assert "Bilal Ahmed,staff,2,0,0,2,1,0,0,0,0" in lines
    assert "Usman Tariq,accountant,0,1,2,2,0,0,0,1,1" in lines
    from sqlalchemy import text

    row = db_session.execute(text("SELECT after FROM audit_events WHERE action = 'report.exported'")).scalar_one()
    assert row["report"] == "activity"
    assert row["rows"] == 4  # the four active people, including the quiet one
