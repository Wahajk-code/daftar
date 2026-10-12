"""A real, committing application for tests that need requests to run at the same time.

It uses a scratch database and the application role, with sessions that commit like production. Requests go through
an async client, so the sync endpoints really run in parallel threads, each on its own connection."""

import asyncio
from collections.abc import Callable, Coroutine, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any

import httpx2
from fastapi import FastAPI
from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import Settings
from app.core.clock import Clock
from app.core.enums import Role
from app.core.rate_limit import RateLimiter, build_policies
from app.core.security import create_access_token
from app.db import build_engine, get_session
from app.deps import get_mailer
from app.main import create_app
from app.models.user import User
from tests.support.database import scratch_database
from tests.support.factories import RecordingMailer, make_user


@dataclass
class Parallel:
    app: FastAPI
    engine: Engine
    factory: sessionmaker[Session]
    mailer: RecordingMailer
    settings: Settings

    def make(self, role: Role = Role.STAFF, **kwargs: Any) -> User:
        with self.factory() as session:
            user = make_user(session, role, **kwargs)
            session.commit()
            return user

    def headers(self, user: User) -> dict[str, str]:
        token = create_access_token(
            user.id,
            secret_key=self.settings.secret_key.get_secret_value(),
            now=Clock().now(),
            ttl_seconds=self.settings.access_token_ttl_seconds,
        )
        return {"Authorization": f"Bearer {token}"}

    def scalar(self, sql: str, **params: Any) -> Any:
        from sqlalchemy import text

        with self.factory() as session:
            return session.execute(text(sql), params).scalar_one()

    def run(
        self, calls: list[Callable[[httpx2.AsyncClient], Coroutine[Any, Any, httpx2.Response]]]
    ) -> list[httpx2.Response]:
        """Fire every call at once and return the responses in order."""

        async def go() -> list[httpx2.Response]:
            transport = httpx2.ASGITransport(app=self.app)
            async with httpx2.AsyncClient(transport=transport, base_url="http://test") as client:
                gate = asyncio.Event()

                async def released(
                    call: Callable[[httpx2.AsyncClient], Coroutine[Any, Any, httpx2.Response]],
                ) -> httpx2.Response:
                    await gate.wait()
                    return await call(client)

                tasks = [asyncio.create_task(released(call)) for call in calls]
                await asyncio.sleep(0.05)
                gate.set()
                return list(await asyncio.gather(*tasks))

        return asyncio.run(go())


@contextmanager
def parallel_app(settings: Settings, rate_limits: dict[str, str] | None = None) -> Iterator[Parallel]:
    with scratch_database(settings) as db:
        engine = build_engine(db.app_url, settings)
        factory = sessionmaker(bind=engine, expire_on_commit=False)
        app = create_app()
        if rate_limits:  # a test about something other than throttling raises the limits it would otherwise trip
            app.state.rate_limiter = RateLimiter(Clock(), build_policies(rate_limits))
        mailer = RecordingMailer()

        def session_per_request() -> Iterator[Session]:
            with factory() as session:
                yield session

        app.dependency_overrides[get_session] = session_per_request
        app.dependency_overrides[get_mailer] = lambda: mailer
        try:
            yield Parallel(app, engine, factory, mailer, settings)
        finally:
            engine.dispose()
