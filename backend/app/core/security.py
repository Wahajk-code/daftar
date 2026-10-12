"""Passwords, access tokens and one-time tokens. Nothing here touches the database or FastAPI."""

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta

import jwt
from argon2 import PasswordHasher, Type
from argon2.exceptions import InvalidHashError, VerificationError

from app.core.clock import require_utc
from app.core.errors import UnauthenticatedError

ISSUER = "daftar"
ACCESS_TYPE = "access"
MIN_PASSWORD_LENGTH = 10
MAX_PASSWORD_LENGTH = 128


class Passwords:
    """argon2id. An unknown account is checked against a dummy hash made with the same parameters, so the work done
    (and so the time taken) is the same whether or not the email exists."""

    def __init__(self, *, time_cost: int, memory_cost_kib: int, parallelism: int) -> None:
        self._hasher = PasswordHasher(
            time_cost=time_cost, memory_cost=memory_cost_kib, parallelism=parallelism, type=Type.ID
        )
        self._dummy_hash = self._hasher.hash(secrets.token_urlsafe(16))

    def hash(self, password: str) -> str:
        return self._hasher.hash(password)

    def verify(self, stored_hash: str | None, password: str) -> bool:
        """True only for a real hash that matches. With no hash, burn the same time on the dummy and return False."""
        target = stored_hash or self._dummy_hash
        try:
            matched = self._hasher.verify(target, password)
        except (VerificationError, InvalidHashError):
            return False
        return matched and stored_hash is not None

    def needs_rehash(self, stored_hash: str) -> bool:
        return self._hasher.check_needs_rehash(stored_hash)


def password_problem(password: str, email: str | None = None) -> str | None:
    """Why a new password is unacceptable, or None. Length, not composition rules: long phrases beat symbols."""
    if len(password) < MIN_PASSWORD_LENGTH:
        return f"Use at least {MIN_PASSWORD_LENGTH} characters."
    if len(password) > MAX_PASSWORD_LENGTH:
        return f"Use at most {MAX_PASSWORD_LENGTH} characters."
    if len(set(password)) < 4:
        return "Use a less repetitive password."
    if email and password.lower() == email.lower():
        return "The password must not be your email address."
    return None


def new_secret_token() -> str:
    """256 bits of randomness, URL safe. Handed to the user once; only its hash is stored."""
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    """SHA-256 is enough for a token that is already 256 random bits: there is nothing to brute-force."""
    return hashlib.sha256(token.encode()).hexdigest()


def same_secret(supplied: str | None, expected: str | None) -> bool:
    if not supplied or not expected:
        return False
    return hmac.compare_digest(supplied.encode(), expected.encode())


def create_access_token(user_id: int, *, secret_key: str, now: datetime, ttl_seconds: int) -> str:
    issued = require_utc(now)
    claims = {
        "iss": ISSUER,
        "typ": ACCESS_TYPE,
        "sub": str(user_id),
        "iat": int(issued.timestamp()),
        "exp": int((issued + timedelta(seconds=ttl_seconds)).timestamp()),
    }
    return jwt.encode(claims, secret_key, algorithm="HS256")


def read_access_token(token: str, *, secret_key: str, now: datetime) -> int:
    """The user id in a valid, unexpired access token. Expiry is judged against the injected clock, not the system's."""
    try:
        claims = jwt.decode(
            token,
            secret_key,
            algorithms=["HS256"],
            issuer=ISSUER,
            options={"require": ["exp", "iat", "sub", "iss"], "verify_exp": False, "verify_iat": False},
        )
        expired = int(claims["exp"]) <= int(require_utc(now).timestamp())
        if claims.get("typ") != ACCESS_TYPE:
            raise UnauthenticatedError("Sign in to continue.")
        user_id = int(claims["sub"])
    except (jwt.PyJWTError, ValueError, KeyError, TypeError) as exc:
        raise UnauthenticatedError("Sign in to continue.") from exc
    if expired:
        raise UnauthenticatedError("Your session has expired. Sign in again.")
    return user_id
