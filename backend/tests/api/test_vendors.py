"""Stories B1 (vendors, masked bank details) and B2 (the separate filer flag)."""

import logging
from collections.abc import Callable
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.enums import Role
from app.models.user import User
from tests.support.factories import TEST_PASSWORD, RecordingMailer

Make = Callable[..., User]
Auth = Callable[[User], dict[str, str]]

IBAN = "PK36SCBL0000001123456702"
OTHER_IBAN = "PK94MEZN0001234567890123"


def new_vendor(client: TestClient, headers: dict[str, str], **overrides: Any) -> Any:
    body = {
        "name": "Ravi Stationers",
        "is_sales_tax_registered": True,
        "is_filer": True,
        "ntn": "1234567-8",
        "strn": "03-01-8700-123-45",
        **overrides,
    }
    return client.post("/api/v1/vendors", json=body, headers=headers)


def audit_text(db: Session) -> str:
    return str(
        db.execute(
            text(
                "SELECT coalesce(string_agg(coalesce(before::text, '') || coalesce(after::text, ''), ' '), '')"
                " FROM audit_events"
            )
        ).scalar_one()
    )


# Creating and reading ------------------------------------------------------------------------------------------------


def test_b1_a_registered_vendor_is_created_with_its_numbers(client: TestClient, make: Make, auth: Auth) -> None:
    response = new_vendor(
        client,
        auth(make(Role.ACCOUNTANT)),
        contact_name="Ravi Khan",
        phone="+92 300 1234567",
        email="Ravi@Stationers.PK",
        address="Urdu Bazaar, Lahore",
    )
    assert response.status_code == 201
    body = response.json()
    assert (body["ntn"], body["strn"]) == ("1234567-8", "03-01-8700-123-45")
    assert body["email"] == "ravi@stationers.pk"
    assert (body["version"], body["is_active"]) == (1, True)
    assert body["bank_account_masked"] is None


def test_b1_a_registered_vendor_needs_both_numbers(client: TestClient, make: Make, auth: Auth) -> None:
    headers = auth(make(Role.ACCOUNTANT))
    response = new_vendor(client, headers, ntn=None, strn="")
    assert response.status_code == 422
    assert {e["field"] for e in response.json()["errors"]} == {"ntn", "strn"}
    assert new_vendor(client, headers, name="Only NTN", strn=None).status_code == 422


def test_b1_the_database_refuses_a_registered_vendor_without_numbers(db_session: Session, make: Make) -> None:
    owner = make(Role.ADMIN)
    db_session.execute(text("SAVEPOINT s"))
    with pytest.raises(IntegrityError, match="ck_vendors_registered_has_ntn_and_strn"):
        db_session.execute(
            text("INSERT INTO vendors (name, is_sales_tax_registered, created_by) VALUES ('Bypass', true, :u)"),
            {"u": owner.id},
        )
    db_session.execute(text("ROLLBACK TO SAVEPOINT s"))


def test_b1_an_unregistered_vendor_needs_no_numbers_and_may_still_have_an_ntn(
    client: TestClient, make: Make, auth: Auth
) -> None:
    headers = auth(make(Role.ACCOUNTANT))
    bare = new_vendor(
        client, headers, name="Haji Noor Transport", is_sales_tax_registered=False, is_filer=False, ntn=None, strn=None
    )
    assert bare.status_code == 201
    printer = new_vendor(
        client,
        headers,
        name="Al-Madina Printers",
        is_sales_tax_registered=False,
        is_filer=True,
        ntn="9988776-1",
        strn=None,
    )
    assert printer.status_code == 201
    assert printer.json()["ntn"] == "9988776-1"


def test_b2_the_filer_flag_is_independent_of_registration(client: TestClient, make: Make, auth: Auth) -> None:
    headers = auth(make(Role.ACCOUNTANT))
    new_vendor(client, headers, name="Zarai Traders", is_filer=False, ntn="7654321-2", strn="03-01-8700-765-43")
    new_vendor(
        client,
        headers,
        name="Al-Madina Printers",
        is_sales_tax_registered=False,
        is_filer=True,
        ntn="9988776-1",
        strn=None,
    )
    both = client.get("/api/v1/vendors?registered=true&filer=false", headers=headers).json()
    assert [v["name"] for v in both["items"]] == ["Zarai Traders"]
    other = client.get("/api/v1/vendors?registered=false&filer=true", headers=headers).json()
    assert [v["name"] for v in other["items"]] == ["Al-Madina Printers"]


@pytest.mark.parametrize("field", ["ntn", "strn"])
def test_b1_tax_numbers_must_look_like_tax_numbers(client: TestClient, make: Make, auth: Auth, field: str) -> None:
    response = new_vendor(client, auth(make(Role.ACCOUNTANT)), **{field: "not a number"})
    assert response.status_code == 422
    assert response.json()["errors"][0]["field"] == field


def test_b1_unknown_fields_are_rejected(client: TestClient, make: Make, auth: Auth) -> None:
    response = new_vendor(client, auth(make(Role.ACCOUNTANT)), bank_account_encrypted="x", created_by=1)
    assert response.status_code == 422


def test_b1_names_are_unique_ignoring_case_and_spacing(client: TestClient, make: Make, auth: Auth) -> None:
    headers = auth(make(Role.ACCOUNTANT))
    new_vendor(client, headers, name="Ravi Stationers")
    clash = new_vendor(client, headers, name="  RAVI   stationers ")
    assert clash.status_code == 409
    assert clash.json()["code"] == "DUPLICATE_VALUE"
    assert clash.json()["errors"][0]["field"] == "name"


def test_b1_the_list_searches_sorts_and_paginates(client: TestClient, make: Make, auth: Auth) -> None:
    headers = auth(make(Role.ACCOUNTANT))
    for name, ntn in (
        ("Ravi Stationers", "1234567-8"),
        ("Zarai Traders", "7654321-2"),
        ("Karachi Cables", "2233445-6"),
    ):
        new_vendor(client, headers, name=name, ntn=ntn)
    by_name = client.get("/api/v1/vendors?q=zarai", headers=headers).json()
    assert [v["name"] for v in by_name["items"]] == ["Zarai Traders"]
    by_ntn = client.get("/api/v1/vendors?q=2233445", headers=headers).json()
    assert [v["name"] for v in by_ntn["items"]] == ["Karachi Cables"]
    ordered = client.get("/api/v1/vendors?sort=-name&limit=2", headers=headers).json()
    assert ([v["name"] for v in ordered["items"]], ordered["total"]) == (["Zarai Traders", "Ravi Stationers"], 3)
    assert client.get("/api/v1/vendors?sort=bank_account_encrypted", headers=headers).status_code == 422


def test_b1_an_unknown_vendor_is_a_404(client: TestClient, make: Make, auth: Auth) -> None:
    assert client.get("/api/v1/vendors/99999", headers=auth(make(Role.ACCOUNTANT))).status_code == 404


# Bank details --------------------------------------------------------------------------------------------------------


def test_b1_the_account_number_is_never_returned_stored_in_clear_or_audited(
    client: TestClient, make: Make, auth: Auth, db_session: Session, caplog: pytest.LogCaptureFixture
) -> None:
    headers = auth(make(Role.ACCOUNTANT))
    with caplog.at_level(logging.DEBUG):
        created = new_vendor(client, headers, bank_name="Standard Chartered", bank_account_number=IBAN.lower()).json()
        vendor_id = created["id"]
        responses = [
            created,
            client.get(f"/api/v1/vendors/{vendor_id}", headers=headers).json(),
            client.get("/api/v1/vendors", headers=headers).json(),
            client.patch(
                f"/api/v1/vendors/{vendor_id}", json={"phone": "042-111"}, headers={**headers, "If-Match": "1"}
            ).json(),
        ]
    assert created["bank_account_masked"] == "****6702"
    assert created["bank_name"] == "Standard Chartered"
    for body in responses:
        assert IBAN not in str(body)
        assert "bank_account_encrypted" not in str(body)
        assert "6702" in str(body)
    stored = db_session.execute(text("SELECT bank_account_encrypted, bank_account_last4 FROM vendors")).one()
    assert IBAN not in stored[0]
    assert stored[1] == "6702"
    assert IBAN not in audit_text(db_session)
    assert IBAN not in caplog.text


def test_b1_a_malformed_account_number_is_refused(client: TestClient, make: Make, auth: Auth) -> None:
    response = new_vendor(client, auth(make(Role.ACCOUNTANT)), bank_account_number="12")
    assert response.status_code == 422
    assert response.json()["errors"][0]["field"] == "account_number"


def change_bank(client: TestClient, headers: dict[str, str], vendor: dict[str, Any], **body: Any) -> Any:
    payload = {"account_number": OTHER_IBAN, "bank_name": "Meezan Bank", "current_password": TEST_PASSWORD, **body}
    return client.post(
        f"/api/v1/vendors/{vendor['id']}/bank-account",
        json=payload,
        headers={**headers, "If-Match": str(vendor["version"])},
    )


def test_b1_changing_the_bank_account_needs_the_password_again(client: TestClient, make: Make, auth: Auth) -> None:
    headers = auth(make(Role.ACCOUNTANT))
    vendor = new_vendor(client, headers, bank_account_number=IBAN).json()
    wrong = change_bank(client, headers, vendor, current_password="not my password")
    assert wrong.status_code == 403
    assert wrong.json()["code"] == "REAUTH_FAILED"
    assert client.get(f"/api/v1/vendors/{vendor['id']}", headers=headers).json()["bank_account_masked"] == "****6702"
    right = change_bank(client, headers, vendor)
    assert right.status_code == 200
    assert right.json()["bank_account_masked"] == "****0123"
    assert right.json()["version"] == 2


def test_b1_a_bank_change_notifies_the_owner_and_all_admins_and_is_audited(
    client: TestClient, make: Make, auth: Auth, mailer: RecordingMailer, db_session: Session
) -> None:
    owner = make(Role.ACCOUNTANT, full_name="Usman Tariq")
    admin_one = make(Role.ADMIN)
    admin_two = make(Role.ADMIN)
    make(Role.APPROVER)
    make(Role.ADMIN, active=False)
    vendor = new_vendor(client, auth(owner), bank_account_number=IBAN).json()
    # An Admin, not the owner, makes the change: the owner must still hear of it.
    assert change_bank(client, auth(admin_one), vendor).status_code == 200
    recipients = sorted(m.to for m in mailer.sent)
    assert recipients == sorted({owner.email, admin_one.email, admin_two.email})
    body = mailer.sent[0].body
    assert "Ravi Stationers" in body
    assert "0123" in body
    assert OTHER_IBAN not in body
    assert "PKT" in body
    rows = db_session.execute(
        text("SELECT actor_id, before, after FROM audit_events WHERE action = 'vendor.bank_account_changed'")
    ).all()
    assert len(rows) == 1
    assert rows[0].actor_id == admin_one.id
    assert rows[0].before == {"bank_name": None, "bank_account": "****6702"}
    assert rows[0].after == {"bank_name": "Meezan Bank", "bank_account": "****0123"}
    assert OTHER_IBAN not in audit_text(db_session)


def test_b1_the_same_account_again_is_not_a_change(
    client: TestClient, make: Make, auth: Auth, mailer: RecordingMailer, db_session: Session
) -> None:
    headers = auth(make(Role.ACCOUNTANT))
    vendor = new_vendor(client, headers, bank_name="Meezan Bank", bank_account_number=IBAN).json()
    again = change_bank(client, headers, vendor, account_number=IBAN.lower(), bank_name="Meezan Bank")
    assert again.status_code == 200
    assert again.json()["version"] == 1
    assert mailer.sent == []
    count = db_session.execute(
        text("SELECT count(*) FROM audit_events WHERE action = 'vendor.bank_account_changed'")
    ).scalar_one()
    assert count == 0


def test_b1_the_bank_name_stays_when_only_the_number_changes(client: TestClient, make: Make, auth: Auth) -> None:
    headers = auth(make(Role.ACCOUNTANT))
    vendor = new_vendor(client, headers, bank_name="Standard Chartered", bank_account_number=IBAN).json()
    changed = change_bank(client, headers, vendor, bank_name=None)
    assert changed.json()["bank_name"] == "Standard Chartered"


def test_b1_password_guesses_on_a_bank_change_are_throttled(client: TestClient, make: Make, auth: Auth) -> None:
    headers = auth(make(Role.ACCOUNTANT))
    vendor = new_vendor(client, headers, bank_account_number=IBAN).json()
    for _ in range(5):
        assert change_bank(client, headers, vendor, current_password="guess one").status_code == 403
    assert change_bank(client, headers, vendor).status_code == 429


# Updating and deactivating -------------------------------------------------------------------------------------------


def test_b1_an_update_needs_the_version_and_bumps_it(client: TestClient, make: Make, auth: Auth) -> None:
    headers = auth(make(Role.ACCOUNTANT))
    vendor = new_vendor(client, headers).json()
    missing = client.patch(f"/api/v1/vendors/{vendor['id']}", json={"phone": "042-111"}, headers=headers)
    assert missing.status_code == 422
    assert missing.json()["errors"][0]["field"] == "If-Match"
    updated = client.patch(
        f"/api/v1/vendors/{vendor['id']}", json={"phone": "042-111"}, headers={**headers, "If-Match": "1"}
    )
    assert (updated.json()["phone"], updated.json()["version"]) == ("042-111", 2)


def test_b1_an_update_made_against_a_stale_copy_is_a_conflict(client: TestClient, make: Make, auth: Auth) -> None:
    headers = auth(make(Role.ACCOUNTANT))
    vendor = new_vendor(client, headers).json()
    client.patch(f"/api/v1/vendors/{vendor['id']}", json={"phone": "1"}, headers={**headers, "If-Match": "1"})
    stale = client.patch(f"/api/v1/vendors/{vendor['id']}", json={"phone": "2"}, headers={**headers, "If-Match": "1"})
    assert stale.status_code == 409
    assert stale.json()["code"] == "VERSION_CONFLICT"
    assert client.get(f"/api/v1/vendors/{vendor['id']}", headers=headers).json()["phone"] == "1"


def test_b1_an_update_cannot_make_a_vendor_registered_without_numbers(
    client: TestClient, make: Make, auth: Auth
) -> None:
    headers = auth(make(Role.ACCOUNTANT))
    vendor = new_vendor(client, headers, is_sales_tax_registered=False, ntn=None, strn=None).json()
    refused = client.patch(
        f"/api/v1/vendors/{vendor['id']}", json={"is_sales_tax_registered": True}, headers={**headers, "If-Match": "1"}
    )
    assert refused.status_code == 422
    accepted = client.patch(
        f"/api/v1/vendors/{vendor['id']}",
        json={"is_sales_tax_registered": True, "ntn": "1234567-8", "strn": "03-01-8700-123-45"},
        headers={**headers, "If-Match": "1"},
    )
    assert accepted.status_code == 200


def test_b1_changes_are_audited_with_only_the_fields_that_changed(
    client: TestClient, make: Make, auth: Auth, db_session: Session
) -> None:
    headers = auth(make(Role.ACCOUNTANT))
    vendor = new_vendor(client, headers).json()
    client.patch(
        f"/api/v1/vendors/{vendor['id']}",
        json={"phone": "042-111", "is_filer": False},
        headers={**headers, "If-Match": "1"},
    )
    row = db_session.execute(text("SELECT before, after FROM audit_events WHERE action = 'vendor.updated'")).one()
    assert row.before == {"phone": None, "is_filer": True}
    assert row.after == {"phone": "042-111", "is_filer": False}


def test_b1_vendors_deactivate_and_stay_readable_and_are_never_deleted(
    client: TestClient, make: Make, auth: Auth, db_session: Session
) -> None:
    headers = auth(make(Role.ACCOUNTANT))
    vendor = new_vendor(client, headers).json()
    assert client.post(f"/api/v1/vendors/{vendor['id']}/deactivate", headers=headers).json()["is_active"] is False
    assert client.get(f"/api/v1/vendors/{vendor['id']}", headers=headers).json()["name"] == "Ravi Stationers"
    assert client.get("/api/v1/vendors?is_active=true", headers=headers).json()["total"] == 0
    assert client.get("/api/v1/vendors?is_active=false", headers=headers).json()["total"] == 1
    assert client.delete(f"/api/v1/vendors/{vendor['id']}", headers=headers).status_code == 405
    assert client.post(f"/api/v1/vendors/{vendor['id']}/activate", headers=headers).json()["is_active"] is True
    db_session.execute(text("SAVEPOINT s"))
    with pytest.raises(Exception, match="never deleted"):
        db_session.execute(text("DELETE FROM vendors"))
    db_session.execute(text("ROLLBACK TO SAVEPOINT s"))


def test_b1_who_may_do_what(client: TestClient, make: Make, auth: Auth) -> None:
    vendor = new_vendor(client, auth(make(Role.ACCOUNTANT))).json()
    path = f"/api/v1/vendors/{vendor['id']}"
    approver, staff = auth(make(Role.APPROVER)), auth(make(Role.STAFF))
    assert client.get(path, headers=approver).status_code == 200
    assert client.get(path, headers=staff).status_code == 403
    assert client.get("/api/v1/vendors", headers=staff).status_code == 403
    assert new_vendor(client, approver, name="Nope").status_code == 403
    assert client.patch(path, json={"phone": "1"}, headers={**approver, "If-Match": "1"}).status_code == 403
    assert client.post(f"{path}/deactivate", headers=approver).status_code == 403
    assert new_vendor(client, auth(make(Role.ADMIN)), name="Admin made").status_code == 201
