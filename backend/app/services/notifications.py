"""The two emails an approval workflow sends: "needs your approval" when a document is submitted, and "decided" to the
author when it is approved or rejected (decision 52: nothing else, no preferences). The messages go into the Outbox; the
router sends them after the commit, so a move that rolls back tells nobody."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.config import Settings
from app.core import mail_templates
from app.core.clock import format_display_instant
from app.core.enums import DocumentStatus, DocumentType, Role
from app.core.mail import Outbox
from app.core.principal import Principal
from app.repositories import users as user_repository

PATHS = {DocumentType.EXPENSE: "expenses", DocumentType.PURCHASE: "purchases", DocumentType.VOUCHER: "vouchers"}
NAMES = {DocumentType.EXPENSE: "Expense", DocumentType.PURCHASE: "Purchase", DocumentType.VOUCHER: "Voucher"}


@dataclass(frozen=True)
class Recipient:
    email: str
    name: str


def summary_line(amount: Decimal, description: str | None) -> str:
    text = " ".join((description or "").split())
    return f"{amount:,.2f}" + (f" - {text}" if text else "")


class MoveNotifier:
    def __init__(self, session: Session, settings: Settings, outbox: Outbox) -> None:
        self._session = session
        self._settings = settings
        self._outbox = outbox

    def audience(self, target: DocumentStatus, author_id: int) -> list[Recipient]:
        """Who hears about a move to `target`. Ask before the service changes the document: this is a query."""
        if target is DocumentStatus.SUBMITTED:
            people = [
                user
                for role in (Role.APPROVER, Role.ADMIN)
                for user in user_repository.active_by_role(self._session, role)
                if user.id != author_id
            ]
        elif target in (DocumentStatus.APPROVED, DocumentStatus.REJECTED):
            author = user_repository.get(self._session, author_id)
            people = [author] if author is not None and author.is_active else []
        else:
            people = []
        return [Recipient(user.email, user.full_name) for user in people]

    def announce(
        self,
        audience: list[Recipient],
        *,
        document_type: DocumentType,
        document_id: int,
        summary: str,
        actor: Principal,
        target: DocumentStatus,
        comment: str | None,
        when: datetime,
    ) -> None:
        label = f"{NAMES[document_type]} {document_id}"
        link = f"{self._settings.web_base_url.rstrip('/')}/{PATHS[document_type]}/{document_id}"
        zone = ZoneInfo(self._settings.display_timezone)
        for person in audience:
            if target is DocumentStatus.SUBMITTED:
                message = mail_templates.needs_approval(
                    to=person.email,
                    name=person.name,
                    label=label,
                    summary=summary,
                    submitted_by=actor.full_name,
                    link=link,
                )
            else:
                message = mail_templates.decided(
                    to=person.email,
                    name=person.name,
                    label=label,
                    summary=summary,
                    outcome=target.value,
                    decided_by=actor.full_name,
                    when=format_display_instant(when, zone),
                    comment=comment,
                    link=link,
                )
            self._outbox.add(message)
