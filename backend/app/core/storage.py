"""Where attachments live. One small interface, two implementations: Cloudinary, and an in-memory store for
development and tests (so the suite needs no network and no account).

Receipts are financial documents. In Cloudinary they are uploaded with delivery type `authenticated`, so they have no
public URL; the API checks who is asking and only then reads the bytes back. Clients never talk to Cloudinary."""

import time
from abc import ABC, abstractmethod
from io import BytesIO
from urllib.parse import urlparse

import cloudinary
import cloudinary.uploader
import cloudinary.utils
import urllib3

from app.config import Settings
from app.core.images import EXTENSIONS

DOWNLOAD_LINK_SECONDS = 120


class StorageError(Exception):
    """The store could not be reached or refused. Never carries credentials."""


class Storage(ABC):
    @abstractmethod
    def save(self, key: str, content: bytes, content_type: str) -> None: ...

    @abstractmethod
    def fetch(self, key: str, content_type: str) -> bytes: ...

    @abstractmethod
    def remove(self, key: str) -> None: ...


class MemoryStorage(Storage):
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    def save(self, key: str, content: bytes, content_type: str) -> None:
        self.objects[key] = content

    def fetch(self, key: str, content_type: str) -> bytes:
        try:
            return self.objects[key]
        except KeyError as exc:
            raise StorageError("The stored file is missing.") from exc

    def remove(self, key: str) -> None:
        self.objects.pop(key, None)


class CloudinaryStorage(Storage):
    def __init__(self, cloudinary_url: str) -> None:
        parsed = urlparse(cloudinary_url)
        if parsed.scheme != "cloudinary" or not (parsed.username and parsed.password and parsed.hostname):
            raise ValueError("CLOUDINARY_URL must look like cloudinary://<key>:<secret>@<cloud_name>")
        cloudinary.config(cloud_name=parsed.hostname, api_key=parsed.username, api_secret=parsed.password, secure=True)
        self._http = urllib3.PoolManager(timeout=urllib3.Timeout(connect=5, read=20), retries=urllib3.Retry(2))

    def save(self, key: str, content: bytes, content_type: str) -> None:
        try:
            cloudinary.uploader.upload(
                BytesIO(content),
                public_id=key,
                type="authenticated",
                resource_type="image",
                overwrite=False,
                unique_filename=False,
            )
        except Exception as exc:  # the SDK raises its own error types; none may leak credentials
            raise StorageError("The file could not be stored.") from exc

    def fetch(self, key: str, content_type: str) -> bytes:
        try:
            url = cloudinary.utils.private_download_url(
                key,
                EXTENSIONS[content_type],
                resource_type="image",
                type="authenticated",
                expires_at=int(time.time()) + DOWNLOAD_LINK_SECONDS,
            )
            response = self._http.request("GET", url)
        except Exception as exc:
            raise StorageError("The stored file could not be read.") from exc
        if response.status != 200:
            raise StorageError("The stored file could not be read.")
        return bytes(response.data)

    def remove(self, key: str) -> None:
        try:
            cloudinary.uploader.destroy(key, type="authenticated", resource_type="image", invalidate=True)
        except Exception as exc:
            raise StorageError("The stored file could not be removed.") from exc


def make_storage(settings: Settings) -> Storage:
    if settings.storage_backend == "cloudinary" and settings.cloudinary_url is not None:
        return CloudinaryStorage(settings.cloudinary_url.get_secret_value())
    return MemoryStorage()
