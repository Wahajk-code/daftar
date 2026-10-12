"""Pieces every master-data service shares: the version check, audit snapshots and the reauthentication step."""

from collections.abc import Iterable
from typing import Any, Protocol

from sqlalchemy.orm import Session

from app.core.errors import ReauthFailedError, VersionConflictError
from app.core.principal import Principal
from app.core.rate_limit import RateLimiter
from app.core.security import Passwords
from app.models.base import JsonDict
from app.repositories import users as user_repository


class Versioned(Protocol):
    id: int
    version: int


def check_version(row: Versioned, expected: int) -> None:
    """Optimistic locking: refuse a change made against a copy that is no longer current."""
    if row.version != expected:
        raise VersionConflictError("Someone else changed this record. Reload it and try again.")


def snapshot(row: object, fields: Iterable[str]) -> JsonDict:
    """The named fields of a row as plain JSON, for the audit log's before and after."""
    values: dict[str, Any] = {}
    for name in fields:
        value = getattr(row, name)
        values[name] = (
            value.value if hasattr(value, "value") else (value.isoformat() if hasattr(value, "isoformat") else value)
        )
    return values


def changed(before: JsonDict, after: JsonDict) -> tuple[JsonDict, JsonDict]:
    """Only the fields that differ, from both sides."""
    keys = [key for key in after if before.get(key) != after[key]]
    return {key: before.get(key) for key in keys}, {key: after[key] for key in keys}


def reauthenticate(
    session: Session, passwords: Passwords, limiter: RateLimiter, principal: Principal, password: str
) -> None:
    """Ask for the password again before a sensitive change. Throttled per user and counted before the check."""
    ticket = limiter.hit(("reauth_user", str(principal.id)))
    user = user_repository.get(session, principal.id)
    if user is None or not passwords.verify(user.password_hash, password):
        raise ReauthFailedError("The password you entered is incorrect.")
    limiter.refund(ticket)
