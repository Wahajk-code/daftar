"""Stories A2 (managing users), I4 (invitations), I7 (Admin-triggered reset) and I8 (resend or revoke)."""

import re
from collections.abc import Callable
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.enums import Role
from app.models.user import User
from tests.support.clock import FakeClock
from tests.support.database import settle_constraints
from tests.support.factories import TEST_PASSWORD, RecordingMailer

Make = Callable[..., User]
Auth = Callable[[User], dict[str, str]]
NEW_PASSWORD = "a brand new passphrase"


def audit_rows(db: Session, action: str) -> list[Any]:
    return list(
        db.execute(text("SELECT actor_id, entity_id, before, after FROM audit_events WHERE action = :a"), {"a": action})
    )


def login(client: TestClient, email: str, password: str = TEST_PASSWORD) -> Any:
    return client.post("/api/v1/auth/login", json={"email": email, "password": password})


# Invitations ---------------------------------------------------------------------------------------------------------


def invite(
    client: TestClient, headers: dict[str, str], email: str = "new.hire@daftar.pk", role: str = "accountant"
) -> Any:
    return client.post("/api/v1/invites", json={"email": email, "role": role}, headers=headers)


def test_i4_an_admin_invites_by_email_with_one_role(
    client: TestClient, make: Make, auth: Auth, mailer: RecordingMailer, db_session: Session
) -> None:
    admin = make(Role.ADMIN, full_name="Nadia Qureshi")
    response = invite(client, auth(admin), " New.Hire@Daftar.PK ", "approver")
    assert response.status_code == 201
    body = response.json()
    assert (body["email"], body["role"], body["status"]) == ("new.hire@daftar.pk", "approver", "pending")
    (message,) = mailer.to("new.hire@daftar.pk")
    assert "Nadia Qureshi" in message.body
    assert "approver" in message.body
    assert "accept-invite?token=" in message.body
    assert body["expires_at"].endswith("Z")
    (row,) = audit_rows(db_session, "invite.created")
    assert row.actor_id == admin.id


def test_i4_the_link_creates_the_account_once(
    client: TestClient, make: Make, auth: Auth, mailer: RecordingMailer
) -> None:
    invite(client, auth(make(Role.ADMIN)), "new.hire@daftar.pk", "accountant")
    token = mailer.token_for("new.hire@daftar.pk")

    preview = client.post("/api/v1/auth/invites/inspect", json={"token": token})
    assert preview.status_code == 200
    assert (preview.json()["email"], preview.json()["role"]) == ("new.hire@daftar.pk", "accountant")

    accepted = client.post(
        "/api/v1/auth/invites/accept", json={"token": token, "full_name": "  Usman   Tariq ", "password": NEW_PASSWORD}
    )
    assert accepted.status_code == 201
    assert accepted.json()["full_name"] == "Usman Tariq"
    assert accepted.json()["role"] == "accountant"
    assert "password" not in accepted.text

    assert login(client, "new.hire@daftar.pk", NEW_PASSWORD).status_code == 200
    again = client.post(
        "/api/v1/auth/invites/accept", json={"token": token, "full_name": "Someone Else", "password": NEW_PASSWORD}
    )
    assert again.status_code == 400
    assert again.json()["code"] == "TOKEN_INVALID"


def test_i4_the_invitee_chooses_a_proper_name_and_password(
    client: TestClient, make: Make, auth: Auth, mailer: RecordingMailer
) -> None:
    invite(client, auth(make(Role.ADMIN)))
    token = mailer.token_for("new.hire@daftar.pk")
    weak = client.post("/api/v1/auth/invites/accept", json={"token": token, "full_name": "Usman", "password": "short"})
    assert weak.status_code == 422
    assert weak.json()["errors"][0]["field"] == "password"
    blank = client.post(
        "/api/v1/auth/invites/accept", json={"token": token, "full_name": "   ", "password": NEW_PASSWORD}
    )
    assert blank.status_code == 422
    # Neither attempt used the link up.
    ok = client.post(
        "/api/v1/auth/invites/accept", json={"token": token, "full_name": "Usman", "password": NEW_PASSWORD}
    )
    assert ok.status_code == 201


def test_i4_an_invitation_expires_after_seven_days(
    client: TestClient, make: Make, auth: Auth, mailer: RecordingMailer, clock: FakeClock
) -> None:
    invite(client, auth(make(Role.ADMIN)))
    token = mailer.token_for("new.hire@daftar.pk")
    clock.advance(days=7)
    for path, extra in (("inspect", {}), ("accept", {"full_name": "Usman", "password": NEW_PASSWORD})):
        response = client.post(f"/api/v1/auth/invites/{path}", json={"token": token, **extra})
        assert response.status_code == 400
        assert response.json()["code"] == "TOKEN_EXPIRED"


def test_i4_an_email_that_already_has_an_account_is_refused(client: TestClient, make: Make, auth: Auth) -> None:
    existing = make(Role.STAFF, email="bilal@daftar.pk")
    response = invite(client, auth(make(Role.ADMIN)), existing.email)
    assert response.status_code == 409
    assert response.json()["code"] == "EMAIL_TAKEN"


def test_i4_a_second_invitation_while_one_is_waiting_is_refused_until_it_expires(
    client: TestClient, make: Make, auth: Auth, mailer: RecordingMailer, clock: FakeClock
) -> None:
    headers = auth(make(Role.ADMIN))
    invite(client, headers)
    first = mailer.token_for("new.hire@daftar.pk")
    second = invite(client, headers)
    assert second.status_code == 409
    assert second.json()["code"] == "INVITE_PENDING"
    clock.advance(days=7, seconds=1)
    headers = auth(make(Role.ADMIN))  # the earlier token has aged too
    assert invite(client, headers).status_code == 201
    assert client.post("/api/v1/auth/invites/inspect", json={"token": first}).json()["code"] == "TOKEN_REVOKED"


def test_i4_only_admins_invite(client: TestClient, make: Make, auth: Auth) -> None:
    for role in (Role.ACCOUNTANT, Role.APPROVER, Role.STAFF):
        assert invite(client, auth(make(role))).status_code == 403
    assert client.post("/api/v1/invites", json={"email": "a@b.co", "role": "staff"}).status_code == 401


def test_i4_the_role_must_be_one_of_the_four(client: TestClient, make: Make, auth: Auth) -> None:
    assert invite(client, auth(make(Role.ADMIN)), role="owner").status_code == 422
    assert invite(client, auth(make(Role.ADMIN)), email="not an email").status_code == 422


def test_i4_invitation_tokens_are_stored_only_as_hashes(
    client: TestClient, make: Make, auth: Auth, mailer: RecordingMailer, db_session: Session
) -> None:
    invite(client, auth(make(Role.ADMIN)))
    token = mailer.token_for("new.hire@daftar.pk")
    stored = db_session.execute(text("SELECT string_agg(token_hash, ' ') FROM auth_tokens")).scalar_one()
    assert token not in stored


# Resend, revoke and list ---------------------------------------------------------------------------------------------


def test_i8_resending_replaces_the_link(
    client: TestClient, make: Make, auth: Auth, mailer: RecordingMailer, db_session: Session
) -> None:
    headers = auth(make(Role.ADMIN))
    created = invite(client, headers).json()
    old = mailer.token_for("new.hire@daftar.pk")
    resent = client.post(f"/api/v1/invites/{created['id']}/resend", headers=headers)
    assert resent.status_code == 200
    assert resent.json()["status"] == "pending"
    new = mailer.token_for("new.hire@daftar.pk")
    assert new != old
    assert client.post("/api/v1/auth/invites/inspect", json={"token": old}).json()["code"] == "TOKEN_REVOKED"
    assert client.post("/api/v1/auth/invites/inspect", json={"token": new}).status_code == 200
    assert len(audit_rows(db_session, "invite.resent")) == 1


def test_i8_an_expired_invitation_can_be_resent(
    client: TestClient, make: Make, auth: Auth, mailer: RecordingMailer, clock: FakeClock
) -> None:
    admin = make(Role.ADMIN)
    created = invite(client, auth(admin)).json()
    clock.advance(days=8)
    assert client.post(f"/api/v1/invites/{created['id']}/resend", headers=auth(admin)).status_code == 200
    assert (
        client.post("/api/v1/auth/invites/inspect", json={"token": mailer.token_for("new.hire@daftar.pk")}).status_code
        == 200
    )


def test_i8_resending_is_throttled_per_invitee(client: TestClient, make: Make, auth: Auth) -> None:
    headers = auth(make(Role.ADMIN))
    current = invite(client, headers).json()
    for _ in range(3):
        resent = client.post(f"/api/v1/invites/{current['id']}/resend", headers=headers)
        assert resent.status_code == 200
        current = resent.json()  # a resend issues a new invitation; the old one is cancelled
    blocked = client.post(f"/api/v1/invites/{current['id']}/resend", headers=headers)
    assert blocked.status_code == 429
    assert "Retry-After" in blocked.headers


def test_i8_a_revoked_link_says_so_and_stays_revoked(
    client: TestClient, make: Make, auth: Auth, mailer: RecordingMailer, db_session: Session
) -> None:
    headers = auth(make(Role.ADMIN))
    created = invite(client, headers).json()
    token = mailer.token_for("new.hire@daftar.pk")
    revoked = client.post(f"/api/v1/invites/{created['id']}/revoke", headers=headers)
    assert revoked.json()["status"] == "revoked"
    refused = client.post("/api/v1/auth/invites/inspect", json={"token": token})
    assert (refused.status_code, refused.json()["code"]) == (400, "TOKEN_REVOKED")
    accept = client.post(
        "/api/v1/auth/invites/accept", json={"token": token, "full_name": "Usman", "password": NEW_PASSWORD}
    )
    assert accept.json()["code"] == "TOKEN_REVOKED"
    assert client.post(f"/api/v1/invites/{created['id']}/resend", headers=headers).status_code == 409
    assert len(audit_rows(db_session, "invite.revoked")) == 1
    # Revoking again changes nothing and is not audited twice.
    client.post(f"/api/v1/invites/{created['id']}/revoke", headers=headers)
    assert len(audit_rows(db_session, "invite.revoked")) == 1
    # And a new invitation to the same address is allowed again.
    assert invite(client, headers).status_code == 201


def test_i8_an_accepted_invitation_cannot_be_resent_or_revoked(
    client: TestClient, make: Make, auth: Auth, mailer: RecordingMailer
) -> None:
    headers = auth(make(Role.ADMIN))
    created = invite(client, headers).json()
    client.post(
        "/api/v1/auth/invites/accept",
        json={"token": mailer.token_for("new.hire@daftar.pk"), "full_name": "Usman", "password": NEW_PASSWORD},
    )
    assert client.post(f"/api/v1/invites/{created['id']}/resend", headers=headers).status_code == 409
    assert client.post(f"/api/v1/invites/{created['id']}/revoke", headers=headers).status_code == 409
    assert client.post("/api/v1/invites/99999/revoke", headers=headers).status_code == 404


def test_i8_the_list_shows_each_invitations_state(
    client: TestClient, make: Make, auth: Auth, mailer: RecordingMailer, clock: FakeClock
) -> None:
    admin = make(Role.ADMIN)
    pending = invite(client, auth(admin), "pending@daftar.pk").json()
    revoked = invite(client, auth(admin), "revoked@daftar.pk").json()
    client.post(f"/api/v1/invites/{revoked['id']}/revoke", headers=auth(admin))
    invite(client, auth(admin), "accepted@daftar.pk")
    client.post(
        "/api/v1/auth/invites/accept",
        json={"token": mailer.token_for("accepted@daftar.pk"), "full_name": "Ayesha", "password": NEW_PASSWORD},
    )
    invite(client, auth(admin), "expired@daftar.pk")
    clock.advance(days=8)
    page = client.get("/api/v1/invites", headers=auth(admin)).json()
    states = {item["email"]: item["status"] for item in page["items"]}
    assert states["accepted@daftar.pk"] == "accepted"
    assert states["revoked@daftar.pk"] == "revoked"
    assert states["expired@daftar.pk"] == "expired"
    assert states["pending@daftar.pk"] == "expired"  # eight days on, everything unaccepted has lapsed
    assert page["total"] == 4
    assert pending["id"] in {item["id"] for item in page["items"]}


# Roles and deactivation (A2) -----------------------------------------------------------------------------------------


def test_a2_an_admin_changes_a_role_and_it_is_audited(
    client: TestClient, make: Make, auth: Auth, db_session: Session
) -> None:
    admin = make(Role.ADMIN)
    user = make(Role.ACCOUNTANT)
    response = client.post(f"/api/v1/users/{user.id}/role", json={"role": "approver"}, headers=auth(admin))
    assert response.status_code == 200
    assert response.json()["role"] == "approver"
    ((actor, entity, before, after),) = audit_rows(db_session, "user.role_changed")
    assert (actor, entity, before, after) == (admin.id, user.id, {"role": "accountant"}, {"role": "approver"})


def test_a2_the_new_role_applies_on_the_users_next_request(client: TestClient, make: Make, auth: Auth) -> None:
    admin = make(Role.ADMIN)
    user = make(Role.STAFF)
    assert client.get("/api/v1/users", headers=auth(user)).status_code == 403
    client.post(f"/api/v1/users/{user.id}/role", json={"role": "admin"}, headers=auth(admin))
    assert client.get("/api/v1/users", headers=auth(user)).status_code == 200


def test_a2_changing_a_role_ends_that_users_sessions(client: TestClient, make: Make, auth: Auth) -> None:
    admin = make(Role.ADMIN)
    user = make(Role.ACCOUNTANT)
    pair = login(client, user.email).json()
    client.post(f"/api/v1/users/{user.id}/role", json={"role": "staff"}, headers=auth(admin))
    assert client.post("/api/v1/auth/refresh", json={"refresh_token": pair["refresh_token"]}).status_code == 401


def test_a2_the_same_role_again_changes_nothing(
    client: TestClient, make: Make, auth: Auth, db_session: Session
) -> None:
    admin = make(Role.ADMIN)
    user = make(Role.STAFF)
    assert client.post(f"/api/v1/users/{user.id}/role", json={"role": "staff"}, headers=auth(admin)).status_code == 200
    assert audit_rows(db_session, "user.role_changed") == []


def test_a2_nobody_changes_their_own_role_or_deactivates_themselves(client: TestClient, make: Make, auth: Auth) -> None:
    admin = make(Role.ADMIN)
    make(Role.ADMIN)
    own_role = client.post(f"/api/v1/users/{admin.id}/role", json={"role": "staff"}, headers=auth(admin))
    own_deactivation = client.post(f"/api/v1/users/{admin.id}/deactivate", headers=auth(admin))
    for response in (own_role, own_deactivation):
        assert response.status_code == 403
        assert response.json()["code"] == "SELF_CHANGE_FORBIDDEN"


def test_a2_deactivating_blocks_sign_in_and_ends_sessions_and_reactivating_restores_it(
    client: TestClient, make: Make, auth: Auth, db_session: Session
) -> None:
    admin = make(Role.ADMIN)
    user = make(Role.STAFF)
    pair = login(client, user.email).json()
    response = client.post(f"/api/v1/users/{user.id}/deactivate", headers=auth(admin))
    assert response.json()["is_active"] is False
    assert login(client, user.email).status_code == 401
    assert client.post("/api/v1/auth/refresh", json={"refresh_token": pair["refresh_token"]}).status_code == 401
    assert client.get("/api/v1/me", headers={"Authorization": f"Bearer {pair['access_token']}"}).status_code == 401
    client.post(f"/api/v1/users/{user.id}/reactivate", headers=auth(admin))
    assert login(client, user.email).status_code == 200
    assert len(audit_rows(db_session, "user.deactivated")) == 1
    assert len(audit_rows(db_session, "user.reactivated")) == 1


def test_a2_deactivating_cancels_a_waiting_reset_link(
    client: TestClient, make: Make, auth: Auth, mailer: RecordingMailer
) -> None:
    admin = make(Role.ADMIN)
    user = make(Role.STAFF)
    client.post("/api/v1/auth/forgot-password", json={"email": user.email})
    token = mailer.token_for(user.email)
    client.post(f"/api/v1/users/{user.id}/deactivate", headers=auth(admin))
    response = client.post("/api/v1/auth/reset-password", json={"token": token, "new_password": NEW_PASSWORD})
    assert response.json()["code"] == "TOKEN_REVOKED"


def test_a2_the_database_refuses_to_leave_no_active_admin(db_session: Session, make: Make) -> None:
    """The service guards this; this proves the database does too, for any path that skips the service."""
    only_admin = make(Role.ADMIN)
    make(Role.STAFF)
    only_admin.role = Role.STAFF
    db_session.flush()  # accepted for now: the check waits for commit
    with pytest.raises(IntegrityError, match="users_keep_an_active_admin"):
        settle_constraints(db_session)


def test_a2_the_database_allows_the_change_while_another_admin_remains(db_session: Session, make: Make) -> None:
    first = make(Role.ADMIN)
    make(Role.ADMIN)
    first.is_active = False
    db_session.flush()
    settle_constraints(db_session)


def test_a2_the_users_list_filters_sorts_and_paginates(client: TestClient, make: Make, auth: Auth) -> None:
    admin = make(Role.ADMIN, full_name="Nadia Qureshi")
    make(Role.STAFF, full_name="Bilal Ahmed", email="bilal@daftar.pk")
    make(Role.STAFF, full_name="Zainab Raza", email="zainab@daftar.pk", active=False)
    make(Role.ACCOUNTANT, full_name="Usman Tariq")
    headers = auth(admin)
    everyone = client.get("/api/v1/users", headers=headers).json()
    assert everyone["total"] == 4
    assert [u["full_name"] for u in everyone["items"]] == ["Bilal Ahmed", "Nadia Qureshi", "Usman Tariq", "Zainab Raza"]
    assert all("password" not in u for u in everyone["items"])
    assert client.get("/api/v1/users?role=staff", headers=headers).json()["total"] == 2
    assert client.get("/api/v1/users?is_active=false", headers=headers).json()["total"] == 1
    assert client.get("/api/v1/users?q=BILAL", headers=headers).json()["items"][0]["email"] == "bilal@daftar.pk"
    descending = client.get("/api/v1/users?sort=-name&limit=2&offset=1", headers=headers).json()
    assert (descending["total"], descending["limit"], descending["offset"]) == (4, 2, 1)
    assert [u["full_name"] for u in descending["items"]] == ["Usman Tariq", "Nadia Qureshi"]


def test_a2_page_size_is_clamped_and_sorting_is_whitelisted(client: TestClient, make: Make, auth: Auth) -> None:
    headers = auth(make(Role.ADMIN))
    assert client.get("/api/v1/users?limit=500", headers=headers).json()["limit"] == 100
    assert client.get("/api/v1/users?limit=0", headers=headers).status_code == 422
    assert client.get("/api/v1/users?offset=-1", headers=headers).status_code == 422
    for bad in ("password_hash", "id; DROP TABLE users", "-"):
        response = client.get("/api/v1/users", params={"sort": bad}, headers=headers)
        assert response.status_code == 422
        assert response.json()["errors"][0]["field"] == "sort"


def test_a2_an_unknown_user_is_a_404(client: TestClient, make: Make, auth: Auth) -> None:
    headers = auth(make(Role.ADMIN))
    assert client.get("/api/v1/users/99999", headers=headers).status_code == 404
    assert client.post("/api/v1/users/99999/role", json={"role": "staff"}, headers=headers).status_code == 404


def test_a2_only_admins_manage_users(client: TestClient, make: Make, auth: Auth) -> None:
    target = make(Role.STAFF)
    for role in (Role.ACCOUNTANT, Role.APPROVER, Role.STAFF):
        headers = auth(make(role))
        assert client.get("/api/v1/users", headers=headers).status_code == 403
        assert (
            client.post(f"/api/v1/users/{target.id}/role", json={"role": "admin"}, headers=headers).status_code == 403
        )
        assert client.post(f"/api/v1/users/{target.id}/deactivate", headers=headers).status_code == 403
        assert client.post(f"/api/v1/users/{target.id}/reset-password", headers=headers).status_code == 403


def test_a2_rows_in_users_are_never_deleted(db_session: Session, make: Make) -> None:
    user = make()
    db_session.execute(text("SAVEPOINT s"))
    with pytest.raises(Exception, match="never deleted"):
        db_session.execute(text("DELETE FROM users WHERE id = :id"), {"id": user.id})
    db_session.execute(text("ROLLBACK TO SAVEPOINT s"))


# Admin-triggered reset (I7) ------------------------------------------------------------------------------------------


def test_i7_an_admin_triggers_the_same_reset_email_without_seeing_a_password(
    client: TestClient, make: Make, auth: Auth, mailer: RecordingMailer, db_session: Session
) -> None:
    admin = make(Role.ADMIN)
    user = make(Role.ACCOUNTANT)
    response = client.post(f"/api/v1/users/{user.id}/reset-password", headers=auth(admin))
    assert response.status_code == 202
    assert response.json() == {"status": "accepted"}  # no token, no link, nothing the Admin could use
    (message,) = mailer.to(user.email)
    assert "administrator" in message.body
    assert re.search(r"reset-password\?token=", message.body)
    token = mailer.token_for(user.email)
    done = client.post("/api/v1/auth/reset-password", json={"token": token, "new_password": NEW_PASSWORD})
    assert done.status_code == 204
    assert login(client, user.email, NEW_PASSWORD).status_code == 200
    ((actor, entity, _, _),) = audit_rows(db_session, "user.reset_triggered")
    assert (actor, entity) == (admin.id, user.id)


def test_i7_resets_are_throttled_per_target(client: TestClient, make: Make, auth: Auth) -> None:
    admin = make(Role.ADMIN)
    user = make(Role.STAFF)
    other = make(Role.STAFF)
    for _ in range(3):
        assert client.post(f"/api/v1/users/{user.id}/reset-password", headers=auth(admin)).status_code == 202
    blocked = client.post(f"/api/v1/users/{user.id}/reset-password", headers=auth(admin))
    assert blocked.status_code == 429
    assert "Retry-After" in blocked.headers
    assert client.post(f"/api/v1/users/{other.id}/reset-password", headers=auth(admin)).status_code == 202


def test_i7_a_deactivated_or_unknown_user_cannot_be_reset(client: TestClient, make: Make, auth: Auth) -> None:
    admin = make(Role.ADMIN)
    gone = make(Role.STAFF, active=False)
    assert client.post(f"/api/v1/users/{gone.id}/reset-password", headers=auth(admin)).status_code == 409
    assert client.post("/api/v1/users/99999/reset-password", headers=auth(admin)).status_code == 404
