"""Numbering, idempotent posting and void, proved with requests that really run at once on a committing database.

The scratch database is migrated from nothing, so it carries the seeded chart of accounts and posting accounts. Each
test repeats with fresh vouchers, because a race that only sometimes goes wrong must be given several chances to."""

from collections import Counter
from collections.abc import Callable, Coroutine
from typing import Any

import httpx2
import pytest

from app.config import Settings
from app.core.enums import Role
from app.models.user import User
from tests.support.parallel import Parallel, parallel_app

pytestmark = pytest.mark.concurrency

Call = Callable[[httpx2.AsyncClient], Coroutine[Any, Any, httpx2.Response]]
ROUNDS = 3


def post(path: str, json: dict[str, Any] | None = None, headers: dict[str, str] | None = None) -> Call:
    async def call(client: httpx2.AsyncClient) -> httpx2.Response:
        return await client.post(path, json=json, headers=headers)

    return call


def statuses(responses: list[httpx2.Response]) -> Counter[int]:
    return Counter(r.status_code for r in responses)


class Books:
    """The people and the accounts for one scratch database."""

    def __init__(self, world: Parallel) -> None:
        self.world = world
        self.bookkeeper = world.make(Role.ACCOUNTANT)
        self.approver = world.make(Role.APPROVER)
        self.admin = world.make(Role.ADMIN)
        self.expense = int(world.scalar("SELECT id FROM accounts WHERE code = '5100'"))
        self.cash = int(world.scalar("SELECT id FROM accounts WHERE code = '1100'"))

    def headers(self, user: User, **extra: str) -> dict[str, str]:
        return {**self.world.headers(user), **extra}

    def approved_voucher(self, amount: str = "100.00") -> dict[str, Any]:
        """A voucher created, submitted and approved through the API, ready to post."""
        world = self.world
        body = {
            "voucher_type": "PV",
            "description": "Office rent",
            "lines": [
                {"account_id": self.expense, "debit": amount},
                {"account_id": self.cash, "credit": amount},
            ],
        }
        voucher: dict[str, Any] = world.run([post("/api/v1/vouchers", body, self.headers(self.bookkeeper))])[0].json()
        for actor, action in ((self.bookkeeper, "submit"), (self.approver, "approve")):
            response = world.run(
                [
                    post(
                        f"/api/v1/vouchers/{voucher['id']}/{action}",
                        None,
                        self.headers(actor, **{"If-Match": str(voucher["version"])}),
                    )
                ]
            )[0]
            assert response.status_code == 200, response.text
            voucher = response.json()
        assert voucher["status"] == "approved"
        return voucher

    def post_call(self, voucher: dict[str, Any], key: str) -> Call:
        headers = self.headers(self.bookkeeper, **{"If-Match": str(voucher["version"]), "Idempotency-Key": key})
        return post(f"/api/v1/vouchers/{voucher['id']}/post", None, headers)

    def void_call(self, voucher: dict[str, Any], key: str) -> Call:
        headers = self.headers(self.admin, **{"If-Match": str(voucher["version"]), "Idempotency-Key": key})
        return post(f"/api/v1/vouchers/{voucher['id']}/void", {"reason": "Entered twice"}, headers)


def assert_gapless(world: Parallel) -> None:
    """The invariant the counter exists for: the numbers given are exactly 1 to N, and the counter agrees."""
    sequences = world.scalar(
        "SELECT coalesce(array_agg(seq ORDER BY seq), ARRAY[]::int[]) FROM vouchers"
        " WHERE number IS NOT NULL AND voucher_type = 'PV'"
    )
    assert sequences == list(range(1, len(sequences) + 1)), sequences
    if sequences:
        assert world.scalar("SELECT last_seq FROM number_counters WHERE voucher_type = 'PV'") == len(sequences)


def test_e3_simultaneous_posts_get_consecutive_numbers_with_no_gap_and_no_duplicate(settings: Settings) -> None:
    with parallel_app(settings) as world:
        books = Books(world)
        total = 0
        for round_number in range(ROUNDS):
            vouchers = [books.approved_voucher() for _ in range(8)]
            responses = world.run(
                [books.post_call(v, f"post-{round_number}-{n}-voucher") for n, v in enumerate(vouchers)]
            )
            assert statuses(responses) == {200: 8}, [r.text for r in responses if r.status_code != 200]
            total += 8
            numbers = [r.json()["number"] for r in responses]
            assert len(set(numbers)) == 8
            assert world.scalar("SELECT count(*) FROM vouchers WHERE number IS NOT NULL") == total
            assert_gapless(world)


def test_e5_the_same_key_sent_at_once_posts_one_voucher_and_every_caller_gets_it(settings: Settings) -> None:
    with parallel_app(settings) as world:
        books = Books(world)
        for round_number in range(ROUNDS):
            voucher = books.approved_voucher()
            responses = world.run([books.post_call(voucher, f"same-key-round-{round_number}")] * 8)
            assert statuses(responses) == {200: 8}, [r.text for r in responses if r.status_code != 200]
            assert len({r.json()["number"] for r in responses}) == 1
            assert (
                world.scalar(
                    "SELECT count(*) FROM document_events WHERE document_id = :i AND action = 'posted'"
                    " AND document_type = 'voucher'",
                    i=voucher["id"],
                )
                == 1
            )
        assert_gapless(world)
        assert world.scalar("SELECT count(*) FROM vouchers WHERE number IS NOT NULL") == ROUNDS


def test_e5_different_keys_for_one_voucher_at_once_post_it_once(settings: Settings) -> None:
    with parallel_app(settings) as world:
        books = Books(world)
        for round_number in range(ROUNDS):
            voucher = books.approved_voucher()
            responses = world.run([books.post_call(voucher, f"key-{round_number}-{n}-abcdef") for n in range(6)])
            assert statuses(responses) == {200: 1, 409: 5}, [(r.status_code, r.text) for r in responses]
            assert {r.json()["code"] for r in responses if r.status_code == 409} <= {
                "VERSION_CONFLICT",
                "INVALID_TRANSITION",
            }
        assert_gapless(world)
        assert world.scalar("SELECT count(*) FROM vouchers WHERE number IS NOT NULL") == ROUNDS


def test_e6_simultaneous_voids_of_one_voucher_make_exactly_one_reversal(settings: Settings) -> None:
    with parallel_app(settings) as world:
        books = Books(world)
        for round_number in range(ROUNDS):
            voucher = books.approved_voucher()
            posted = world.run([books.post_call(voucher, f"post-for-void-{round_number}")])[0].json()
            responses = world.run([books.void_call(posted, f"void-{round_number}-{n}-abcdef") for n in range(6)])
            assert statuses(responses) == {200: 1, 409: 5}, [(r.status_code, r.text) for r in responses]
            assert world.scalar("SELECT count(*) FROM vouchers WHERE reversal_of_id = :i", i=posted["id"]) == 1
            assert world.scalar("SELECT status FROM vouchers WHERE id = :i", i=posted["id"]) == "void"
        assert_gapless(world)  # each round used two numbers: the original and its reversal


def test_e6_the_same_void_key_sent_at_once_returns_the_same_reversal_to_everyone(settings: Settings) -> None:
    with parallel_app(settings) as world:
        books = Books(world)
        for round_number in range(ROUNDS):
            voucher = books.approved_voucher()
            posted = world.run([books.post_call(voucher, f"post-replay-void-{round_number}")])[0].json()
            responses = world.run([books.void_call(posted, f"one-void-key-{round_number}")] * 6)
            assert statuses(responses) == {200: 6}, [(r.status_code, r.text) for r in responses]
            assert len({r.json()["reversal"]["id"] for r in responses}) == 1
            assert world.scalar("SELECT count(*) FROM vouchers WHERE reversal_of_id = :i", i=posted["id"]) == 1
        assert_gapless(world)


def test_e3_posts_and_voids_at_the_same_moment_share_one_counter_without_a_gap(settings: Settings) -> None:
    with parallel_app(settings) as world:
        books = Books(world)
        for round_number in range(ROUNDS):
            to_void = [
                world.run([books.post_call(books.approved_voucher(), f"setup-{round_number}-{n}-abcd")])[0].json()
                for n in range(3)
            ]
            to_post = [books.approved_voucher() for _ in range(4)]
            calls = [books.void_call(v, f"mixed-void-{round_number}-{n}") for n, v in enumerate(to_void)]
            calls += [books.post_call(v, f"mixed-post-{round_number}-{n}") for n, v in enumerate(to_post)]
            responses = world.run(calls)
            assert statuses(responses) == {200: 7}, [(r.status_code, r.text) for r in responses]
            assert_gapless(world)
