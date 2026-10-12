import time
from datetime import UTC, datetime, timedelta

import jwt
import pytest

from app.core.crypto import FieldCipher
from app.core.errors import UnauthenticatedError
from app.core.security import (
    Passwords,
    create_access_token,
    hash_token,
    new_secret_token,
    password_problem,
    read_access_token,
    same_secret,
)

KEY = "unit-test-secret-key-with-enough-length-0123456789"
NOW = datetime(2026, 10, 12, 14, 5, tzinfo=UTC)


@pytest.fixture(scope="module")
def passwords() -> Passwords:
    return Passwords(time_cost=1, memory_cost_kib=1024, parallelism=1)


# Passwords -----------------------------------------------------------------------------------------------------------


def test_hashes_are_argon2id_and_salted(passwords: Passwords) -> None:
    first = passwords.hash("a long enough password")
    assert first.startswith("$argon2id$")
    assert first != passwords.hash("a long enough password")


def test_verify_accepts_only_the_right_password(passwords: Passwords) -> None:
    stored = passwords.hash("a long enough password")
    assert passwords.verify(stored, "a long enough password")
    assert not passwords.verify(stored, "a long enough passwordX")
    assert not passwords.verify(stored, "")


def test_a_missing_hash_never_verifies_but_still_does_the_work(passwords: Passwords) -> None:
    assert not passwords.verify(None, "anything")
    assert not passwords.verify("not-a-hash", "anything")


def test_unknown_accounts_cost_about_what_wrong_passwords_cost() -> None:
    """Same argon2 work either way, so timing does not reveal whether an email exists. Compared on realistic cost
    settings, taking the fastest of several runs of each to ignore scheduling noise."""
    realistic = Passwords(time_cost=2, memory_cost_kib=19_456, parallelism=1)
    stored = realistic.hash("the real password")

    def fastest(hash_to_check: str | None) -> float:
        best = float("inf")
        for _ in range(6):
            started = time.perf_counter()
            realistic.verify(hash_to_check, "a wrong guess")
            best = min(best, time.perf_counter() - started)
        return best

    known, unknown = fastest(stored), fastest(None)
    assert unknown > known * 0.6
    assert unknown < known * 1.7


def test_a_hash_made_with_weaker_settings_is_marked_for_rehash(passwords: Passwords) -> None:
    stronger = Passwords(time_cost=2, memory_cost_kib=2048, parallelism=1)
    assert stronger.needs_rehash(passwords.hash("a long enough password"))
    assert not passwords.needs_rehash(passwords.hash("a long enough password"))


@pytest.mark.parametrize(
    ("password", "email", "problem"),
    [
        ("short", None, "at least"),
        ("x" * 129, None, "at most"),
        ("aaaaaaaaaaaa", None, "repetitive"),
        ("ayesha@daftar.pk", "Ayesha@Daftar.pk", "email"),
    ],
)
def test_weak_passwords_are_refused_with_a_reason(password: str, email: str | None, problem: str) -> None:
    assert problem in (password_problem(password, email) or "")


def test_a_long_plain_phrase_is_acceptable() -> None:
    assert password_problem("correct horse battery staple", "a@daftar.pk") is None


# Tokens --------------------------------------------------------------------------------------------------------------


def test_secret_tokens_are_long_and_unique_and_hash_stably() -> None:
    tokens = {new_secret_token() for _ in range(100)}
    assert len(tokens) == 100
    assert all(len(t) >= 40 for t in tokens)
    token = new_secret_token()
    assert hash_token(token) == hash_token(token)
    assert hash_token(token) != token
    assert len(hash_token(token)) == 64


def test_same_secret_compares_in_constant_time_and_refuses_empty() -> None:
    assert same_secret("abc", "abc")
    assert not same_secret("abc", "abd")
    assert not same_secret(None, "abc")
    assert not same_secret("abc", None)
    assert not same_secret("", "")


def test_an_access_token_round_trips() -> None:
    token = create_access_token(42, secret_key=KEY, now=NOW, ttl_seconds=900)
    assert read_access_token(token, secret_key=KEY, now=NOW) == 42
    assert read_access_token(token, secret_key=KEY, now=NOW + timedelta(seconds=899)) == 42


def test_an_access_token_expires_by_the_injected_clock() -> None:
    token = create_access_token(42, secret_key=KEY, now=NOW, ttl_seconds=900)
    with pytest.raises(UnauthenticatedError, match="expired"):
        read_access_token(token, secret_key=KEY, now=NOW + timedelta(seconds=900))


def test_a_tampered_or_foreign_token_is_refused() -> None:
    token = create_access_token(42, secret_key=KEY, now=NOW, ttl_seconds=900)
    with pytest.raises(UnauthenticatedError):
        read_access_token(token, secret_key=KEY + "x", now=NOW)
    with pytest.raises(UnauthenticatedError):
        read_access_token(token[:-2] + "aa", secret_key=KEY, now=NOW)
    with pytest.raises(UnauthenticatedError):
        read_access_token("not.a.token", secret_key=KEY, now=NOW)


def test_the_none_algorithm_and_wrong_claims_are_refused() -> None:
    claims = {"iss": "daftar", "typ": "access", "sub": "1", "iat": 1, "exp": 9_999_999_999}
    unsigned = jwt.encode(claims, key="", algorithm="none")
    with pytest.raises(UnauthenticatedError):
        read_access_token(unsigned, secret_key=KEY, now=NOW)
    wrong_issuer = jwt.encode({**claims, "iss": "someone-else"}, KEY, algorithm="HS256")
    with pytest.raises(UnauthenticatedError):
        read_access_token(wrong_issuer, secret_key=KEY, now=NOW)
    wrong_type = jwt.encode({**claims, "typ": "refresh"}, KEY, algorithm="HS256")
    with pytest.raises(UnauthenticatedError):
        read_access_token(wrong_type, secret_key=KEY, now=NOW)
    no_subject = jwt.encode({k: v for k, v in claims.items() if k != "sub"}, KEY, algorithm="HS256")
    with pytest.raises(UnauthenticatedError):
        read_access_token(no_subject, secret_key=KEY, now=NOW)


# Field encryption ----------------------------------------------------------------------------------------------------


def test_field_encryption_round_trips_and_hides_the_value() -> None:
    cipher = FieldCipher(KEY)
    stored = cipher.encrypt("PK36SCBL0000001123456702")
    assert "PK36" not in stored
    assert cipher.decrypt(stored) == "PK36SCBL0000001123456702"
    assert cipher.encrypt("PK36SCBL0000001123456702") != stored  # a fresh nonce each time


def test_field_decryption_fails_under_another_key() -> None:
    stored = FieldCipher(KEY).encrypt("PK36SCBL0000001123456702")
    with pytest.raises(ValueError, match="cannot be decrypted"):
        FieldCipher(KEY + "x").decrypt(stored)
