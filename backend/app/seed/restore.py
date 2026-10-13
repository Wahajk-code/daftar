"""Put the demonstration receipts back into the in-memory store.

The development store lives inside the API process, so the seed (a separate process) cannot fill it, and a restart
empties it. At start-up in development the API calls this: each demonstration receipt is drawn again, matched to its
attachment by the SHA-256 of the bytes that were uploaded, and stored under the key the attachment already has.
Receipts a person uploaded themselves are not restored; Cloudinary (a deployed setting) is what keeps those."""

import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings
from app.core.images import clean_image
from app.core.storage import Storage, StorageError
from app.models.documents import Attachment
from app.seed.data import RECEIPTS
from app.seed.receipts import receipt_image

logger = logging.getLogger("app.seed")


def restore_demo_receipts(session: Session, storage: Storage, settings: Settings) -> int:
    """Returns how many receipts were put back. Receipts already in the store are left alone."""
    restored = 0
    for name in RECEIPTS:
        raw = receipt_image(name)
        image = clean_image(raw, max_pixels=settings.max_image_pixels)
        for attachment in session.scalars(select(Attachment).where(Attachment.sha256 == image.sha256)):
            try:
                storage.fetch(attachment.storage_key, attachment.content_type)
            except StorageError:
                storage.save(attachment.storage_key, image.content, attachment.content_type)
                restored += 1
    return restored
