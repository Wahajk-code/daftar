"""Outgoing email. Services add messages to an Outbox; the router sends them in the background once the service has
returned, which is after the commit. A provider failure is logged and never raised.

Three transports, chosen by the MAIL_BACKEND setting: the console (development), SMTP (Mailpit locally) and Resend
(deployed). Both real ones use only the standard library."""

import json
import logging
import smtplib
import urllib.error
import urllib.request
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from email.message import EmailMessage as MimeMessage
from email.utils import formatdate, make_msgid

from app.config import Settings

logger = logging.getLogger("app.mail")


@dataclass(frozen=True)
class EmailMessage:
    kind: str  # the template, for example "invite"; the only thing logged about a message outside development
    to: str
    subject: str
    body: str


class Mailer(ABC):
    @abstractmethod
    def send(self, message: EmailMessage) -> None: ...

    def send_safely(self, message: EmailMessage) -> None:
        try:
            self.send(message)
        except Exception:
            logger.exception("email failed", extra={"email_kind": message.kind})


class ConsoleMailer(Mailer):
    """Development transport: the whole message goes to the log. Production never uses it."""

    def send(self, message: EmailMessage) -> None:
        logger.info(
            "email (console transport)",
            extra={"email_kind": message.kind, "to": message.to, "subject": message.subject, "body": message.body},
        )


class SmtpMailer(Mailer):
    """Plain SMTP without login or encryption: for Mailpit, which catches everything and delivers nothing."""

    def __init__(self, host: str, port: int, sender: str, timeout_seconds: int) -> None:
        self._host = host
        self._port = port
        self._sender = sender
        self._timeout = timeout_seconds

    def send(self, message: EmailMessage) -> None:
        mime = MimeMessage()
        mime["From"] = self._sender
        mime["To"] = message.to
        mime["Subject"] = message.subject
        mime["Date"] = formatdate(localtime=False)
        mime["Message-ID"] = make_msgid(domain="daftar.local")
        mime.set_content(message.body)
        with smtplib.SMTP(self._host, self._port, timeout=self._timeout) as connection:
            connection.send_message(mime)


RESEND_ENDPOINT = "https://api.resend.com/emails"


class ResendMailer(Mailer):
    """Resend's HTTP API: POST /emails with a bearer key, JSON body with from, to, subject and text. Any answer other
    than 2xx is an error (urllib raises for 4xx and 5xx)."""

    def __init__(self, api_key: str, sender: str, timeout_seconds: int, endpoint: str = RESEND_ENDPOINT) -> None:
        self._api_key = api_key
        self._sender = sender
        self._timeout = timeout_seconds
        self._endpoint = endpoint

    def send(self, message: EmailMessage) -> None:
        payload = json.dumps(
            {"from": self._sender, "to": [message.to], "subject": message.subject, "text": message.body}
        ).encode()
        request = urllib.request.Request(  # noqa: S310 - the endpoint is a constant https URL, or a local test server
            self._endpoint,
            data=payload,
            method="POST",
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
                "User-Agent": "daftar/1.0",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=self._timeout):  # noqa: S310
                pass
        except urllib.error.HTTPError as error:
            error.close()  # an error answer keeps its socket open until it is collected
            raise


def build_mailer(settings: Settings) -> Mailer:
    if settings.mail_backend == "smtp":
        return SmtpMailer(settings.smtp_host, settings.smtp_port, settings.mail_from, settings.mail_timeout_seconds)
    if settings.mail_backend == "resend":
        key = settings.resend_api_key
        assert key is not None  # Settings refuses to start without it
        return ResendMailer(key.get_secret_value(), settings.mail_from, settings.mail_timeout_seconds)
    return ConsoleMailer()


@dataclass
class Outbox:
    """Messages waiting for the commit. If the service raises, the router never sends them."""

    messages: list[EmailMessage] = field(default_factory=list)

    def add(self, message: EmailMessage) -> None:
        self.messages.append(message)
