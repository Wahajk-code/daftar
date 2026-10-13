"""Approval emails (decision 52): "needs your approval" on submit, "decided" to the author on approve or reject.
Sent only after the commit, only to people who may act on them, and a provider failure never fails the request."""

import logging
from collections.abc import Callable
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.enums import Role
from app.core.mail import EmailMessage, Mailer
from app.deps import get_mailer
from app.models.user import User
from tests.support.documents import (
    Ledger,
    Lookups,
    create_ledger,
    create_lookups,
    direct_expense,
    purchase_body,
    voucher_body,
)
from tests.support.factories import RecordingMailer

Make = Callable[..., User]
Auth = Callable[[User], dict[str, str]]


@pytest.fixture
def lookups(db_session: Session, make: Make) -> Lookups:
    # The owner of the reference data is deactivated so it is not one of the people an email could go to.
    return create_lookups(db_session, make(Role.ADMIN, active=False))


def v(headers: dict[str, str], doc: dict[str, Any]) -> dict[str, str]:
    return {**headers, "If-Match": str(doc["version"])}


def new_expense(client: TestClient, headers: dict[str, str], lookups: Lookups) -> dict[str, Any]:
    created: dict[str, Any] = client.post("/api/v1/expenses", json=direct_expense(lookups), headers=headers).json()
    return created


def submit(client: TestClient, kind: str, headers: dict[str, str], doc: dict[str, Any]) -> dict[str, Any]:
    response = client.post(f"/api/v1/{kind}/{doc['id']}/submit", headers=v(headers, doc))
    assert response.status_code == 200, response.text
    result: dict[str, Any] = response.json()
    return result


def test_i2_submitting_tells_every_active_approver_and_admin_but_not_the_author(
    client: TestClient, make: Make, auth: Auth, lookups: Lookups, mailer: RecordingMailer
) -> None:
    author = make(Role.ACCOUNTANT, full_name="Usman Tariq")
    approver = make(Role.APPROVER, full_name="Ayesha Siddiqui")
    admin = make(Role.ADMIN)
    author_admin = make(Role.ADMIN)
    make(Role.APPROVER, active=False)
    make(Role.STAFF)
    make(Role.ACCOUNTANT)
    expense = new_expense(client, auth(author), lookups)
    mailer.sent.clear()
    submit(client, "expenses", auth(author), expense)
    assert sorted(m.to for m in mailer.sent) == sorted([approver.email, admin.email, author_admin.email])
    assert {m.kind for m in mailer.sent} == {"needs_approval"}
    message = mailer.to(approver.email)[0]
    assert message.subject == f"Needs your approval: Expense {expense['id']}"
    assert "Hello Ayesha Siddiqui" in message.body
    assert "Usman Tariq submitted Expense" in message.body
    assert "1,500.00 - Printer paper for the head office" in message.body
    assert f"http://localhost:3001/expenses/{expense['id']}" in message.body


def test_i2_an_author_who_is_an_admin_is_not_asked_to_approve_their_own_document(
    client: TestClient, make: Make, auth: Auth, lookups: Lookups, mailer: RecordingMailer
) -> None:
    author = make(Role.ADMIN)
    other = make(Role.ADMIN)
    expense = new_expense(client, auth(author), lookups)
    mailer.sent.clear()
    submit(client, "expenses", auth(author), expense)
    assert [m.to for m in mailer.sent] == [other.email]


def test_i3_approving_tells_the_author_and_nobody_else(
    client: TestClient, make: Make, auth: Auth, lookups: Lookups, mailer: RecordingMailer
) -> None:
    author = make(Role.STAFF, full_name="Bilal Ahmed")
    approver = make(Role.APPROVER, full_name="Ayesha Siddiqui")
    make(Role.ADMIN)
    expense = submit(client, "expenses", auth(author), new_expense(client, auth(author), lookups))
    mailer.sent.clear()
    response = client.post(f"/api/v1/expenses/{expense['id']}/approve", headers=v(auth(approver), expense))
    assert response.status_code == 200
    assert [(m.kind, m.to) for m in mailer.sent] == [("decided", author.email)]
    message = mailer.sent[0]
    assert message.subject == f"Expense {expense['id']} was approved"
    assert "Ayesha Siddiqui approved Expense" in message.body
    assert "12 Oct 2026, 19:05 PKT" in message.body  # the fake clock reads 14:05 UTC; Karachi is UTC+5
    assert "Their comment" not in message.body


def test_i3_rejecting_carries_the_comment_to_the_author(
    client: TestClient, make: Make, auth: Auth, lookups: Lookups, mailer: RecordingMailer
) -> None:
    author = make(Role.STAFF)
    approver = make(Role.APPROVER)
    expense = submit(client, "expenses", auth(author), new_expense(client, auth(author), lookups))
    mailer.sent.clear()
    response = client.post(
        f"/api/v1/expenses/{expense['id']}/reject",
        json={"comment": "The receipt is for a different month."},
        headers=v(auth(approver), expense),
    )
    assert response.status_code == 200
    (message,) = mailer.sent
    assert (message.kind, message.to) == ("decided", author.email)
    assert message.subject == f"Expense {expense['id']} was rejected"
    assert "Their comment: The receipt is for a different month." in message.body


def test_i3_a_deactivated_author_is_not_emailed_about_the_decision(
    client: TestClient, make: Make, auth: Auth, lookups: Lookups, mailer: RecordingMailer, db_session: Session
) -> None:
    author = make(Role.STAFF)
    approver = make(Role.APPROVER)
    expense = submit(client, "expenses", auth(author), new_expense(client, auth(author), lookups))
    author.is_active = False
    db_session.commit()
    mailer.sent.clear()
    assert (
        client.post(f"/api/v1/expenses/{expense['id']}/approve", headers=v(auth(approver), expense)).status_code == 200
    )
    assert mailer.sent == []


def test_i2_a_move_that_fails_sends_nothing(
    client: TestClient, make: Make, auth: Auth, lookups: Lookups, mailer: RecordingMailer
) -> None:
    author = make(Role.STAFF)
    make(Role.APPROVER)
    expense = new_expense(client, auth(author), lookups)
    mailer.sent.clear()
    stale = client.post(f"/api/v1/expenses/{expense['id']}/submit", headers={**auth(author), "If-Match": "99"})
    assert stale.status_code == 409
    own = client.post(f"/api/v1/expenses/{expense['id']}/approve", headers=v(auth(author), expense))
    assert own.status_code in (403, 409)
    assert mailer.sent == []


def test_i2_a_purchase_goes_through_the_same_two_emails(
    client: TestClient, make: Make, auth: Auth, lookups: Lookups, mailer: RecordingMailer
) -> None:
    author = make(Role.ACCOUNTANT)
    approver = make(Role.APPROVER)
    created = client.post(
        "/api/v1/purchases", json=purchase_body(lookups.vendors["unreg_nonfiler"]), headers=auth(author)
    ).json()
    mailer.sent.clear()
    submitted = submit(client, "purchases", auth(author), created)
    assert [(m.kind, m.to) for m in mailer.sent] == [("needs_approval", approver.email)]
    assert f"http://localhost:3001/purchases/{created['id']}" in mailer.sent[0].body
    assert "10,000.00 - Quarterly supplies" in mailer.sent[0].body
    mailer.sent.clear()
    client.post(f"/api/v1/purchases/{created['id']}/approve", headers=v(auth(approver), submitted))
    assert [(m.kind, m.to) for m in mailer.sent] == [("decided", author.email)]
    assert mailer.sent[0].subject == f"Purchase {created['id']} was approved"


def test_i2_a_voucher_goes_through_the_same_two_emails(
    client: TestClient, make: Make, auth: Auth, lookups: Lookups, db_session: Session, mailer: RecordingMailer
) -> None:
    ledger: Ledger = create_ledger(db_session, lookups, make(Role.ADMIN, active=False))
    author = make(Role.ACCOUNTANT)
    approver = make(Role.APPROVER)
    created = client.post("/api/v1/vouchers", json=voucher_body(ledger, "250.00"), headers=auth(author)).json()
    mailer.sent.clear()
    submitted = submit(client, "vouchers", auth(author), created)
    assert [(m.kind, m.to) for m in mailer.sent] == [("needs_approval", approver.email)]
    assert "250.00 - Office rent for October" in mailer.sent[0].body
    mailer.sent.clear()
    client.post(
        f"/api/v1/vouchers/{created['id']}/reject",
        json={"comment": "Wrong account"},
        headers=v(auth(approver), submitted),
    )
    assert [(m.kind, m.to) for m in mailer.sent] == [("decided", author.email)]
    assert mailer.sent[0].subject == f"Voucher {created['id']} was rejected"


class BrokenMailer(Mailer):
    def __init__(self) -> None:
        self.attempts = 0

    def send(self, message: EmailMessage) -> None:
        self.attempts += 1
        raise ConnectionError("the mail provider is down")


def test_i2_a_provider_failure_never_fails_the_request_and_is_logged(
    app: FastAPI,
    client: TestClient,
    make: Make,
    auth: Auth,
    lookups: Lookups,
    caplog: pytest.LogCaptureFixture,
) -> None:
    broken = BrokenMailer()
    app.dependency_overrides[get_mailer] = lambda: broken
    author = make(Role.STAFF)
    make(Role.APPROVER)
    make(Role.ADMIN)
    expense = new_expense(client, auth(author), lookups)
    with caplog.at_level(logging.ERROR, logger="app.mail"):
        response = client.post(f"/api/v1/expenses/{expense['id']}/submit", headers=v(auth(author), expense))
    assert response.status_code == 200
    assert response.json()["status"] == "submitted"
    assert broken.attempts == 2  # one per recipient: a failure for one does not stop the other
    assert len([r for r in caplog.records if r.message == "email failed"]) == 2
    again = client.get(f"/api/v1/expenses/{expense['id']}", headers=auth(author)).json()
    assert again["status"] == "submitted"  # the change was committed before the email was tried
