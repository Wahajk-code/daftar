"""Story N1 (server side): whether the onboarding tour is done is kept on the server, per person, for every device."""

from collections.abc import Callable

from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.enums import Role
from app.models.user import User
from tests.support.clock import FakeClock

Make = Callable[..., User]
Auth = Callable[[User], dict[str, str]]


def test_n1_a_new_person_has_not_done_the_tour(client: TestClient, make: Make, auth: Auth) -> None:
    me = client.get("/api/v1/me", headers=auth(make(Role.STAFF))).json()
    assert me["tour_completed_at"] is None


def test_n1_finishing_or_skipping_the_tour_is_remembered_with_the_time(
    client: TestClient, make: Make, auth: Auth, clock: FakeClock
) -> None:
    headers = auth(make(Role.APPROVER))
    done = client.post("/api/v1/me/tour/complete", headers=headers)
    assert done.status_code == 200
    assert done.json()["tour_completed_at"] == "2026-10-12T14:05:00Z"
    assert client.get("/api/v1/me", headers=headers).json()["tour_completed_at"] == "2026-10-12T14:05:00Z"


def test_n1_completing_twice_keeps_the_first_time_and_audits_once(
    client: TestClient, make: Make, auth: Auth, clock: FakeClock, db_session: Session
) -> None:
    user = make(Role.STAFF)
    client.post("/api/v1/me/tour/complete", headers=auth(user))
    clock.advance(hours=3)
    again = client.post("/api/v1/me/tour/complete", headers=auth(user))  # a fresh token: the first has expired
    assert again.json()["tour_completed_at"] == "2026-10-12T14:05:00Z"
    count = db_session.execute(
        text("SELECT count(*) FROM audit_events WHERE action = 'user.tour_completed'")
    ).scalar_one()
    assert count == 1


def test_n1_the_tour_can_be_offered_again(client: TestClient, make: Make, auth: Auth) -> None:
    headers = auth(make(Role.ACCOUNTANT))
    client.post("/api/v1/me/tour/complete", headers=headers)
    restarted = client.post("/api/v1/me/tour/restart", headers=headers)
    assert restarted.json()["tour_completed_at"] is None
    assert client.get("/api/v1/me", headers=headers).json()["tour_completed_at"] is None


def test_n1_each_person_has_their_own_tour_state(client: TestClient, make: Make, auth: Auth) -> None:
    first, second = auth(make(Role.STAFF)), auth(make(Role.STAFF))
    client.post("/api/v1/me/tour/complete", headers=first)
    assert client.get("/api/v1/me", headers=second).json()["tour_completed_at"] is None


def test_n1_the_tour_routes_need_a_sign_in(client: TestClient) -> None:
    for path in ("/api/v1/me/tour/complete", "/api/v1/me/tour/restart"):
        assert client.post(path).status_code == 401
