"""Outgoing email. Services add messages to an Outbox; the router sends them in the background once the service has
returned, which is after the commit. A provider failure is logged and never raised.

Two transports: the console (development) and SMTP (Gmail when deployed, Mailpit locally). Both use only the standard
library. Which one is used follows the settings (see Settings.mail_transport)."""

import logging
import smtplib
import ssl
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from email.message import EmailMessage as MimeMessage
from email.utils import formatdate, make_msgid, parseaddr

from app.config import Settings

logger = logging.getLogger("app.mail")


@dataclass(frozen=True)
class EmailMessage:
    kind: str  # the template, for example "invite"; the only thing logged about a message outside development
    to: str
    subject: str
    body: str
    html: str | None = None  # the styled version; `body` stays as the plain-text fallback


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
    """SMTP with the standard library. With a user it logs in, after upgrading the connection with STARTTLS (port
    587) or from the first byte when `secure` is set (port 465). Without a user it is plain, as Mailpit expects."""

    def __init__(
        self,
        host: str,
        port: int,
        sender: str,
        timeout_seconds: int,
        *,
        user: str | None = None,
        password: str | None = None,
        secure: bool = False,
    ) -> None:
        self._host = host
        self._port = port
        self._sender = sender
        self._timeout = timeout_seconds
        self._user = user
        self._password = password
        self._secure = secure

    def send(self, message: EmailMessage) -> None:
        mime = MimeMessage()
        mime["From"] = self._sender
        mime["To"] = message.to
        mime["Subject"] = message.subject
        mime["Date"] = formatdate(localtime=False)
        mime["Message-ID"] = make_msgid(domain=parseaddr(self._sender)[1].partition("@")[2] or "daftar.local")
        mime.set_content(message.body)
        if message.html:
            mime.add_alternative(message.html, subtype="html")
        connection_class = smtplib.SMTP_SSL if self._secure else smtplib.SMTP
        with connection_class(self._host, self._port, timeout=self._timeout) as connection:
            if self._user is not None:
                if not self._secure:
                    connection.starttls(context=ssl.create_default_context())
                connection.login(self._user, self._password or "")
            connection.send_message(mime)


def build_mailer(settings: Settings) -> Mailer:
    if settings.mail_transport == "smtp":
        password = settings.smtp_pass.get_secret_value() if settings.smtp_pass is not None else None
        return SmtpMailer(
            settings.smtp_host,
            settings.smtp_port,
            settings.mail_from,
            settings.mail_timeout_seconds,
            user=settings.smtp_user,
            password=password,
            secure=settings.smtp_secure,
        )
    return ConsoleMailer()


@dataclass
class Outbox:
    """Messages waiting for the commit. If the service raises, the router never sends them."""

    messages: list[EmailMessage] = field(default_factory=list)

    def add(self, message: EmailMessage) -> None:
        self.messages.append(message)
