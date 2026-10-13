"""The three mail transports. The real ones run against local servers; a provider failure is logged and never raised."""

import logging
from typing import Any

import pytest
from pydantic import ValidationError

from app.config import Settings
from app.core.mail import ConsoleMailer, EmailMessage, ResendMailer, SmtpMailer, build_mailer
from tests.support.mailservers import resend_server, smtp_server
from tests.unit.test_config import STRONG_KEY, URL, make

SENDER = "Daftar <no-reply@daftar.pk>"
MESSAGE = EmailMessage(
    kind="needs_approval", to="approver@daftar.pk", subject="Needs your approval: Expense 7", body="Open it."
)


def settings(**overrides: Any) -> Settings:
    return Settings(**{"secret_key": STRONG_KEY, "database_url": URL, "environment": "development", **overrides})


def test_the_default_transport_is_the_console() -> None:
    assert isinstance(build_mailer(settings()), ConsoleMailer)


def test_smtp_delivers_the_message_to_the_server() -> None:
    with smtp_server() as inbox:
        SmtpMailer("127.0.0.1", inbox.port, SENDER, timeout_seconds=5).send(MESSAGE)
    assert len(inbox.messages) == 1
    raw = inbox.messages[0]
    assert "Subject: Needs your approval: Expense 7" in raw
    assert f"From: {SENDER}" in raw
    assert "To: approver@daftar.pk" in raw
    assert "Open it." in raw
    assert inbox.envelopes[0][1] == ["<approver@daftar.pk>"]


def test_the_smtp_transport_is_chosen_by_the_setting() -> None:
    with smtp_server() as inbox:
        mailer = build_mailer(settings(mail_backend="smtp", smtp_host="127.0.0.1", smtp_port=inbox.port))
        assert isinstance(mailer, SmtpMailer)
        mailer.send(MESSAGE)
    assert len(inbox.messages) == 1


def test_resend_gets_a_bearer_key_and_the_documented_json_body() -> None:
    with resend_server() as calls:
        ResendMailer("re_test_key", SENDER, 5, endpoint=calls.url).send(MESSAGE)
    (request,) = calls.requests
    assert request["path"] == "/emails"
    assert request["headers"]["authorization"] == "Bearer re_test_key"
    assert request["headers"]["content-type"] == "application/json"
    assert request["json"] == {
        "from": SENDER,
        "to": ["approver@daftar.pk"],
        "subject": "Needs your approval: Expense 7",
        "text": "Open it.",
    }


def test_the_resend_transport_is_chosen_by_the_setting() -> None:
    assert isinstance(build_mailer(settings(mail_backend="resend", resend_api_key="re_test_key")), ResendMailer)


def test_a_provider_that_refuses_is_logged_and_never_raised(caplog: pytest.LogCaptureFixture) -> None:
    with resend_server(status=500) as calls:
        mailer = ResendMailer("re_test_key", SENDER, 5, endpoint=calls.url)
        with pytest.raises(OSError, match="500"):  # the raw transport reports the failure...
            mailer.send(MESSAGE)
        with caplog.at_level(logging.ERROR, logger="app.mail"):
            mailer.send_safely(MESSAGE)  # ...and the wrapper the app uses swallows it
    failures = [r for r in caplog.records if r.message == "email failed"]
    assert len(failures) == 1
    assert failures[0].__dict__["email_kind"] == "needs_approval"


def test_a_server_that_is_not_there_is_logged_and_never_raised(caplog: pytest.LogCaptureFixture) -> None:
    with smtp_server() as inbox:
        port = inbox.port
    with caplog.at_level(logging.ERROR, logger="app.mail"):
        SmtpMailer("127.0.0.1", port, SENDER, timeout_seconds=2).send_safely(MESSAGE)
    assert any(r.message == "email failed" for r in caplog.records)


def test_the_log_line_for_a_failure_does_not_carry_the_message_text(caplog: pytest.LogCaptureFixture) -> None:
    secret = EmailMessage(kind="password_reset", to="a@daftar.pk", subject="Reset", body="https://x/r?token=SECRET123")
    with resend_server(status=500) as calls, caplog.at_level(logging.ERROR, logger="app.mail"):
        ResendMailer("re_test_key", SENDER, 5, endpoint=calls.url).send_safely(secret)
    assert "SECRET123" not in caplog.text


def test_resend_needs_its_key() -> None:
    with pytest.raises(ValidationError, match="RESEND_API_KEY"):
        settings(mail_backend="resend")
    with pytest.raises(ValidationError, match="RESEND_API_KEY"):
        settings(mail_backend="resend", resend_api_key="  ")


def test_production_refuses_the_console_transport() -> None:
    with pytest.raises(ValidationError, match="SMTP or Resend"):
        make(mail_backend="console")
    assert make(mail_backend="resend", resend_api_key="re_live").mail_backend == "resend"
