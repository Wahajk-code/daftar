"""The demonstration data (`python -m app.seed`) matches `docs/seed-data.md`, whatever day it is run on.

It is built in a scratch database from nothing but the migrations, through the real services, so every rule applied
to it: numbers are gapless, vouchers balance, the period lock holds. Each test reads the result back with queries."""

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import Settings
from app.core.security import Passwords
from app.core.storage import MemoryStorage
from app.db import build_engine
from app.seed import __main__ as seed_command
from app.seed import data
from app.seed.run import Summary, seed
from app.services.duplicates import DuplicateFinder
from tests.support.database import scratch_database

pytestmark = pytest.mark.slow

# An ordinary day, a day early in the month with the year turning, and the first day of a month.
DAYS = [
    datetime(2026, 10, 12, 10, 0, tzinfo=UTC),
    datetime(2027, 1, 5, 10, 0, tzinfo=UTC),
    datetime(2026, 10, 1, 4, 0, tzinfo=UTC),
]


@contextmanager
def seeded(settings: Settings, now: datetime) -> Iterator[tuple[Session, MemoryStorage, Summary]]:
    with scratch_database(settings) as db:
        engine = build_engine(db.app_url, settings)
        storage = MemoryStorage()
        try:
            with Session(engine) as session:
                summary = seed(session, settings, storage, now)
                yield session, storage, summary
        finally:
            engine.dispose()


@pytest.fixture(scope="module", params=DAYS, ids=["oct-12", "jan-5-new-year", "oct-1-first-day"])
def world(
    request: pytest.FixtureRequest, settings: Settings
) -> Iterator[tuple[Session, MemoryStorage, Summary, datetime]]:
    with seeded(settings, request.param) as (session, storage, summary):
        yield session, storage, summary, request.param


def scalar(session: Session, sql: str, **params: Any) -> Any:
    return session.execute(text(sql), params).scalar_one()


def test_the_four_people_exist_one_per_role_and_can_sign_in_with_the_published_password(
    world: tuple[Session, MemoryStorage, Summary, datetime], settings: Settings
) -> None:
    session = world[0]
    rows = session.execute(text("SELECT email, role, full_name, password_hash FROM users ORDER BY id")).all()
    assert [(r.email, r.role, r.full_name) for r in rows] == [(e, role, name) for e, name, role in data.USERS]
    passwords = Passwords(
        time_cost=settings.argon2_time_cost,
        memory_cost_kib=settings.argon2_memory_kib,
        parallelism=settings.argon2_parallelism,
    )
    assert all(passwords.verify(r.password_hash, data.DEMO_PASSWORD) for r in rows)
    assert not passwords.verify(rows[0].password_hash, "not the password")


def test_the_reference_data_is_there(world: tuple[Session, MemoryStorage, Summary, datetime]) -> None:
    session = world[0]
    assert scalar(session, "SELECT count(*) FROM accounts") == 19
    assert [r.code for r in session.execute(text("SELECT code FROM cost_centers ORDER BY code")).all()] == sorted(
        c for c, _ in data.COST_CENTRES
    )
    assert [r.code for r in session.execute(text("SELECT code FROM projects ORDER BY code")).all()] == [
        "PRJ-001",
        "PRJ-002",
    ]
    vendors = session.execute(text("SELECT name, is_sales_tax_registered, is_filer FROM vendors ORDER BY id")).all()
    assert [(v.name, v.is_sales_tax_registered, v.is_filer) for v in vendors] == [
        (v.name, v.registered, v.filer) for v in data.VENDORS
    ]


def test_there_are_forty_expenses_sixty_per_cent_direct_across_every_status(
    world: tuple[Session, MemoryStorage, Summary, datetime],
) -> None:
    session = world[0]
    assert scalar(session, "SELECT count(*) FROM expenses") == 40
    assert scalar(session, "SELECT count(*) FROM expenses WHERE expense_type = 'direct'") == 24
    statuses = {r.status for r in session.execute(text("SELECT DISTINCT status FROM expenses")).all()}
    assert statuses == {"draft", "submitted", "approved", "rejected", "posted"}


def test_the_splits_include_the_two_whole_examples_and_at_least_three_with_a_remainder(
    world: tuple[Session, MemoryStorage, Summary, datetime],
) -> None:
    session = world[0]
    for amount, bps in (("10000.00", [3333, 3333, 3334]), ("7500.00", [3300, 3300, 3400])):
        found = session.execute(
            text(
                "SELECT array_agg(a.basis_points ORDER BY a.basis_points) FROM expense_allocations a"
                " JOIN expenses e ON e.id = a.expense_id WHERE e.amount = :amount GROUP BY e.id"
            ),
            {"amount": amount},
        ).scalar_one()
        assert found == sorted(bps)
    with_remainder = scalar(
        session,
        "SELECT count(DISTINCT e.id) FROM expense_allocations a JOIN expenses e ON e.id = a.expense_id"
        " WHERE (e.amount * 100)::bigint * a.basis_points % 10000 <> 0",
    )
    assert with_remainder >= 3
    # Whatever the split, every part adds up to the expense: the database checks it, and so does this.
    assert (
        scalar(
            session,
            "SELECT count(*) FROM (SELECT e.id FROM expenses e JOIN expense_allocations a ON a.expense_id = e.id"
            " GROUP BY e.id, e.amount HAVING sum(a.amount) <> e.amount) bad",
        )
        == 0
    )


def test_there_are_fifteen_purchases_and_at_least_four_from_unregistered_vendors(
    world: tuple[Session, MemoryStorage, Summary, datetime],
) -> None:
    session = world[0]
    assert scalar(session, "SELECT count(*) FROM purchases") == 15
    assert scalar(session, "SELECT count(*) FROM purchases WHERE NOT vendor_registered") >= 4
    assert (
        scalar(
            session, "SELECT count(*) FROM purchases WHERE NOT vendor_registered AND document_kind = 'purchase_memo'"
        )
        >= 4
    )


def test_about_twenty_five_vouchers_are_posted_and_numbered_without_a_gap_per_type_and_year(
    world: tuple[Session, MemoryStorage, Summary, datetime],
) -> None:
    session = world[0]
    assert scalar(session, "SELECT count(*) FROM vouchers WHERE status = 'posted'") == 25
    groups = session.execute(
        text(
            "SELECT voucher_type, year, array_agg(seq ORDER BY seq) AS sequences FROM vouchers"
            " WHERE number IS NOT NULL GROUP BY voucher_type, year"
        )
    ).all()
    assert {g.voucher_type for g in groups} == {"PV", "RV", "JV"}
    for group in groups:
        assert group.sequences == list(range(1, len(group.sequences) + 1)), (group.voucher_type, group.year)
    counters = {
        (r.voucher_type, r.year): r.last_seq for r in session.execute(text("SELECT * FROM number_counters")).all()
    }
    assert counters == {(g.voucher_type, g.year): len(g.sequences) for g in groups}


def test_exactly_one_voucher_is_void_with_its_reversal_visible_and_linked(
    world: tuple[Session, MemoryStorage, Summary, datetime],
) -> None:
    session, _, _, now = world
    void = session.execute(text("SELECT id, number, void_reason FROM vouchers WHERE status = 'void'")).one()
    assert void.void_reason == data.VOID_REASON
    reversal = session.execute(
        text("SELECT id, status, number, document_date FROM vouchers WHERE reversal_of_id = :v"), {"v": void.id}
    ).one()
    assert reversal.status == "posted"
    assert reversal.document_date == now.date().replace(day=1)  # dated the day it was voided, in the current month
    mirrored = session.execute(
        text(
            "SELECT a.account_id, a.debit, a.credit, b.debit AS reversed_debit, b.credit AS reversed_credit"
            " FROM voucher_lines a JOIN voucher_lines b ON b.line_no = a.line_no AND b.voucher_id = :r"
            " WHERE a.voucher_id = :v"
        ),
        {"v": void.id, "r": reversal.id},
    ).all()
    assert mirrored
    assert all((m.debit, m.credit) == (m.reversed_credit, m.reversed_debit) for m in mirrored)


def test_two_documents_are_waiting_for_the_approver(world: tuple[Session, MemoryStorage, Summary, datetime]) -> None:
    session = world[0]
    waiting = sum(
        scalar(session, f"SELECT count(*) FROM {table} WHERE status = 'submitted'")
        for table in ("expenses", "purchases", "vouchers")
    )
    assert waiting == 2


def test_one_expense_sits_just_under_fifty_thousand(world: tuple[Session, MemoryStorage, Summary, datetime]) -> None:
    assert scalar(world[0], "SELECT count(*) FROM expenses WHERE amount = 49750.00 AND status = 'submitted'") == 1


def test_the_near_duplicate_purchase_pair_raises_a_warning_and_the_shared_receipt_is_found(
    world: tuple[Session, MemoryStorage, Summary, datetime],
) -> None:
    from app.models.documents import Expense, Purchase

    session = world[0]
    pair = (
        session.execute(text("SELECT id FROM purchases WHERE invoice_number = 'RS-2102' ORDER BY id")).scalars().all()
    )
    assert len(pair) == 2
    second = session.get(Purchase, pair[1])
    assert second is not None
    kinds = {w.kind.value for w in DuplicateFinder(session).for_purchase(second)}
    assert "same_invoice" in kinds
    shared = (
        session.execute(
            text(
                "SELECT expense_id FROM attachments WHERE sha256 IN"
                " (SELECT sha256 FROM attachments GROUP BY sha256 HAVING count(*) > 1)"
            )
        )
        .scalars()
        .all()
    )
    assert len(shared) == 2
    expense = session.get(Expense, shared[0])
    assert expense is not None
    assert "same_receipt" in {w.kind.value for w in DuplicateFinder(session).for_expense(expense, only_author=None)}


def test_receipts_are_stored_and_there_are_three_or_four_distinct_images(
    world: tuple[Session, MemoryStorage, Summary, datetime],
) -> None:
    session, storage, _, _ = world
    assert 3 <= scalar(session, "SELECT count(DISTINCT sha256) FROM attachments") <= 4
    keys = [r.storage_key for r in session.execute(text("SELECT storage_key FROM attachments")).all()]
    assert keys
    assert all(key in storage.objects for key in keys)


def test_the_two_months_before_this_one_are_closed_and_this_one_is_open(
    world: tuple[Session, MemoryStorage, Summary, datetime],
) -> None:
    session, _, _, now = world
    first_of_this_month = now.date().replace(day=1)
    periods = session.execute(text("SELECT start_date, end_date FROM closed_periods ORDER BY start_date")).all()
    assert len(periods) == 2
    assert periods[0].end_date + timedelta(days=1) == periods[1].start_date  # one after the other, no gap
    assert periods[1].end_date == first_of_this_month - timedelta(days=1)
    assert periods[0].start_date.day == 1
    assert (first_of_this_month - periods[0].start_date).days <= 62  # two months back, no more
    assert not any(p.start_date <= now.date() <= p.end_date for p in periods)


def test_every_document_is_dated_inside_the_window_and_never_in_the_future(
    world: tuple[Session, MemoryStorage, Summary, datetime],
) -> None:
    session, _, _, now = world
    first = session.execute(text("SELECT min(start_date) FROM closed_periods")).scalar_one()
    for table in ("expenses", "purchases", "vouchers"):
        low, high = session.execute(text(f"SELECT min(document_date), max(document_date) FROM {table}")).one()
        assert first <= low, table
        assert high <= now.date(), table


def test_running_the_seed_again_changes_nothing(
    world: tuple[Session, MemoryStorage, Summary, datetime], settings: Settings
) -> None:
    session, storage, first, now = world
    again = seed(session, settings, storage, now)
    assert again.already_seeded
    assert (again.expenses, again.purchases, again.vouchers, again.users) == (
        first.expenses,
        first.purchases,
        first.vouchers,
        first.users,
    )


def test_the_command_refuses_to_run_in_production(
    settings: Settings, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(seed_command, "get_settings", lambda: settings.model_copy(update={"environment": "production"}))
    assert seed_command.main() == 2
    assert "production" in capsys.readouterr().err
