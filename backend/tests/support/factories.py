"""Builders for the rows tests need. Passwords are hashed once per run, not once per user."""

import itertools
import re
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.config import Settings
from app.core.enums import Role
from app.core.mail import EmailMessage, Mailer
from app.core.security import create_access_token
from app.deps import get_passwords
from app.models.user import User

TEST_PASSWORD = "correct horse battery staple"
_counter = itertools.count(1)
_cached_hash: dict[str, str] = {}


def password_hash(password: str = TEST_PASSWORD) -> str:
    if password not in _cached_hash:
        _cached_hash[password] = get_passwords().hash(password)
    return _cached_hash[password]


def make_user(
    session: Session,
    role: Role = Role.STAFF,
    *,
    email: str | None = None,
    full_name: str | None = None,
    active: bool = True,
    password: str = TEST_PASSWORD,
    now: datetime | None = None,
) -> User:
    number = next(_counter)
    user = User(
        email=email or f"{role.value}{number}@daftar.test",
        full_name=full_name or f"{role.value.capitalize()} {number}",
        password_hash=password_hash(password),
        role=role,
        is_active=active,
    )
    if now is not None:
        user.created_at = now
        user.updated_at = now
    session.add(user)
    session.flush()
    return user


def bearer(user: User, settings: Settings, now: datetime) -> dict[str, str]:
    token = create_access_token(
        user.id,
        secret_key=settings.secret_key.get_secret_value(),
        now=now,
        ttl_seconds=settings.access_token_ttl_seconds,
    )
    return {"Authorization": f"Bearer {token}"}


class RecordingMailer(Mailer):
    """Keeps what would have been sent, so a test can read the link out of it."""

    def __init__(self) -> None:
        self.sent: list[EmailMessage] = []

    def send(self, message: EmailMessage) -> None:
        self.sent.append(message)

    def to(self, address: str) -> list[EmailMessage]:
        return [m for m in self.sent if m.to == address]

    def token_for(self, address: str) -> str:
        """The single-use token in the most recent email to this address."""
        message = self.to(address)[-1]
        match = re.search(r"token=([A-Za-z0-9_%-]+)", message.body)
        assert match, message.body
        return match.group(1)


def error_code(response: Any) -> str:
    return str(response.json()["code"])
