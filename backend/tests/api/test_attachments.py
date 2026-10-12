"""Stories C3 (receipts on expenses) and D6 (documents on purchases): checked by content, size-capped, stripped of
metadata, private, and readable only through the API by people who may see the document."""

import hashlib
from collections.abc import Callable
from io import BytesIO
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.core.enums import Role
from app.core.storage import MemoryStorage, Storage, StorageError
from app.deps import get_storage
from app.models.user import User
from tests.support.documents import (
    Lookups,
    create_lookups,
    direct_expense,
    image_bytes,
    jpeg_with_metadata,
    noisy_png,
    purchase_body,
)

Make = Callable[..., User]
Auth = Callable[[User], dict[str, str]]


@pytest.fixture
def lookups(db_session: Session, make: Make) -> Lookups:
    return create_lookups(db_session, make(Role.ADMIN))


def new_expense(client: TestClient, headers: dict[str, str], lookups: Lookups) -> dict[str, Any]:
    body: dict[str, Any] = client.post("/api/v1/expenses", json=direct_expense(lookups), headers=headers).json()
    return body


def upload(
    client: TestClient, headers: dict[str, str], expense: dict[str, Any], data: bytes, name: str = "receipt.jpg"
) -> Any:
    return client.post(
        f"/api/v1/expenses/{expense['id']}/attachments",
        files={"file": (name, data, "application/octet-stream")},
        headers=headers,
    )


def override_settings(app: FastAPI, settings: Settings, **changes: Any) -> None:
    app.dependency_overrides[get_settings] = lambda: settings.model_copy(update=changes)


# C3: receipts --------------------------------------------------------------------------------------------------------


def test_c3_a_receipt_is_stored_under_a_random_key_and_recorded(
    client: TestClient, make: Make, auth: Auth, lookups: Lookups, storage: MemoryStorage
) -> None:
    headers = auth(make(Role.STAFF))
    expense = new_expense(client, headers, lookups)
    original = image_bytes("JPEG", size=(120, 90))
    response = upload(client, headers, expense, original, name="Receipt from the shop (1).JPG")
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["content_type"] == "image/jpeg"
    assert body["sha256"] == hashlib.sha256(original).hexdigest()  # of the file as received
    assert body["original_name"] == "Receipt_from_the_shop_1.jpg"
    assert "storage_key" not in body
    assert body["created_at"].endswith("Z")
    (key,) = storage.objects
    assert key.startswith("daftar/expense/")
    assert "receipt" not in key.lower()  # nothing about the file name or the owner is in the key
    assert len(key.rsplit("/", 1)[1]) == 32
    assert body["size_bytes"] == len(storage.objects[key])


def test_c3_the_type_is_decided_by_the_bytes_not_the_name(
    client: TestClient, make: Make, auth: Auth, lookups: Lookups
) -> None:
    headers = auth(make(Role.STAFF))
    expense = new_expense(client, headers, lookups)
    png_named_jpg = upload(client, headers, expense, image_bytes("PNG"), name="photo.jpg")
    assert (png_named_jpg.status_code, png_named_jpg.json()["content_type"]) == (201, "image/png")
    assert png_named_jpg.json()["original_name"] == "photo.png"
    webp = upload(client, headers, expense, image_bytes("WEBP"), name="photo.webp")
    assert webp.json()["content_type"] == "image/webp"
    for bad, name in (
        (b"just some text pretending", "receipt.jpg"),
        (b"GIF89a" + b"\0" * 40, "r.gif"),
        (b"%PDF-1.7 ...", "r.jpg"),
        (b"", "empty.jpg"),
        (b"\xff\xd8\xff garbage that is not a jpeg", "broken.jpg"),
    ):
        refused = upload(client, headers, expense, bad, name=name)
        assert refused.status_code == 422, name
        assert refused.json()["code"] == "UNSUPPORTED_FILE_TYPE", name
    assert len(client.get(f"/api/v1/expenses/{expense['id']}/attachments", headers=headers).json()) == 2


def test_c3_metadata_is_stripped_before_the_image_is_stored(
    client: TestClient, make: Make, auth: Auth, lookups: Lookups, storage: MemoryStorage
) -> None:
    headers = auth(make(Role.STAFF))
    expense = new_expense(client, headers, lookups)
    original = jpeg_with_metadata()
    assert upload(client, headers, expense, original).status_code == 201
    (stored,) = storage.objects.values()
    assert b"SecretCameraMaker" not in stored
    reopened = Image.open(BytesIO(stored))
    assert len(reopened.getexif()) == 0
    assert reopened.size == (64, 48)


def test_c3_the_size_cap_is_enforced_and_leaves_nothing_behind(
    client: TestClient,
    app: FastAPI,
    settings: Settings,
    make: Make,
    auth: Auth,
    lookups: Lookups,
    storage: MemoryStorage,
) -> None:
    override_settings(app, settings, max_upload_megabytes=1)
    headers = auth(make(Role.STAFF))
    expense = new_expense(client, headers, lookups)
    big = noisy_png(600)  # about a megabyte and a half of incompressible pixels
    assert len(big) > 1024 * 1024
    refused = upload(client, headers, expense, big)
    assert (refused.status_code, refused.json()["code"]) == (413, "PAYLOAD_TOO_LARGE")
    assert storage.objects == {}
    assert upload(client, headers, expense, image_bytes("PNG")).status_code == 201


def test_c3_an_image_with_too_many_pixels_is_refused(
    client: TestClient, app: FastAPI, settings: Settings, make: Make, auth: Auth, lookups: Lookups
) -> None:
    override_settings(app, settings, max_image_pixels=1000)
    headers = auth(make(Role.STAFF))
    expense = new_expense(client, headers, lookups)
    refused = upload(client, headers, expense, image_bytes("PNG", size=(100, 100)))
    assert (refused.status_code, refused.json()["code"]) == (422, "UNSUPPORTED_FILE_TYPE")
    assert "too large" in refused.json()["detail"]


def test_c3_a_document_holds_a_limited_number_of_attachments(
    client: TestClient, app: FastAPI, settings: Settings, make: Make, auth: Auth, lookups: Lookups
) -> None:
    override_settings(app, settings, max_attachments_per_document=2)
    headers = auth(make(Role.STAFF))
    expense = new_expense(client, headers, lookups)
    first = upload(client, headers, expense, image_bytes("PNG")).json()
    assert upload(client, headers, expense, image_bytes("JPEG")).status_code == 201
    over = upload(client, headers, expense, image_bytes("WEBP"))
    assert (over.status_code, over.json()["code"]) == (409, "ATTACHMENT_LIMIT")
    client.post(f"/api/v1/attachments/{first['id']}/remove", headers=headers)
    assert upload(client, headers, expense, image_bytes("WEBP")).status_code == 201


def test_c3_uploads_are_throttled_per_user(
    client: TestClient, app: FastAPI, settings: Settings, make: Make, auth: Auth, lookups: Lookups
) -> None:
    override_settings(app, settings, max_attachments_per_document=100)
    headers = auth(make(Role.STAFF))
    expense = new_expense(client, headers, lookups)
    tiny = image_bytes("PNG", size=(4, 4))
    assert all(upload(client, headers, expense, tiny).status_code == 201 for _ in range(30))
    blocked = upload(client, headers, expense, tiny)
    assert blocked.status_code == 429
    assert "Retry-After" in blocked.headers


def test_c3_the_same_file_twice_has_the_same_hash_for_duplicate_detection(
    client: TestClient, make: Make, auth: Auth, lookups: Lookups
) -> None:
    headers = auth(make(Role.STAFF))
    first, second = new_expense(client, headers, lookups), new_expense(client, headers, lookups)
    data = jpeg_with_metadata()
    a = upload(client, headers, first, data).json()
    b = upload(client, headers, second, data).json()
    assert a["sha256"] == b["sha256"]
    assert a["id"] != b["id"]


# Reading -------------------------------------------------------------------------------------------------------------


def test_c3_the_image_comes_back_only_through_the_api_with_private_headers(
    client: TestClient, make: Make, auth: Auth, lookups: Lookups
) -> None:
    author = auth(make(Role.STAFF))
    expense = new_expense(client, author, lookups)
    attachment = upload(client, author, expense, image_bytes("PNG", size=(30, 20)), name="../../etc/passwd.png").json()
    url = f"/api/v1/attachments/{attachment['id']}/content"
    response = client.get(url, headers=author)
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    assert response.headers["cache-control"] == "private, no-store"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["content-disposition"] == 'inline; filename="etc_passwd.png"'
    assert Image.open(BytesIO(response.content)).size == (30, 20)
    assert client.get(url).status_code == 401


def test_c3_who_may_read_a_receipt(client: TestClient, make: Make, auth: Auth, lookups: Lookups) -> None:
    author = auth(make(Role.STAFF))
    expense = new_expense(client, author, lookups)
    attachment = upload(client, author, expense, image_bytes("JPEG")).json()
    url = f"/api/v1/attachments/{attachment['id']}/content"
    listing = f"/api/v1/expenses/{expense['id']}/attachments"
    for role in (Role.ADMIN, Role.ACCOUNTANT, Role.APPROVER):
        reader = auth(make(role))
        assert client.get(url, headers=reader).status_code == 200
        assert len(client.get(listing, headers=reader).json()) == 1
    stranger = auth(make(Role.STAFF))
    for path in (url, listing):
        refused = client.get(path, headers=stranger)
        assert (refused.status_code, refused.json()["code"]) == (404, "NOT_FOUND")
    assert client.get("/api/v1/attachments/999999/content", headers=author).status_code == 404


def test_c3_a_storage_failure_is_a_503_and_leaves_no_record(
    client: TestClient, app: FastAPI, make: Make, auth: Auth, lookups: Lookups, db_session: Session
) -> None:
    class Broken(Storage):
        def save(self, key: str, content: bytes, content_type: str) -> None:
            raise StorageError("down")

        def fetch(self, key: str, content_type: str) -> bytes:
            raise StorageError("down")

        def remove(self, key: str) -> None:
            raise StorageError("down")

    headers = auth(make(Role.STAFF))
    expense = new_expense(client, headers, lookups)
    good = upload(client, headers, expense, image_bytes("PNG")).json()
    app.dependency_overrides[get_storage] = Broken
    failed = upload(client, headers, expense, image_bytes("JPEG"))
    assert (failed.status_code, failed.json()["code"]) == (503, "SERVICE_UNAVAILABLE")
    assert len(client.get(f"/api/v1/expenses/{expense['id']}/attachments", headers=headers).json()) == 1
    unreadable = client.get(f"/api/v1/attachments/{good['id']}/content", headers=headers)
    assert unreadable.status_code == 503
    assert "down" not in unreadable.text
    assert db_session.execute(text("SELECT count(*) FROM attachments")).scalar_one() == 1


# Changing ------------------------------------------------------------------------------------------------------------


def test_c3_only_the_author_changes_attachments_and_only_while_draft(
    client: TestClient, make: Make, auth: Auth, lookups: Lookups
) -> None:
    author = auth(make(Role.ACCOUNTANT))
    expense = new_expense(client, author, lookups)
    attachment = upload(client, author, expense, image_bytes("JPEG")).json()
    other = auth(make(Role.ADMIN))
    assert upload(client, other, expense, image_bytes("JPEG")).status_code == 403
    assert client.post(f"/api/v1/attachments/{attachment['id']}/remove", headers=other).status_code == 403
    client.post(f"/api/v1/expenses/{expense['id']}/submit", headers={**author, "If-Match": str(expense["version"])})
    locked_upload = upload(client, author, expense, image_bytes("PNG"))
    assert (locked_upload.status_code, locked_upload.json()["code"]) == (409, "DOCUMENT_LOCKED")
    locked_remove = client.post(f"/api/v1/attachments/{attachment['id']}/remove", headers=author)
    assert (locked_remove.status_code, locked_remove.json()["code"]) == (409, "DOCUMENT_LOCKED")
    assert (
        client.get(f"/api/v1/attachments/{attachment['id']}/content", headers=author).status_code == 200
    )  # still readable


def test_c3_removing_keeps_the_record_and_deletes_the_file(
    client: TestClient, make: Make, auth: Auth, lookups: Lookups, storage: MemoryStorage, db_session: Session
) -> None:
    headers = auth(make(Role.STAFF))
    expense = new_expense(client, headers, lookups)
    attachment = upload(client, headers, expense, image_bytes("JPEG")).json()
    assert len(storage.objects) == 1
    removed = client.post(f"/api/v1/attachments/{attachment['id']}/remove", headers=headers)
    assert removed.status_code == 200
    assert storage.objects == {}
    assert client.get(f"/api/v1/expenses/{expense['id']}/attachments", headers=headers).json() == []
    assert client.get(f"/api/v1/attachments/{attachment['id']}/content", headers=headers).status_code == 404
    assert client.post(f"/api/v1/attachments/{attachment['id']}/remove", headers=headers).status_code == 404
    row = db_session.execute(text("SELECT removed_at, removed_by FROM attachments")).one()
    assert row.removed_at is not None
    actions = [
        r[0]
        for r in db_session.execute(
            text("SELECT action FROM audit_events WHERE action LIKE 'attachment.%' ORDER BY id")
        )
    ]
    assert actions == ["attachment.added", "attachment.removed"]


# D6: purchases -------------------------------------------------------------------------------------------------------


def test_d6_documents_attach_to_a_purchase_under_the_same_rules(
    client: TestClient, make: Make, auth: Auth, lookups: Lookups, storage: MemoryStorage
) -> None:
    accountant = auth(make(Role.ACCOUNTANT))
    purchase = client.post(
        "/api/v1/purchases", json=purchase_body(lookups.vendors["unreg_nonfiler"]), headers=accountant
    ).json()
    path = f"/api/v1/purchases/{purchase['id']}/attachments"
    sent = client.post(path, files={"file": ("memo.png", image_bytes("PNG"), "image/png")}, headers=accountant)
    assert sent.status_code == 201
    assert next(iter(storage.objects)).startswith("daftar/purchase/")
    bad = client.post(path, files={"file": ("memo.pdf", b"%PDF-1.7", "application/pdf")}, headers=accountant)
    assert (bad.status_code, bad.json()["code"]) == (422, "UNSUPPORTED_FILE_TYPE")
    approver = auth(make(Role.APPROVER))
    assert len(client.get(path, headers=approver).json()) == 1
    assert client.get(f"/api/v1/attachments/{sent.json()['id']}/content", headers=approver).status_code == 200
    staff = auth(make(Role.STAFF))
    assert client.get(path, headers=staff).status_code == 403
    assert client.get(f"/api/v1/attachments/{sent.json()['id']}/content", headers=staff).status_code == 404
    assert (
        client.post(path, files={"file": ("a.png", image_bytes("PNG"), "image/png")}, headers=approver).status_code
        == 403
    )
    submitted = client.post(
        f"/api/v1/purchases/{purchase['id']}/submit", headers={**accountant, "If-Match": str(purchase["version"])}
    )
    assert submitted.status_code == 200
    locked = client.post(path, files={"file": ("a.png", image_bytes("PNG"), "image/png")}, headers=accountant)
    assert locked.json()["code"] == "DOCUMENT_LOCKED"
