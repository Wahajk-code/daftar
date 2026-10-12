"""Stories A1 (sign in, tokens, throttling) and I1 (self-service password reset)."""

from collections.abc import Callable
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.enums import Role
from app.models.user import User
from tests.support.clock import FakeClock
from tests.support.factories import TEST_PASSWORD, RecordingMailer

BFF_SECRET = "test-bff-secret-for-automated-tests-only"
Make = Callable[..., User]


def login(client: TestClient, email: str, password: str = TEST_PASSWORD, **headers: str) -> Any:
    return client.post("/api/v1/auth/login", json={"email": email, "password": password}, headers=headers)


def refresh(client: TestClient, token: str) -> Any:
    return client.post("/api/v1/auth/refresh", json={"refresh_token": token})


def bearer(pair: dict[str, Any]) -> dict[str, str]:
    return {"Authorization": f"Bearer {pair['access_token']}"}


def audit_actions(db: Session) -> list[str]:
    return [row[0] for row in db.execute(text("SELECT action FROM audit_events ORDER BY id"))]


# Signing in ----------------------------------------------------------------------------------------------------------


def test_a1_login_returns_tokens_and_the_user(client: TestClient, make: Make) -> None:
    user = make(Role.ACCOUNTANT)
    response = login(client, user.email)
    assert response.status_code == 200
    pair = response.json()
    assert pair["token_type"] == "bearer"
    assert pair["expires_in"] == 900
    assert pair["user"] == {"id": user.id, "email": user.email, "full_name": user.full_name, "role": "accountant"}
    assert client.get("/api/v1/me", headers=bearer(pair)).json()["email"] == user.email


def test_a1_a_wrong_password_and_an_unknown_email_look_identical(client: TestClient, make: Make) -> None:
    user = make()
    wrong_password = login(client, user.email, "not the password at all")
    unknown_email = login(client, "nobody@daftar.test")

    def shape(response: Any) -> tuple[int, dict[str, Any]]:
        body = response.json()
        body.pop("correlation_id")
        return response.status_code, body

    assert shape(wrong_password) == shape(unknown_email)
    assert wrong_password.status_code == 401
    assert wrong_password.json()["code"] == "INVALID_CREDENTIALS"
    assert user.email not in wrong_password.text


def test_a1_a_deactivated_user_gets_the_same_generic_answer(client: TestClient, make: Make) -> None:
    gone = make(active=False)
    response = login(client, gone.email)
    assert response.status_code == 401
    assert response.json()["code"] == "INVALID_CREDENTIALS"


def test_a1_email_spelling_does_not_matter(client: TestClient, make: Make) -> None:
    user = make(email="ayesha@daftar.test")
    assert login(client, "  AYESHA@Daftar.TEST ").status_code == 200
    assert user.id


def test_a1_the_access_token_lasts_fifteen_minutes(client: TestClient, make: Make, clock: FakeClock) -> None:
    pair = login(client, make().email).json()
    clock.advance(seconds=899)
    assert client.get("/api/v1/me", headers=bearer(pair)).status_code == 200
    clock.advance(seconds=1)
    assert client.get("/api/v1/me", headers=bearer(pair)).status_code == 401


@pytest.mark.parametrize("header", [None, "Bearer", "Bearer not-a-token", "Basic abc", "bearer "])
def test_a1_a_missing_or_malformed_token_is_a_401(client: TestClient, header: str | None) -> None:
    headers = {"Authorization": header} if header else {}
    response = client.get("/api/v1/me", headers=headers)
    assert response.status_code == 401
    assert response.json()["code"] == "UNAUTHENTICATED"


def test_a1_a_live_token_stops_working_the_moment_the_user_is_deactivated(
    client: TestClient, make: Make, db_session: Session
) -> None:
    user = make()
    pair = login(client, user.email).json()
    user.is_active = False
    db_session.commit()
    assert client.get("/api/v1/me", headers=bearer(pair)).status_code == 401


def test_a1_a_role_change_applies_on_the_next_request(client: TestClient, make: Make, db_session: Session) -> None:
    user = make(Role.ADMIN)
    make(Role.ADMIN)  # a second Admin, so the demotion below is allowed by the database
    pair = login(client, user.email).json()
    assert client.get("/api/v1/users", headers=bearer(pair)).status_code == 200
    user.role = Role.STAFF
    db_session.commit()
    assert client.get("/api/v1/users", headers=bearer(pair)).status_code == 403


def test_a1_failed_and_successful_sign_ins_are_audited_without_the_email(
    client: TestClient, make: Make, db_session: Session
) -> None:
    user = make()
    login(client, user.email, "wrong wrong wrong")
    login(client, "nobody@daftar.test")
    login(client, user.email)
    assert audit_actions(db_session) == ["auth.login_failed", "auth.login_failed", "auth.login"]
    stored = db_session.execute(
        text("SELECT string_agg(coalesce(after::text, ''), ' ') FROM audit_events")
    ).scalar_one()
    assert "nobody@daftar.test" not in (stored or "")


# Refresh tokens ------------------------------------------------------------------------------------------------------


def test_a1_refresh_rotates_the_pair(client: TestClient, make: Make) -> None:
    first = login(client, make().email).json()
    second = refresh(client, first["refresh_token"]).json()
    assert second["refresh_token"] != first["refresh_token"]
    assert second["access_token"]
    assert client.get("/api/v1/me", headers=bearer(second)).status_code == 200


def test_a1_reusing_a_consumed_refresh_token_ends_every_session(
    client: TestClient, make: Make, db_session: Session
) -> None:
    user = make()
    first = login(client, user.email).json()
    other_device = login(client, user.email).json()
    second = refresh(client, first["refresh_token"]).json()
    # The old token is presented again: someone is replaying it.
    assert refresh(client, first["refresh_token"]).status_code == 401
    # Everything this user held is now dead, including the legitimate newest token and the other device.
    assert refresh(client, second["refresh_token"]).status_code == 401
    assert refresh(client, other_device["refresh_token"]).status_code == 401
    assert "auth.refresh_reuse_detected" in audit_actions(db_session)


def test_a1_reuse_by_one_user_does_not_touch_another(client: TestClient, make: Make) -> None:
    first = login(client, make().email).json()
    bystander = login(client, make().email).json()
    refresh(client, first["refresh_token"])
    refresh(client, first["refresh_token"])  # reuse
    assert refresh(client, bystander["refresh_token"]).status_code == 200


def test_a1_a_refresh_token_expires_after_seven_days(client: TestClient, make: Make, clock: FakeClock) -> None:
    pair = login(client, make().email).json()
    clock.advance(days=7, seconds=-1)
    renewed = refresh(client, pair["refresh_token"])
    assert renewed.status_code == 200
    clock.advance(days=7)
    assert refresh(client, renewed.json()["refresh_token"]).status_code == 401


def test_a1_an_unknown_refresh_token_is_a_plain_401(client: TestClient) -> None:
    assert refresh(client, "x" * 43).status_code == 401


def test_a1_a_deactivated_user_cannot_refresh(client: TestClient, make: Make, db_session: Session) -> None:
    user = make()
    pair = login(client, user.email).json()
    user.is_active = False
    db_session.commit()
    assert refresh(client, pair["refresh_token"]).status_code == 401


def test_a1_logout_ends_that_session_and_is_repeatable(client: TestClient, make: Make) -> None:
    pair = login(client, make().email).json()
    body = {"refresh_token": pair["refresh_token"]}
    assert client.post("/api/v1/auth/logout", json=body).status_code == 204
    assert client.post("/api/v1/auth/logout", json=body).status_code == 204
    assert refresh(client, pair["refresh_token"]).status_code == 401


def test_a1_a_refresh_token_is_stored_only_as_a_hash(client: TestClient, make: Make, db_session: Session) -> None:
    pair = login(client, make().email).json()
    stored = db_session.execute(text("SELECT string_agg(token_hash, ' ') FROM refresh_tokens")).scalar_one()
    assert pair["refresh_token"] not in stored
    assert len(stored.split()[0]) == 64


# Throttling ----------------------------------------------------------------------------------------------------------


def test_a1_the_sixth_attempt_is_throttled_even_with_the_right_password(
    client: TestClient, make: Make, clock: FakeClock
) -> None:
    user = make()
    for _ in range(5):
        assert login(client, user.email, "wrong wrong wrong").status_code == 401
    blocked = login(client, user.email, TEST_PASSWORD)  # the right password, but the attempt is not even checked
    assert blocked.status_code == 429
    assert blocked.json()["code"] == "RATE_LIMITED"
    assert int(blocked.headers["Retry-After"]) == 900
    clock.advance(seconds=899)
    assert login(client, user.email).status_code == 429
    clock.advance(seconds=1)  # the first failure has left the 15-minute window
    assert login(client, user.email).status_code == 200


def test_a1_successful_sign_ins_are_not_counted(client: TestClient, make: Make) -> None:
    user = make()
    assert all(login(client, user.email).status_code == 200 for _ in range(12))


def test_a1_unknown_emails_are_counted_like_real_ones(client: TestClient) -> None:
    for _ in range(5):
        assert login(client, "ghost@daftar.test").status_code == 401
    assert login(client, "ghost@daftar.test").status_code == 429


def test_a1_spelling_variants_of_an_email_share_one_counter(client: TestClient, make: Make) -> None:
    user = make(email="ayesha@daftar.test")
    for variant in ("ayesha@daftar.test", "AYESHA@daftar.test", " Ayesha@Daftar.Test ", "ayesha@daftar.test"):
        assert login(client, variant, "wrong wrong wrong").status_code == 401
    assert login(client, "ayesha@daftar.test", "wrong wrong wrong").status_code == 401
    assert login(client, " AYESHA@DAFTAR.TEST", TEST_PASSWORD).status_code == 429
    assert user.id


def test_a1_a_client_address_header_without_the_secret_is_ignored(client: TestClient) -> None:
    for number in range(20):
        # A different spoofed address and a different email each time: only the real connection address is counted.
        response = login(client, f"ghost{number}@daftar.test", **{"X-Daftar-Client-Ip": f"10.0.0.{number}"})
        assert response.status_code == 401
    assert login(client, "ghost99@daftar.test", **{"X-Daftar-Client-Ip": "10.9.9.9"}).status_code == 429


def test_a1_with_the_secret_each_browser_address_counts_separately(client: TestClient) -> None:
    for number in range(25):
        headers = {"X-Daftar-BFF-Secret": BFF_SECRET, "X-Daftar-Client-Ip": f"203.0.113.{number}"}
        assert login(client, f"ghost{number}@daftar.test", **headers).status_code == 401


def test_a1_a_wrong_secret_is_treated_like_no_secret(client: TestClient) -> None:
    for number in range(20):
        headers = {"X-Daftar-BFF-Secret": "guess", "X-Daftar-Client-Ip": f"203.0.113.{number}"}
        assert login(client, f"ghost{number}@daftar.test", **headers).status_code == 401
    headers = {"X-Daftar-BFF-Secret": "guess", "X-Daftar-Client-Ip": "203.0.113.200"}
    assert login(client, "ghost99@daftar.test", **headers).status_code == 429


def test_a1_failures_from_another_address_do_not_block_the_users_own(client: TestClient, make: Make) -> None:
    victim = make()
    attacker = {"X-Daftar-BFF-Secret": BFF_SECRET, "X-Daftar-Client-Ip": "198.51.100.7"}
    for _ in range(5):
        assert login(client, victim.email, "wrong wrong wrong", **attacker).status_code == 401
    assert login(client, victim.email, TEST_PASSWORD, **attacker).status_code == 429
    own = {"X-Daftar-BFF-Secret": BFF_SECRET, "X-Daftar-Client-Ip": "192.0.2.44"}
    assert login(client, victim.email, TEST_PASSWORD, **own).status_code == 200


def test_a1_the_per_email_cap_still_slows_a_distributed_guesser(client: TestClient, make: Make) -> None:
    """The residual the design accepts: 30 failures an hour for one email, from any addresses, then 429 for everyone."""
    victim = make()
    for number in range(30):
        headers = {"X-Daftar-BFF-Secret": BFF_SECRET, "X-Daftar-Client-Ip": f"203.0.113.{number}"}
        assert login(client, victim.email, "wrong wrong wrong", **headers).status_code == 401
    headers = {"X-Daftar-BFF-Secret": BFF_SECRET, "X-Daftar-Client-Ip": "192.0.2.1"}
    assert login(client, victim.email, TEST_PASSWORD, **headers).status_code == 429


def test_a1_the_per_user_safety_net_throttles_a_flood_of_authenticated_calls(
    client: TestClient, make: Make, auth: Callable[[User], dict[str, str]], clock: FakeClock
) -> None:
    headers = auth(make())
    assert all(client.get("/api/v1/me", headers=headers).status_code == 200 for _ in range(300))
    blocked = client.get("/api/v1/me", headers=headers)
    assert blocked.status_code == 429
    assert blocked.headers["Retry-After"] == "60"
    clock.advance(seconds=60)
    assert client.get("/api/v1/me", headers=headers).status_code == 200


# Password reset (I1) -------------------------------------------------------------------------------------------------


def forgot(client: TestClient, email: str, **headers: str) -> Any:
    return client.post("/api/v1/auth/forgot-password", json={"email": email}, headers=headers)


def reset(client: TestClient, token: str, password: str = "a brand new passphrase") -> Any:
    return client.post("/api/v1/auth/reset-password", json={"token": token, "new_password": password})


def test_i1_forgot_password_answers_the_same_for_known_and_unknown_emails(
    client: TestClient, make: Make, mailer: RecordingMailer
) -> None:
    user = make()
    known = forgot(client, user.email)
    unknown = forgot(client, "nobody@daftar.test")
    assert (known.status_code, known.json()) == (unknown.status_code, unknown.json()) == (202, {"status": "accepted"})
    assert len(mailer.sent) == 1
    assert mailer.sent[0].to == user.email


def test_i1_the_email_has_a_single_use_link_that_expires_in_thirty_minutes(
    client: TestClient, make: Make, mailer: RecordingMailer, clock: FakeClock
) -> None:
    user = make()
    forgot(client, user.email)
    message = mailer.sent[0]
    assert "reset-password?token=" in message.body
    assert "PKT" in message.body  # the expiry is shown in the display zone
    token = mailer.token_for(user.email)
    clock.advance(minutes=29, seconds=59)
    assert reset(client, token).status_code == 204


def test_i1_a_reset_link_expires(client: TestClient, make: Make, mailer: RecordingMailer, clock: FakeClock) -> None:
    user = make()
    forgot(client, user.email)
    clock.advance(minutes=30)
    response = reset(client, mailer.token_for(user.email))
    assert response.status_code == 400
    assert response.json()["code"] == "TOKEN_EXPIRED"


def test_i1_a_reset_link_works_once(client: TestClient, make: Make, mailer: RecordingMailer) -> None:
    user = make()
    forgot(client, user.email)
    token = mailer.token_for(user.email)
    assert reset(client, token).status_code == 204
    again = reset(client, token, "yet another passphrase")
    assert again.status_code == 400
    assert again.json()["code"] == "TOKEN_INVALID"


def test_i1_the_new_password_works_and_the_old_one_does_not(
    client: TestClient, make: Make, mailer: RecordingMailer
) -> None:
    user = make()
    forgot(client, user.email)
    reset(client, mailer.token_for(user.email), "a brand new passphrase")
    assert login(client, user.email, TEST_PASSWORD).status_code == 401
    assert login(client, user.email, "a brand new passphrase").status_code == 200


def test_i1_using_the_link_signs_the_user_out_everywhere(
    client: TestClient, make: Make, mailer: RecordingMailer
) -> None:
    user = make()
    session_one = login(client, user.email).json()
    session_two = login(client, user.email).json()
    forgot(client, user.email)
    reset(client, mailer.token_for(user.email))
    assert refresh(client, session_one["refresh_token"]).status_code == 401
    assert refresh(client, session_two["refresh_token"]).status_code == 401


def test_i1_a_weak_new_password_is_refused_and_does_not_burn_the_link(
    client: TestClient, make: Make, mailer: RecordingMailer
) -> None:
    user = make()
    forgot(client, user.email)
    token = mailer.token_for(user.email)
    weak = reset(client, token, "short")
    assert weak.status_code == 422
    assert weak.json()["errors"][0]["field"] == "new_password"
    assert reset(client, token, "a good long passphrase").status_code == 204


def test_i1_a_new_request_replaces_the_earlier_link(client: TestClient, make: Make, mailer: RecordingMailer) -> None:
    user = make()
    forgot(client, user.email)
    first = mailer.token_for(user.email)
    forgot(client, user.email)
    second = mailer.token_for(user.email)
    assert first != second
    assert reset(client, first).json()["code"] == "TOKEN_REVOKED"
    assert reset(client, second).status_code == 204


def test_i1_a_garbage_token_is_just_invalid(client: TestClient) -> None:
    response = reset(client, "z" * 43)
    assert response.status_code == 400
    assert response.json()["code"] == "TOKEN_INVALID"


def test_i1_a_deactivated_user_gets_no_email_and_the_same_reply(
    client: TestClient, make: Make, mailer: RecordingMailer
) -> None:
    gone = make(active=False)
    assert forgot(client, gone.email).status_code == 202
    assert mailer.sent == []


def test_i1_reset_tokens_are_stored_only_as_hashes(
    client: TestClient, make: Make, mailer: RecordingMailer, db_session: Session
) -> None:
    user = make()
    forgot(client, user.email)
    token = mailer.token_for(user.email)
    stored = db_session.execute(text("SELECT string_agg(token_hash, ' ') FROM auth_tokens")).scalar_one()
    assert token not in stored


def test_i1_forgot_password_is_throttled_per_email_and_per_address(client: TestClient, make: Make) -> None:
    user = make()
    assert all(forgot(client, user.email).status_code == 202 for _ in range(3))
    assert forgot(client, user.email).status_code == 429
    for number in range(7):  # ten requests an hour from one address in all, three already used
        assert forgot(client, f"other{number}@daftar.test").status_code == 202
    assert forgot(client, "another@daftar.test").status_code == 429


def test_i1_the_reset_confirmation_is_throttled_per_address(client: TestClient) -> None:
    for _ in range(10):
        assert reset(client, "z" * 43).status_code == 400
    assert reset(client, "z" * 43).status_code == 429


def test_i1_a_failed_mail_provider_never_fails_the_request(
    client: TestClient, make: Make, app: Any, caplog: pytest.LogCaptureFixture
) -> None:
    from app.core.mail import EmailMessage, Mailer
    from app.deps import get_mailer

    class Broken(Mailer):
        def send(self, message: EmailMessage) -> None:
            raise ConnectionError("the provider is down")

    app.dependency_overrides[get_mailer] = Broken
    user = make()
    with caplog.at_level("ERROR", logger="app.mail"):
        assert forgot(client, user.email).status_code == 202
    assert any(r.exc_info for r in caplog.records)
    assert user.email not in caplog.text  # the failure is logged without the recipient


# Changing your own password ------------------------------------------------------------------------------------------


def test_a1_changing_your_password_needs_the_current_one_and_ends_all_sessions(client: TestClient, make: Make) -> None:
    user = make()
    pair = login(client, user.email).json()
    wrong = client.post(
        "/api/v1/me/password",
        json={"current_password": "not it at all", "new_password": "a brand new passphrase"},
        headers=bearer(pair),
    )
    assert wrong.status_code == 403
    assert wrong.json()["code"] == "REAUTH_FAILED"
    right = client.post(
        "/api/v1/me/password",
        json={"current_password": TEST_PASSWORD, "new_password": "a brand new passphrase"},
        headers=bearer(pair),
    )
    assert right.status_code == 204
    assert refresh(client, pair["refresh_token"]).status_code == 401
    assert login(client, user.email, "a brand new passphrase").status_code == 200


def test_a1_password_checks_for_a_sensitive_change_are_throttled(client: TestClient, make: Make) -> None:
    pair = login(client, make().email).json()
    body = {"current_password": "not it at all", "new_password": "a brand new passphrase"}
    for _ in range(5):
        assert client.post("/api/v1/me/password", json=body, headers=bearer(pair)).status_code == 403
    assert client.post("/api/v1/me/password", json=body, headers=bearer(pair)).status_code == 429
