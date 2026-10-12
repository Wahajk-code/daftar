"""Outgoing email. Services add messages to an Outbox; the router sends them in the background once the service has
returned, which is after the commit. A provider failure is logged and never raised."""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

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
    """Development transport: the whole message goes to the log. Replaced by Mailpit and Resend in Pass 5."""

    def send(self, message: EmailMessage) -> None:
        logger.info(
            "email (console transport)",
            extra={"email_kind": message.kind, "to": message.to, "subject": message.subject, "body": message.body},
        )


@dataclass
class Outbox:
    """Messages waiting for the commit. If the service raises, the router never sends them."""

    messages: list[EmailMessage] = field(default_factory=list)

    def add(self, message: EmailMessage) -> None:
        self.messages.append(message)
