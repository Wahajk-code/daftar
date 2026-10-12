"""Checking and cleaning an uploaded receipt image.

The type is decided by the file's first bytes, never its name or the type the client declared. The image is then
decoded and written out again, which drops every piece of embedded metadata (EXIF, GPS, camera and software tags,
colour profiles, comments) because only the pixels are carried over. The SHA-256 is of the file as received, so the
same file uploaded twice is recognised."""

import hashlib
from dataclasses import dataclass
from io import BytesIO

from PIL import Image, ImageOps, UnidentifiedImageError

JPEG = "image/jpeg"
PNG = "image/png"
WEBP = "image/webp"
EXTENSIONS = {JPEG: "jpg", PNG: "png", WEBP: "webp"}
_PIL_FORMAT = {JPEG: "JPEG", PNG: "PNG", WEBP: "WEBP"}


class ImageRejected(ValueError):
    """The upload is not an acceptable receipt image. The message says why, for the person who sent it."""


@dataclass(frozen=True)
class CleanImage:
    content: bytes
    content_type: str
    extension: str
    width: int
    height: int
    sha256: str  # of the bytes as received


def sniff(data: bytes) -> str | None:
    """The image type from the file signature, or None."""
    if data.startswith(b"\xff\xd8\xff"):
        return JPEG
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return PNG
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return WEBP
    return None


def clean_image(data: bytes, *, max_pixels: int) -> CleanImage:
    if not data:
        raise ImageRejected("The file is empty.")
    content_type = sniff(data)
    if content_type is None:
        raise ImageRejected("Only JPEG, PNG and WebP images are accepted.")
    try:
        image = Image.open(BytesIO(data))
        if image.format != _PIL_FORMAT[content_type]:
            raise ImageRejected("The file's contents do not match its type.")
        width, height = image.size
        if width < 1 or height < 1 or width * height > max_pixels:
            raise ImageRejected("The image is too large. Reduce its size and try again.")
        image.load()
    except ImageRejected:
        raise
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError, Image.DecompressionBombError) as exc:
        raise ImageRejected("The file could not be read as an image.") from exc

    # Turn a sideways phone photo upright before the orientation tag is dropped, then drop every piece of metadata.
    upright: Image.Image = ImageOps.exif_transpose(image)
    upright.info.clear()
    if content_type == JPEG and upright.mode not in {"RGB", "L"}:
        upright = upright.convert("RGB")
    out = BytesIO()
    options: dict[str, object] = {"quality": 88} if content_type in {JPEG, WEBP} else {"optimize": True}
    upright.save(out, format=_PIL_FORMAT[content_type], **options)
    return CleanImage(
        content=out.getvalue(),
        content_type=content_type,
        extension=EXTENSIONS[content_type],
        width=width,
        height=height,
        sha256=hashlib.sha256(data).hexdigest(),
    )
