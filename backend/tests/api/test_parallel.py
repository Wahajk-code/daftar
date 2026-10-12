"""Locks, atomic claims and uniqueness, proved with requests that really run at once on a committing database.

Each test repeats with fresh data, because a race that only sometimes goes wrong must be given several chances to."""

from collections import Counter
from collections.abc import Callable, Coroutine
from typing import Any

import httpx2
import pytest

from app.config import Settings
from app.core.enums import Role
from tests.support.factories import TEST_PASSWORD
from tests.support.parallel import parallel_app

pytestmark = pytest.mark.concurrency

Call = Callable[[httpx2.AsyncClient], Coroutine[Any, Any, httpx2.Response]]
ROUNDS = 4


def post(path: str, json: dict[str, Any] | None = None, headers: dict[str, str] | None = None) -> Call:
    async def call(client: httpx2.AsyncClient) -> httpx2.Response:
        return await client.post(path, json=json, headers=headers)

    return call


def statuses(responses: list[httpx2.Response]) -> Counter[int]:
    return Counter(r.status_code for r in responses)


def test_a1_parallel_wrong_logins_cannot_exceed_the_limit(settings: Settings) -> None:
    with parallel_app(settings) as world:
        user = world.make(Role.STAFF)
        wrong = post("/api/v1/auth/login", {"email": user.email, "password": "definitely not it"})
        responses = world.run([wrong] * 20)
        assert statuses(responses) == {401: 5, 429: 15}
        # Only five of the twenty reached the password check, and only five failures were recorded.
        assert world.scalar("SELECT count(*) FROM audit_events WHERE action = 'auth.login_failed'") == 5
        assert all("Retry-After" in r.headers for r in responses if r.status_code == 429)


def test_a1_parallel_refreshes_with_one_token_have_exactly_one_winner(settings: Settings) -> None:
    with parallel_app(settings) as world:
        for _ in range(ROUNDS):
            user = world.make(Role.STAFF)
            login = world.run([post("/api/v1/auth/login", {"email": user.email, "password": TEST_PASSWORD})])[0]
            token = login.json()["refresh_token"]
            responses = world.run([post("/api/v1/auth/refresh", {"refresh_token": token})] * 8)
            assert statuses(responses) == {200: 1, 401: 7}


def test_i1_parallel_uses_of_one_reset_link_have_exactly_one_winner(settings: Settings) -> None:
    with parallel_app(settings, {"token_confirm_ip": "1000/900"}) as world:
        for _ in range(ROUNDS):
            user = world.make(Role.STAFF)
            world.run([post("/api/v1/auth/forgot-password", {"email": user.email})])
            token = world.mailer.token_for(user.email)
            body = {"token": token, "new_password": "a brand new passphrase"}
            responses = world.run([post("/api/v1/auth/reset-password", body)] * 6)
            assert statuses(responses) == {204: 1, 400: 5}


def test_i4_parallel_acceptances_of_one_invitation_create_one_account(settings: Settings) -> None:
    with parallel_app(settings, {"token_confirm_ip": "1000/900"}) as world:
        admin = world.make(Role.ADMIN)
        for number in range(ROUNDS):
            email = f"hire{number}@daftar.pk"
            world.run([post("/api/v1/invites", {"email": email, "role": "staff"}, world.headers(admin))])
            token = world.mailer.token_for(email)
            calls = [
                post(
                    "/api/v1/auth/invites/accept",
                    {"token": token, "full_name": f"Person {n}", "password": "a good passphrase"},
                )
                for n in range(6)
            ]
            responses = world.run(calls)
            assert statuses(responses) == {201: 1, 400: 5}
            assert world.scalar("SELECT count(*) FROM users WHERE email = :e", e=email) == 1


def test_i4_parallel_invitations_to_one_address_leave_one_waiting(settings: Settings) -> None:
    with parallel_app(settings) as world:
        admin = world.make(Role.ADMIN)
        headers = world.headers(admin)
        responses = world.run([post("/api/v1/invites", {"email": "same@daftar.pk", "role": "staff"}, headers)] * 6)
        assert statuses(responses) == {201: 1, 409: 5}
        assert {r.json()["code"] for r in responses if r.status_code == 409} == {"INVITE_PENDING"}


def test_a2_two_admins_removing_each_other_at_once_leave_an_admin(settings: Settings) -> None:
    with parallel_app(settings) as world:
        for _ in range(ROUNDS):
            first, second = world.make(Role.ADMIN), world.make(Role.ADMIN)
            before = world.scalar("SELECT count(*) FROM users WHERE role = 'admin' AND is_active")
            responses = world.run(
                [
                    post(f"/api/v1/users/{second.id}/role", {"role": "staff"}, world.headers(first)),
                    post(f"/api/v1/users/{first.id}/role", {"role": "staff"}, world.headers(second)),
                ]
            )
            # One goes through; the other finds its own admin rights gone once it holds the lock and is refused.
            assert statuses(responses) == {200: 1, 403: 1}
            after = world.scalar("SELECT count(*) FROM users WHERE role = 'admin' AND is_active")
            assert after == before - 1
            assert after >= 1


def test_a2_a_ring_of_admins_deactivating_one_another_never_leaves_none(settings: Settings) -> None:
    with parallel_app(settings) as world:
        for _ in range(ROUNDS):
            a, b, c = world.make(Role.ADMIN), world.make(Role.ADMIN), world.make(Role.ADMIN)
            responses = world.run(
                [
                    post(f"/api/v1/users/{b.id}/deactivate", headers=world.headers(a)),
                    post(f"/api/v1/users/{c.id}/deactivate", headers=world.headers(b)),
                    post(f"/api/v1/users/{a.id}/deactivate", headers=world.headers(c)),
                ]
            )
            assert all(r.status_code in (200, 403, 409) for r in responses)
            assert (
                world.scalar(
                    "SELECT count(*) FROM users WHERE role = 'admin' AND is_active AND id = ANY(:ids)",
                    ids=[a.id, b.id, c.id],
                )
                >= 1
            )


def test_b1_parallel_creation_of_the_same_vendor_name_makes_one_vendor(settings: Settings) -> None:
    with parallel_app(settings) as world:
        accountant = world.make(Role.ACCOUNTANT)
        body = {"name": "Ravi Stationers", "is_sales_tax_registered": False}
        responses = world.run([post("/api/v1/vendors", body, world.headers(accountant))] * 6)
        assert statuses(responses) == {201: 1, 409: 5}
        assert world.scalar("SELECT count(*) FROM vendors") == 1


def test_b4_parallel_updates_with_the_same_version_have_one_winner(settings: Settings) -> None:
    with parallel_app(settings) as world:
        accountant = world.make(Role.ACCOUNTANT)
        headers = world.headers(accountant)
        created = world.run([post("/api/v1/cost-centers", {"code": "HO", "name": "Head Office"}, headers)])[0].json()

        def rename(name: str) -> Call:
            async def call(client: httpx2.AsyncClient) -> httpx2.Response:
                return await client.patch(
                    f"/api/v1/cost-centers/{created['id']}", json={"name": name}, headers={**headers, "If-Match": "1"}
                )

            return call

        responses = world.run([rename(f"Name {n}") for n in range(6)])
        assert statuses(responses) == {200: 1, 409: 5}
        assert world.scalar("SELECT version FROM cost_centers WHERE id = :i", i=created["id"]) == 2
