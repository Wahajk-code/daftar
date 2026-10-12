from datetime import UTC, datetime

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError, ProgrammingError
from sqlalchemy.orm import Session

from app.core.enums import Role
from app.core.logging import correlation_id_var
from app.models import User
from app.services.audit import AuditService
from tests.support.clock import FakeClock

INSUFFICIENT_PRIVILEGE = "42501"


def make_user(**overrides: object) -> User:
    values: dict[str, object] = {
        "email": "ayesha@example.com",
        "full_name": "Ayesha Khan",
        "password_hash": "not-a-real-hash",
        "role": Role.ACCOUNTANT,
    }
    return User(**{**values, **overrides})


# Users ---------------------------------------------------------------------------------------------------------------


def test_a_user_round_trips_with_defaults(db_session: Session) -> None:
    user = make_user()
    db_session.add(user)
    db_session.flush()
    db_session.refresh(user)
    assert user.id > 0
    assert user.is_active is True
    assert user.tour_completed_at is None
    assert user.role is Role.ACCOUNTANT
    assert user.created_at.tzinfo is not None


def test_the_database_refuses_an_upper_case_email(db_session: Session) -> None:
    db_session.add(make_user(email="Ayesha@Example.com"))
    with pytest.raises(IntegrityError, match="ck_users_email_lower"):
        db_session.flush()


def test_the_database_refuses_a_duplicate_email(db_session: Session) -> None:
    db_session.add_all([make_user(), make_user(full_name="Someone Else")])
    with pytest.raises(IntegrityError, match="uq_users_email"):
        db_session.flush()


def test_the_database_refuses_a_blank_name(db_session: Session) -> None:
    db_session.add(make_user(full_name="   "))
    with pytest.raises(IntegrityError, match="ck_users_full_name_not_blank"):
        db_session.flush()


def test_the_database_refuses_an_unknown_role(db_session: Session) -> None:
    db_session.execute(text("SAVEPOINT s"))
    with pytest.raises(DBAPIError, match="user_role"):
        db_session.execute(
            text("INSERT INTO users (email, full_name, password_hash, role) VALUES ('a@b.c', 'A', 'x', 'owner')")
        )
    db_session.execute(text("ROLLBACK TO SAVEPOINT s"))


# Audit: the service --------------------------------------------------------------------------------------------------


def test_the_audit_service_writes_in_the_callers_transaction(db_session: Session, clock: FakeClock) -> None:
    user = make_user()
    db_session.add(user)
    db_session.flush()
    token = correlation_id_var.set("corr-12345678")
    try:
        AuditService(db_session, clock).record(
            actor_id=user.id,
            action="vendor.update",
            entity_type="vendor",
            entity_id=7,
            before={"name": "Old"},
            after={"name": "New"},
        )
    finally:
        correlation_id_var.reset(token)

    (event,) = AuditService(db_session, clock).history("vendor", 7)
    assert event.actor_id == user.id
    assert event.action == "vendor.update"
    assert (event.before, event.after) == ({"name": "Old"}, {"name": "New"})
    assert event.occurred_at == datetime(2026, 10, 12, 14, 5, tzinfo=UTC)  # the server's clock, not the database's
    assert event.correlation_id == "corr-12345678"


def test_an_audit_row_rolls_back_with_the_change_it_describes(db_session: Session, clock: FakeClock) -> None:
    service = AuditService(db_session, clock)

    def change_that_fails() -> None:
        with db_session.begin_nested():
            service.record(actor_id=None, action="vendor.create", entity_type="vendor", entity_id=1)
            raise RuntimeError("the change failed after the audit row was written")

    with pytest.raises(RuntimeError, match="the change failed"):
        change_that_fails()
    assert service.history("vendor", 1) == []


def test_history_comes_back_in_the_order_written(db_session: Session, clock: FakeClock) -> None:
    service = AuditService(db_session, clock)
    for action in ("create", "submit", "approve"):
        clock.advance(minutes=1)
        service.record(actor_id=None, action=action, entity_type="expense", entity_id=3)
    assert [e.action for e in service.history("expense", 3)] == ["create", "submit", "approve"]


def test_an_event_may_have_no_actor(db_session: Session, clock: FakeClock) -> None:
    event = AuditService(db_session, clock).record(actor_id=None, action="auth.login_failed", entity_type="user")
    assert event.actor_id is None
    assert event.entity_id is None


# Audit: the database -------------------------------------------------------------------------------------------------


def sqlstate(error: Exception) -> str | None:
    orig = getattr(error, "orig", None)
    return getattr(orig, "sqlstate", None)


@pytest.mark.parametrize(
    "statement",
    [
        "UPDATE audit_events SET action = 'tampered'",
        "DELETE FROM audit_events",
        "TRUNCATE audit_events",
    ],
)
def test_the_application_role_cannot_change_or_remove_audit_rows(
    db_session: Session, clock: FakeClock, statement: str
) -> None:
    AuditService(db_session, clock).record(actor_id=None, action="x", entity_type="t", entity_id=1)
    db_session.execute(text("SAVEPOINT guard"))
    with pytest.raises(ProgrammingError) as caught:
        db_session.execute(text(statement))
    assert sqlstate(caught.value) == INSUFFICIENT_PRIVILEGE
    db_session.execute(text("ROLLBACK TO SAVEPOINT guard"))


def test_the_application_role_can_insert_and_select_audit_rows(db_session: Session, clock: FakeClock) -> None:
    AuditService(db_session, clock).record(actor_id=None, action="x", entity_type="t", entity_id=1)
    assert db_session.execute(text("SELECT count(*) FROM audit_events WHERE entity_type = 't'")).scalar_one() == 1


def test_the_application_role_cannot_change_the_schema(db_session: Session) -> None:
    db_session.execute(text("SAVEPOINT guard"))
    with pytest.raises(ProgrammingError) as caught:
        db_session.execute(text("CREATE TABLE sneaky (id int)"))
    assert sqlstate(caught.value) == INSUFFICIENT_PRIVILEGE
    db_session.execute(text("ROLLBACK TO SAVEPOINT guard"))


def test_the_connection_really_is_the_application_role(db_session: Session) -> None:
    assert db_session.execute(text("SELECT current_user")).scalar_one() == "daftar_app"
    assert db_session.execute(text("SELECT rolsuper FROM pg_roles WHERE rolname = current_user")).scalar_one() is False
