"""Receipts and supporting images on expenses and purchases.

Uploaded only by the author while the document is a draft; readable by anyone who may read the document, and only
through this service: the stored file has no public address. Every upload is checked by its first bytes, size-capped,
re-encoded to remove embedded metadata (EXIF and GPS), hashed, and stored under a random key."""

import logging
import re
import uuid
from dataclasses import dataclass
from typing import Literal

from sqlalchemy.orm import Session

from app.config import Settings
from app.core.clock import Clock
from app.core.enums import DocumentStatus, Role
from app.core.errors import (
    DomainError,
    ErrorCode,
    FieldError,
    ForbiddenError,
    GuardFailedError,
    NotFoundError,
    ServiceUnavailableError,
)
from app.core.images import ImageRejected, clean_image
from app.core.principal import Principal
from app.core.rate_limit import RateLimiter
from app.core.storage import Storage, StorageError
from app.models.documents import Attachment, Expense, Purchase
from app.repositories import documents as document_repository
from app.services.audit import AuditService

logger = logging.getLogger("app.attachments")
ParentKind = Literal["expense", "purchase"]


@dataclass(frozen=True)
class StoredFile:
    attachment: Attachment
    content: bytes


def safe_filename(name: str, extension: str) -> str:
    """A download name that cannot carry a path, quotes or control characters."""
    stem = re.sub(r"[^A-Za-z0-9._-]+", "_", name.rsplit(".", 1)[0]).strip("._") or "receipt"
    return f"{stem[:80]}.{extension}"


class AttachmentService:
    def __init__(
        self, session: Session, clock: Clock, settings: Settings, storage: Storage, limiter: RateLimiter
    ) -> None:
        self._session = session
        self._clock = clock
        self._settings = settings
        self._storage = storage
        self._limiter = limiter
        self._audit = AuditService(session, clock)

    # Reading ---------------------------------------------------------------------------------------------------------

    def list_for(self, actor: Principal, kind: ParentKind, parent_id: int) -> list[Attachment]:
        self._parent(actor, kind, parent_id)
        return document_repository.attachments_of(
            self._session,
            expense_id=parent_id if kind == "expense" else None,
            purchase_id=parent_id if kind == "purchase" else None,
        )

    def read(self, actor: Principal, attachment_id: int) -> StoredFile:
        attachment = self._get(attachment_id)
        self._parent(actor, *self._parent_of(attachment))
        try:
            content = self._storage.fetch(attachment.storage_key, attachment.content_type)
        except StorageError as exc:
            raise ServiceUnavailableError("The file cannot be read right now. Try again shortly.") from exc
        return StoredFile(attachment, content)

    # Writing ---------------------------------------------------------------------------------------------------------

    def upload(self, actor: Principal, kind: ParentKind, parent_id: int, filename: str, data: bytes) -> Attachment:
        self._limiter.hit(("upload_user", str(actor.id)))
        parent = self._parent(actor, kind, parent_id)
        self._require_open_draft(actor, parent)
        if len(data) > self._settings.max_upload_bytes:
            raise DomainError(
                f"The file is larger than {self._settings.max_upload_megabytes} MB.",
                code=ErrorCode.PAYLOAD_TOO_LARGE,
            )
        existing = document_repository.attachments_of(
            self._session,
            expense_id=parent_id if kind == "expense" else None,
            purchase_id=parent_id if kind == "purchase" else None,
        )
        if len(existing) >= self._settings.max_attachments_per_document:
            raise GuardFailedError(
                f"A document can hold {self._settings.max_attachments_per_document} attachments. Remove one first.",
                code=ErrorCode.ATTACHMENT_LIMIT,
            )
        try:
            image = clean_image(data, max_pixels=self._settings.max_image_pixels)
        except ImageRejected as exc:
            raise GuardFailedError(
                str(exc), code=ErrorCode.UNSUPPORTED_FILE_TYPE, errors=[FieldError("file", str(exc), "invalid_image")]
            ) from exc

        key = f"{self._settings.storage_folder}/{kind}/{uuid.uuid4().hex}"
        try:
            self._storage.save(key, image.content, image.content_type)
        except StorageError as exc:
            raise ServiceUnavailableError("The file could not be stored. Try again shortly.") from exc
        try:
            attachment = document_repository.add_attachment(
                self._session,
                Attachment(
                    expense_id=parent_id if kind == "expense" else None,
                    purchase_id=parent_id if kind == "purchase" else None,
                    storage_key=key,
                    content_type=image.content_type,
                    size_bytes=len(image.content),
                    sha256=image.sha256,
                    original_name=safe_filename(filename, image.extension),
                    uploaded_by=actor.id,
                    created_at=self._clock.now(),
                ),
            )
            self._audit.record(
                actor_id=actor.id,
                action="attachment.added",
                entity_type=kind,
                entity_id=parent_id,
                after={"attachment_id": attachment.id, "sha256": image.sha256, "size_bytes": len(image.content)},
            )
            self._session.commit()
        except Exception:
            self._discard(key)  # the row did not make it, so the stored file must not be left behind
            raise
        return attachment

    def remove(self, actor: Principal, attachment_id: int) -> Attachment:
        attachment = document_repository.get_attachment(self._session, attachment_id, for_update=True)
        if attachment is None or attachment.removed_at is not None:
            raise NotFoundError("There is no such attachment.")
        parent = self._parent(actor, *self._parent_of(attachment))
        self._require_open_draft(actor, parent)
        attachment.removed_at = self._clock.now()
        attachment.removed_by = actor.id
        self._audit.record(
            actor_id=actor.id,
            action="attachment.removed",
            entity_type=attachment_kind(attachment),
            entity_id=attachment.expense_id or attachment.purchase_id,
            before={"attachment_id": attachment.id, "sha256": attachment.sha256},
        )
        self._session.commit()
        self._discard(attachment.storage_key)
        return attachment

    # -----------------------------------------------------------------------------------------------------------------

    def _get(self, attachment_id: int) -> Attachment:
        attachment = document_repository.get_attachment(self._session, attachment_id)
        if attachment is None or attachment.removed_at is not None:
            raise NotFoundError("There is no such attachment.")
        return attachment

    @staticmethod
    def _parent_of(attachment: Attachment) -> tuple[ParentKind, int]:
        if attachment.expense_id is not None:
            return "expense", attachment.expense_id
        assert attachment.purchase_id is not None
        return "purchase", attachment.purchase_id

    def _parent(self, actor: Principal, kind: ParentKind, parent_id: int) -> Expense | Purchase:
        """The document, if this person may see it. Staff see only their own expenses and no purchases; anyone else's
        document is reported as missing."""
        if kind == "expense":
            expense = self._session.get(Expense, parent_id)
            if expense is None or (actor.role is Role.STAFF and expense.created_by != actor.id):
                raise NotFoundError("There is no such expense.")
            return expense
        purchase = self._session.get(Purchase, parent_id)
        if purchase is None or actor.role is Role.STAFF:
            raise NotFoundError("There is no such purchase.")
        return purchase

    @staticmethod
    def _require_open_draft(actor: Principal, parent: Expense | Purchase) -> None:
        if parent.created_by != actor.id:
            raise ForbiddenError("Only the author can change this document's attachments.")
        if parent.status is not DocumentStatus.DRAFT:
            raise GuardFailedError("Only a draft can be changed.", code=ErrorCode.DOCUMENT_LOCKED)

    def _discard(self, key: str) -> None:
        try:
            self._storage.remove(key)
        except StorageError:
            logger.warning("stored file could not be removed", extra={"storage_key": key})


def attachment_kind(attachment: Attachment) -> str:
    return "expense" if attachment.expense_id is not None else "purchase"
