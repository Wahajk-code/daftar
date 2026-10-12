from io import BytesIO

import cloudinary
import pytest
from PIL import Image
from pydantic import ValidationError

from app.config import Settings
from app.core.images import JPEG, PNG, WEBP, ImageRejected, clean_image, sniff
from app.core.storage import CloudinaryStorage, MemoryStorage, StorageError, make_storage
from tests.support.documents import image_bytes, jpeg_with_metadata, noisy_png

PIXELS = 1_000_000


def test_the_type_comes_from_the_first_bytes() -> None:
    assert sniff(image_bytes("JPEG")) == JPEG
    assert sniff(image_bytes("PNG")) == PNG
    assert sniff(image_bytes("WEBP")) == WEBP
    assert sniff(b"GIF89a....") is None
    assert sniff(b"%PDF-1.7") is None
    assert sniff(b"plain text, whatever the file is called") is None
    assert sniff(b"") is None


@pytest.mark.parametrize("kind", ["JPEG", "PNG", "WEBP"])
def test_each_accepted_type_is_cleaned_and_keeps_its_type(kind: str) -> None:
    cleaned = clean_image(image_bytes(kind), max_pixels=PIXELS)
    assert Image.open(BytesIO(cleaned.content)).format == kind
    assert (cleaned.width, cleaned.height) == (64, 48)


def test_exif_and_gps_are_removed_from_the_stored_image() -> None:
    original = jpeg_with_metadata()
    assert b"SecretCameraMaker" in original  # the fixture really does carry metadata
    assert len(Image.open(BytesIO(original)).getexif()) > 0

    cleaned = clean_image(original, max_pixels=PIXELS)
    assert b"SecretCameraMaker" not in cleaned.content
    assert b"Exif" not in cleaned.content
    reopened = Image.open(BytesIO(cleaned.content))
    assert len(reopened.getexif()) == 0
    assert reopened.size == (64, 48)


def test_png_text_chunks_and_profiles_are_removed() -> None:
    from PIL.PngImagePlugin import PngInfo

    info = PngInfo()
    info.add_text("Author", "SecretAuthor")
    out = BytesIO()
    Image.new("RGB", (32, 32), "white").save(out, format="PNG", pnginfo=info)
    assert b"SecretAuthor" in out.getvalue()
    cleaned = clean_image(out.getvalue(), max_pixels=PIXELS)
    assert b"SecretAuthor" not in cleaned.content


def test_a_sideways_phone_photo_is_turned_upright_before_the_orientation_tag_goes() -> None:
    exif = Image.Exif()
    exif[0x0112] = 6  # rotate 90 degrees clockwise to display
    out = BytesIO()
    Image.new("RGB", (80, 40), "red").save(out, format="JPEG", exif=exif)
    cleaned = clean_image(out.getvalue(), max_pixels=PIXELS)
    assert Image.open(BytesIO(cleaned.content)).size == (40, 80)


def test_the_hash_is_of_the_file_as_received() -> None:
    import hashlib

    original = image_bytes("PNG")
    assert clean_image(original, max_pixels=PIXELS).sha256 == hashlib.sha256(original).hexdigest()
    assert clean_image(original, max_pixels=PIXELS).sha256 == clean_image(original, max_pixels=PIXELS).sha256


def test_a_cmyk_jpeg_is_converted_so_it_can_be_written_back() -> None:
    out = BytesIO()
    Image.new("CMYK", (16, 16), (0, 0, 0, 0)).save(out, format="JPEG")
    cleaned = clean_image(out.getvalue(), max_pixels=PIXELS)
    assert Image.open(BytesIO(cleaned.content)).mode in {"RGB", "L"}


@pytest.mark.parametrize(
    ("data", "message"),
    [
        (b"", "empty"),
        (b"GIF89a" + b"\x00" * 50, "Only JPEG, PNG and WebP"),
        (b"%PDF-1.7 not an image", "Only JPEG, PNG and WebP"),
        (b"\x89PNG\r\n\x1a\n" + b"garbage" * 20, "could not be read"),
        (b"\xff\xd8\xff" + b"garbage" * 20, "could not be read"),
        (b"RIFF\x00\x00\x00\x00WEBPjunk" * 3, "could not be read"),
    ],
)
def test_things_that_are_not_images_are_refused(data: bytes, message: str) -> None:
    with pytest.raises(ImageRejected, match=message):
        clean_image(data, max_pixels=PIXELS)


def test_an_image_with_too_many_pixels_is_refused_before_it_is_decoded() -> None:
    with pytest.raises(ImageRejected, match="too large"):
        clean_image(image_bytes("PNG", size=(200, 200)), max_pixels=10_000)


def test_a_truncated_image_is_refused() -> None:
    with pytest.raises(ImageRejected):
        clean_image(noisy_png(100)[:300], max_pixels=PIXELS)


# Storage -------------------------------------------------------------------------------------------------------------


def test_the_memory_store_round_trips_and_forgets() -> None:
    store = MemoryStorage()
    store.save("k", b"bytes", "image/png")
    assert store.fetch("k", "image/png") == b"bytes"
    store.remove("k")
    store.remove("k")  # removing twice is harmless
    with pytest.raises(StorageError):
        store.fetch("k", "image/png")


def settings_with(**overrides: object) -> Settings:
    values: dict[str, object] = {"secret_key": "x" * 40, "database_url": "postgresql+psycopg://u:p@h/db", **overrides}
    return Settings(**values)  # type: ignore[arg-type]


def test_the_default_store_is_memory() -> None:
    assert isinstance(make_storage(settings_with()), MemoryStorage)


def test_cloudinary_needs_its_url_and_production_needs_cloudinary() -> None:
    with pytest.raises(ValidationError, match="CLOUDINARY_URL"):
        settings_with(storage_backend="cloudinary")
    with pytest.raises(ValidationError, match="Cloudinary"):
        settings_with(environment="production", secret_key="f3a9c1d27b8e4a60915d2c7e8b3f4a1d6e0c95b7a2d8f13e")
    assert settings_with(cloudinary_url="").cloudinary_url is None  # an empty variable means unset


def test_the_cloudinary_store_reads_its_credentials_from_the_url_and_never_echoes_them() -> None:
    store = make_storage(
        settings_with(storage_backend="cloudinary", cloudinary_url="cloudinary://key123:secret456@demo-cloud")
    )
    assert isinstance(store, CloudinaryStorage)
    config = cloudinary.config()
    assert (config.cloud_name, config.api_key) == ("demo-cloud", "key123")
    assert "secret456" not in repr(settings_with(cloudinary_url="cloudinary://key123:secret456@demo-cloud"))


@pytest.mark.parametrize(
    "bad", ["https://example.com", "cloudinary://onlyhost", "cloudinary://:secret@cloud", "nonsense"]
)
def test_a_malformed_cloudinary_url_is_refused(bad: str) -> None:
    with pytest.raises(ValueError, match="CLOUDINARY_URL"):
        CloudinaryStorage(bad)
