from datetime import UTC, datetime

import pytest
from sqlalchemy import Engine, text
from sqlalchemy.exc import IntegrityError, StatementError
from sqlalchemy.orm import Session

from app.config import Settings
from app.models import AuditEvent
from tests.support.database import settle_constraints


def show(session: Session, name: str) -> str:
    return str(session.execute(text(f"SHOW {name}")).scalar_one())


def test_the_session_runs_in_utc(db_session: Session) -> None:
    assert show(db_session, "timezone") == "UTC"


def test_timeouts_are_set_on_every_connection(db_session: Session, settings: Settings) -> None:
    assert show(db_session, "statement_timeout") == "15s"
    assert show(db_session, "lock_timeout") == "5s"
    assert show(db_session, "idle_in_transaction_session_timeout") == "30s"
    assert settings.db_statement_timeout_ms == 15_000


def test_the_pool_is_bounded(app_engine: Engine, settings: Settings) -> None:
    assert app_engine.pool.size() == settings.db_pool_size  # type: ignore[attr-defined]
    assert app_engine.pool._max_overflow == settings.db_max_overflow  # type: ignore[attr-defined]


def test_a_timestamp_comes_back_as_aware_utc(db_session: Session) -> None:
    event = AuditEvent(occurred_at=datetime(2026, 10, 12, 14, 5, tzinfo=UTC), action="a", entity_type="t")
    db_session.add(event)
    db_session.flush()
    db_session.expire(event)
    assert event.occurred_at == datetime(2026, 10, 12, 14, 5, tzinfo=UTC)
    assert event.occurred_at.tzinfo is not None
    assert event.occurred_at.utcoffset().total_seconds() == 0  # type: ignore[union-attr]


def test_a_naive_timestamp_is_refused_on_the_way_in(db_session: Session) -> None:
    db_session.add(AuditEvent(occurred_at=datetime(2026, 10, 12, 14, 5), action="a", entity_type="t"))  # noqa: DTZ001
    with pytest.raises(StatementError, match="timezone-aware"):
        db_session.flush()


def test_deferred_constraints_are_reached_by_settling_them(db_session: Session) -> None:
    """The mechanism every later database rule test relies on: a never-committed transaction still fires them."""
    db_session.execute(
        text("CREATE TEMP TABLE probe (n int, CONSTRAINT probe_unique UNIQUE (n) DEFERRABLE INITIALLY DEFERRED)")
    )
    db_session.execute(text("INSERT INTO probe VALUES (1), (1)"))  # accepted for now: the check waits for commit
    with pytest.raises(IntegrityError, match="probe_unique"):
        settle_constraints(db_session)
