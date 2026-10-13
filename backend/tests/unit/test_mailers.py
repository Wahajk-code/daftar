"""The two mail transports. The real SMTP one runs against a local server; a failure is logged and never raised."""

import logging
import smtplib
from email.utils import formataddr
from typing import Any

import pytest
from pydantic import ValidationError

from app.config import Settings
from app.core.mail import ConsoleMailer, EmailMessage, SmtpMailer, build_mailer
from tests.support.mailservers import smtp_server
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


def test_a_styled_message_goes_out_as_text_and_html_together() -> None:
    styled = EmailMessage(kind="invite", to="a@daftar.pk", subject="Hi", body="Plain words.", html="<p>Styled</p>")
    with smtp_server() as inbox:
        SmtpMailer("127.0.0.1", inbox.port, SENDER, timeout_seconds=5).send(styled)
    raw = inbox.messages[0]
    assert "multipart/alternative" in raw
    assert "Plain words." in raw
    assert "<p>Styled</p>" in raw


def test_the_smtp_transport_is_chosen_by_the_setting() -> None:
    with smtp_server() as inbox:
        mailer = build_mailer(settings(mail_backend="smtp", smtp_host="127.0.0.1", smtp_port=inbox.port))
        assert isinstance(mailer, SmtpMailer)
        mailer.send(MESSAGE)
    assert len(inbox.messages) == 1


def test_a_login_needs_the_connection_to_be_upgraded_first_and_never_sends_the_password_in_the_clear() -> None:
    with smtp_server() as inbox:
        mailer = SmtpMailer("127.0.0.1", inbox.port, SENDER, 5, user="me@gmail.com", password="app-password")
        with pytest.raises(smtplib.SMTPNotSupportedError, match="STARTTLS"):
            mailer.send(MESSAGE)
    assert inbox.messages == []


def test_a_failure_is_logged_and_never_raised(caplog: pytest.LogCaptureFixture) -> None:
    with smtp_server() as inbox:
        port = inbox.port
    mailer = SmtpMailer("127.0.0.1", port, SENDER, timeout_seconds=2)
    with pytest.raises(OSError, match=r"refused|Connect"):  # the raw transport reports the failure...
        mailer.send(MESSAGE)
    with caplog.at_level(logging.ERROR, logger="app.mail"):
        mailer.send_safely(MESSAGE)  # ...and the wrapper the app uses swallows it
    failures = [r for r in caplog.records if r.message == "email failed"]
    assert len(failures) == 1
    assert failures[0].__dict__["email_kind"] == "needs_approval"


def test_the_log_line_for_a_failure_does_not_carry_the_message_text(caplog: pytest.LogCaptureFixture) -> None:
    secret = EmailMessage(kind="password_reset", to="a@daftar.pk", subject="Reset", body="https://x/r?token=SECRET123")
    with smtp_server() as inbox:
        port = inbox.port
    with caplog.at_level(logging.ERROR, logger="app.mail"):
        SmtpMailer("127.0.0.1", port, SENDER, timeout_seconds=2).send_safely(secret)
    assert any(r.message == "email failed" for r in caplog.records)
    assert "SECRET123" not in caplog.text


def test_a_login_makes_smtp_the_transport_and_an_explicit_choice_wins() -> None:
    assert settings().mail_transport == "console"
    assert settings(smtp_user="info@visionpme.ca", smtp_pass="x").mail_transport == "smtp"
    assert settings(smtp_user="info@visionpme.ca", smtp_pass="x", mail_backend="console").mail_transport == "console"
    assert settings(mail_backend="smtp").mail_transport == "smtp"


def test_empty_values_in_an_env_file_mean_not_set() -> None:
    configured = settings(smtp_user="", smtp_pass="", mail_backend="")
    assert (configured.smtp_user, configured.smtp_pass, configured.mail_backend) == (None, None, None)
    assert configured.mail_transport == "console"


def test_the_retired_mail_api_setting_does_not_stop_the_api_starting() -> None:
    assert settings(mail_backend="resend").mail_transport == "console"
    assert settings(mail_backend="resend", smtp_user="info@visionpme.ca", smtp_pass="x").mail_transport == "smtp"


def test_google_and_gmail_are_names_for_smtp() -> None:
    assert settings(mail_backend="google").mail_transport == "smtp"
    assert settings(mail_backend=" Gmail ").mail_transport == "smtp"


def test_a_login_needs_its_password() -> None:
    with pytest.raises(ValidationError, match="SMTP_PASS"):
        settings(smtp_user="info@visionpme.ca")


def test_the_sender_is_built_from_the_name_and_the_address_even_when_the_name_arrives_with_quotes() -> None:
    configured = settings(smtp_from_email="info@visionpme.ca", smtp_from_name="'\"Équipe Vision PME\"'")
    assert configured.smtp_from_name == "Équipe Vision PME"
    assert configured.mail_from == formataddr(("Équipe Vision PME", "info@visionpme.ca"))
    assert configured.mail_from.endswith("<info@visionpme.ca>")
    assert configured.mail_from.isascii()  # the accent is encoded in the header, so any server accepts it
    with pytest.raises(ValidationError, match="SMTP_FROM_EMAIL"):
        settings(smtp_from_email="not-an-address")


def test_an_accented_sender_name_reaches_the_server_encoded() -> None:
    configured = settings(smtp_from_email="info@visionpme.ca", smtp_from_name="Équipe Vision PME")
    with smtp_server() as inbox:
        SmtpMailer("127.0.0.1", inbox.port, configured.mail_from, timeout_seconds=5).send(MESSAGE)
    raw = inbox.messages[0]
    assert "<info@visionpme.ca>" in raw
    assert "=?utf-8?" in raw.split("Subject:")[0].lower()


def test_production_refuses_the_console_transport() -> None:
    with pytest.raises(ValidationError, match="SMTP"):
        make(mail_backend="console")
    assert make(smtp_user="info@visionpme.ca", smtp_pass="app-password").mail_transport == "smtp"


def test_every_template_has_a_styled_version_that_escapes_what_it_is_given_and_keeps_the_link() -> None:
    from app.core import mail_templates as templates

    link = "http://localhost:3001/accept-invite?token=abc&x=1"
    invite = templates.invite(
        to="a@daftar.pk", role="Accountant", link=link, expires="20 Oct", invited_by="<b>Nadia</b>"
    )
    assert invite.html is not None
    assert invite.body
    assert "&lt;b&gt;Nadia&lt;/b&gt;" in invite.html
    assert "<b>Nadia</b>" not in invite.html
    assert 'href="http://localhost:3001/accept-invite?token=abc&amp;x=1"' in invite.html
    rejected = templates.decided(
        to="a@daftar.pk",
        name="Bilal",
        label="Expense 42",
        summary="PKR 1.00",
        outcome="rejected",
        decided_by="Ayesha",
        when="now",
        comment="Unclear <receipt>",
        link=link,
    )
    assert rejected.html is not None
    assert "Unclear &lt;receipt&gt;" in rejected.html
    assert all(
        m.html and m.html.startswith("<!doctype html>")
        for m in (
            templates.password_reset(to="a@daftar.pk", link=link, expires="x", started_by_admin=True),
            templates.bank_account_changed(
                to="a@daftar.pk", vendor="V", changed_by="U", when="w", masked_account="****1"
            ),
            templates.needs_approval(to="a@daftar.pk", name="N", label="L", summary="S", submitted_by="B", link=link),
        )
    )
