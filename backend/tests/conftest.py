from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from hypothesis import settings as hypothesis_settings
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.core.enums import Role
from app.core.rate_limit import RateLimiter, build_policies
from app.db import build_engine, get_session
from app.deps import get_clock, get_mailer
from app.main import create_app
from app.models.user import User
from tests.support.clock import FakeClock
from tests.support.database import migrate, require_test_database, reset_schema
from tests.support.factories import RecordingMailer, bearer, make_user

hypothesis_settings.register_profile("default", deadline=None, max_examples=200)
hypothesis_settings.load_profile("default")


@pytest.fixture(scope="session")
def settings() -> Settings:
    config = get_settings()
    require_test_database(config)
    return config


@pytest.fixture(scope="session")
def migrated_database(settings: Settings) -> None:
    """daftar_test, rebuilt from nothing by the migrations at the start of every run."""
    reset_schema(settings.owner_database_url)
    migrate(settings.owner_database_url)


@pytest.fixture(scope="session")
def app_engine(settings: Settings, migrated_database: None) -> Iterator[Engine]:
    """Connects as the application role, so tests see the same privileges production does."""
    engine = build_engine(settings.database_url, settings)
    yield engine
    engine.dispose()


@pytest.fixture
def db_session(app_engine: Engine) -> Iterator[Session]:
    """The fast setup: everything the test does, including service commits, is rolled back afterwards."""
    connection = app_engine.connect()
    outer = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint", expire_on_commit=False)
    try:
        yield session
    finally:
        session.close()
        outer.rollback()
        connection.close()


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock(datetime(2026, 10, 12, 14, 5, tzinfo=UTC))


@pytest.fixture
def mailer() -> RecordingMailer:
    return RecordingMailer()


@pytest.fixture
def app(db_session: Session, clock: FakeClock, mailer: RecordingMailer, settings: Settings) -> FastAPI:
    application = create_app()

    def request_session() -> Iterator[Session]:
        """Behave like production: a request that fails leaves nothing behind. (Production closes its session, which
        rolls back; the test session outlives the request, so the rollback is explicit.)"""
        try:
            yield db_session
        except Exception:
            db_session.rollback()
            raise

    application.dependency_overrides[get_session] = request_session
    application.dependency_overrides[get_clock] = lambda: clock
    application.dependency_overrides[get_mailer] = lambda: mailer
    # A limiter of its own per test, on the test's clock, so counters never leak between tests.
    application.state.rate_limiter = RateLimiter(
        clock, build_policies(settings.rate_limit_overrides), max_keys=settings.rate_limit_max_keys
    )
    return application


@pytest.fixture
def make(db_session: Session, clock: FakeClock) -> Callable[..., User]:
    """Create a user: make(Role.ADMIN), make(Role.STAFF, email="x@daftar.test")."""

    def build(role: Role = Role.STAFF, **kwargs: Any) -> User:
        user = make_user(db_session, role, now=clock.now(), **kwargs)
        db_session.commit()  # durable for the test, so a failed request's rollback cannot take it away
        return user

    return build


@pytest.fixture
def auth(settings: Settings, clock: FakeClock) -> Callable[[User], dict[str, str]]:
    """Headers for a signed-in user: client.get(url, headers=auth(user))."""
    return lambda user: bearer(user, settings, clock.now())


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    # An unhandled error must come back as the bare 500 a real client would see, not be re-raised into the test.
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client


@pytest.fixture
def route_inventory(app: FastAPI) -> list[dict[str, Any]]:
    """Every operation in the OpenAPI file, for tests that must cover each endpoint (the access matrix starts here)."""
    inventory: list[dict[str, Any]] = []
    for path, methods in app.openapi()["paths"].items():
        for method, operation in methods.items():
            inventory.append({"method": method.upper(), "path": path, **operation})
    return inventory
