"""Story F3: every change leaves an audit row, written in the same transaction as the change.

The route list comes from the OpenAPI file, so a new mutating route fails `test_every_mutating_route_has_a_scenario`
until someone writes a scenario for it or states why it needs no audit row. For each audited route two things are
proved:

1. Atomic: with the audit insert made to fail, the request fails and the database is exactly as it was (every table,
   every column), so the change and its audit row commit or roll back together.
2. Written: the same request, with the audit insert working, succeeds and adds at least one audit row."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.enums import Role
from app.models.user import User
from app.repositories import audit as audit_repository
from tests.support.documents import (
    Ledger,
    Lookups,
    create_ledger,
    create_lookups,
    direct_expense,
    image_bytes,
    purchase_body,
    voucher_body,
)
from tests.support.factories import TEST_PASSWORD, RecordingMailer

pytestmark = pytest.mark.slow

Make = Callable[..., User]
Auth = Callable[[User], dict[str, str]]
Thunk = Callable[[], Any]  # the request under test, ready to send
IBAN = "PK36SCBL0000001123456702"
OTHER_IBAN = "PK94MEZN0001234567890123"
NEW_PASSWORD = "a brand new passphrase"


class World:
    """People, reference data and documents in any state, for scenarios to build on."""

    def __init__(
        self,
        client: TestClient,
        db: Session,
        make: Make,
        auth: Auth,
        mailer: RecordingMailer,
        lookups: Lookups,
        ledger: Ledger,
    ) -> None:
        self.client, self.db, self.make, self.mailer = client, db, make, mailer
        self.lookups, self.ledger = lookups, ledger
        self.users = {role: make(role) for role in Role}
        self.h = {role: auth(user) for role, user in self.users.items()}

    # Requests ---------------------------------------------------------------------------------------------------------

    def post(self, path: str, role: Role, doc: dict[str, Any] | None = None, body: Any = None, **extra: str) -> Any:
        headers = {**self.h[role], **extra}
        if doc is not None:
            headers["If-Match"] = str(doc["version"])
        return self.client.post(path, json=body, headers=headers)

    def ok(self, response: Any) -> dict[str, Any]:
        assert 200 <= response.status_code < 300, (response.status_code, response.text)
        result: dict[str, Any] = response.json()
        return result

    # Documents --------------------------------------------------------------------------------------------------------

    def expense(self, state: str = "draft", **overrides: Any) -> dict[str, Any]:
        doc = self.ok(
            self.client.post(
                "/api/v1/expenses", json=direct_expense(self.lookups, **overrides), headers=self.h[Role.STAFF]
            )
        )
        return self._walk("expenses", doc, state, Role.STAFF)

    def purchase(self, state: str = "draft") -> dict[str, Any]:
        body = purchase_body(self.lookups.vendors["unreg_nonfiler"])
        doc = self.ok(self.client.post("/api/v1/purchases", json=body, headers=self.h[Role.ACCOUNTANT]))
        return self._walk("purchases", doc, state, Role.ACCOUNTANT)

    def voucher(self, state: str = "draft") -> dict[str, Any]:
        doc = self.ok(
            self.client.post("/api/v1/vouchers", json=voucher_body(self.ledger), headers=self.h[Role.ACCOUNTANT])
        )
        doc = self._walk("vouchers", doc, state if state != "posted" else "approved", Role.ACCOUNTANT)
        if state == "posted":
            doc = self.ok(
                self.post(
                    f"/api/v1/vouchers/{doc['id']}/post",
                    Role.ACCOUNTANT,
                    doc,
                    **{"Idempotency-Key": "audit-post-key-1"},
                )
            )
        return doc

    def _walk(self, kind: str, doc: dict[str, Any], state: str, author: Role) -> dict[str, Any]:
        if state in {"submitted", "approved", "rejected"}:
            doc = self.ok(self.post(f"/api/v1/{kind}/{doc['id']}/submit", author, doc))
        if state == "approved":
            doc = self.ok(self.post(f"/api/v1/{kind}/{doc['id']}/approve", Role.APPROVER, doc))
        if state == "rejected":
            doc = self.ok(self.post(f"/api/v1/{kind}/{doc['id']}/reject", Role.APPROVER, doc, {"comment": "No"}))
        return doc

    def attached_expense(self) -> tuple[dict[str, Any], dict[str, Any]]:
        expense = self.expense()
        files = {"file": ("r.jpg", image_bytes("JPEG", (50, 40)), "image/jpeg")}
        attachment = self.ok(
            self.client.post(f"/api/v1/expenses/{expense['id']}/attachments", files=files, headers=self.h[Role.STAFF])
        )
        return expense, attachment

    # Master data and people -------------------------------------------------------------------------------------------

    def create(self, path: str, body: dict[str, Any]) -> dict[str, Any]:
        return self.ok(self.post(path, Role.ACCOUNTANT, body=body))

    def invite(self, email: str = "new.hire@daftar.pk") -> dict[str, Any]:
        return self.ok(self.post("/api/v1/invites", Role.ADMIN, body={"email": email, "role": "staff"}))

    def login(self, user: User) -> dict[str, Any]:
        return self.ok(self.client.post("/api/v1/auth/login", json={"email": user.email, "password": TEST_PASSWORD}))


@dataclass(frozen=True)
class Scenario:
    prepare: Callable[[World], Thunk]
    audited: bool = True
    why_not: str = ""


SCENARIOS: dict[str, Scenario] = {}


def scenario(
    operation: str, *, audited: bool = True, why_not: str = ""
) -> Callable[[Callable[[World], Thunk]], Callable[[World], Thunk]]:
    def register(prepare: Callable[[World], Thunk]) -> Callable[[World], Thunk]:
        SCENARIOS[operation] = Scenario(prepare, audited, why_not)
        return prepare

    return register


def simple(
    operation: str, path: Callable[[World], str], role: Role, body: Callable[[World], Any] | None = None, **flags: Any
) -> None:
    """A route that needs nothing prepared beyond what its path names."""

    def prepare(w: World) -> Thunk:
        url, payload = path(w), body(w) if body else None
        return lambda: w.post(url, role, body=payload)

    scenario(operation, **flags)(prepare)


# Sign in and out -----------------------------------------------------------------------------------------------------


@scenario("login")
def _(w: World) -> Thunk:
    user = w.make(Role.STAFF)
    return lambda: w.client.post("/api/v1/auth/login", json={"email": user.email, "password": TEST_PASSWORD})


@scenario(
    "refresh_session",
    audited=False,
    why_not="A refresh only rotates a session token, every few minutes per user; the sign of theft, a spent token used "
    "again, is audited (auth.refresh_reuse_detected).",
)
def _(w: World) -> Thunk:
    pair = w.login(w.make(Role.STAFF))
    return lambda: w.client.post("/api/v1/auth/refresh", json={"refresh_token": pair["refresh_token"]})


@scenario("logout")
def _(w: World) -> Thunk:
    pair = w.login(w.make(Role.STAFF))
    return lambda: w.client.post("/api/v1/auth/logout", json={"refresh_token": pair["refresh_token"]})


@scenario("forgot_password")
def _(w: World) -> Thunk:
    user = w.make(Role.STAFF)
    return lambda: w.client.post("/api/v1/auth/forgot-password", json={"email": user.email})


@scenario("reset_password")
def _(w: World) -> Thunk:
    user = w.make(Role.STAFF)
    w.client.post("/api/v1/auth/forgot-password", json={"email": user.email})
    token = w.mailer.token_for(user.email)
    return lambda: w.client.post("/api/v1/auth/reset-password", json={"token": token, "new_password": NEW_PASSWORD})


@scenario("inspect_invite", audited=False, why_not="It only reads: it shows the invited address and role.")
def _(w: World) -> Thunk:
    w.invite()
    token = w.mailer.token_for("new.hire@daftar.pk")
    return lambda: w.client.post("/api/v1/auth/invites/inspect", json={"token": token})


@scenario("accept_invite")
def _(w: World) -> Thunk:
    w.invite()
    token = w.mailer.token_for("new.hire@daftar.pk")
    body = {"token": token, "full_name": "New Hire", "password": NEW_PASSWORD}
    return lambda: w.client.post("/api/v1/auth/invites/accept", json=body)


@scenario("change_my_password")
def _(w: World) -> Thunk:
    pair = w.login(w.users[Role.STAFF])
    headers = {"Authorization": f"Bearer {pair['access_token']}"}
    body = {"current_password": TEST_PASSWORD, "new_password": NEW_PASSWORD}
    return lambda: w.client.post("/api/v1/me/password", json=body, headers=headers)


@scenario("complete_my_tour")
def _(w: World) -> Thunk:
    return lambda: w.post("/api/v1/me/tour/complete", Role.STAFF)


@scenario("restart_my_tour")
def _(w: World) -> Thunk:
    w.ok(w.post("/api/v1/me/tour/complete", Role.STAFF))
    return lambda: w.post("/api/v1/me/tour/restart", Role.STAFF)


# Users and invitations -----------------------------------------------------------------------------------------------


@scenario("change_user_role")
def _(w: World) -> Thunk:
    target = w.make(Role.STAFF)
    return lambda: w.post(f"/api/v1/users/{target.id}/role", Role.ADMIN, body={"role": "approver"})


simple("deactivate_user", lambda w: f"/api/v1/users/{w.make(Role.STAFF).id}/deactivate", Role.ADMIN)
simple("reactivate_user", lambda w: f"/api/v1/users/{w.make(Role.STAFF, active=False).id}/reactivate", Role.ADMIN)
simple("trigger_password_reset", lambda w: f"/api/v1/users/{w.make(Role.STAFF).id}/reset-password", Role.ADMIN)
simple(
    "create_invite",
    lambda _w: "/api/v1/invites",
    Role.ADMIN,
    lambda _w: {"email": "invited@daftar.pk", "role": "staff"},
)
simple("resend_invite", lambda w: f"/api/v1/invites/{w.invite()['id']}/resend", Role.ADMIN)
simple("revoke_invite", lambda w: f"/api/v1/invites/{w.invite()['id']}/revoke", Role.ADMIN)


# Vendors -------------------------------------------------------------------------------------------------------------


def new_vendor(w: World, **extra: Any) -> dict[str, Any]:
    return w.create("/api/v1/vendors", {"name": "Test Traders", "is_sales_tax_registered": False, **extra})


simple(
    "create_vendor",
    lambda _w: "/api/v1/vendors",
    Role.ACCOUNTANT,
    lambda _w: {"name": "Fresh Traders", "is_sales_tax_registered": False},
)


@scenario("update_vendor")
def _(w: World) -> Thunk:
    vendor = new_vendor(w)
    return lambda: w.client.patch(
        f"/api/v1/vendors/{vendor['id']}",
        json={"name": "Renamed"},
        headers={**w.h[Role.ACCOUNTANT], "If-Match": str(vendor["version"])},
    )


simple("deactivate_vendor", lambda w: f"/api/v1/vendors/{new_vendor(w)['id']}/deactivate", Role.ACCOUNTANT)


@scenario("activate_vendor")
def _(w: World) -> Thunk:
    vendor = new_vendor(w)
    w.ok(w.post(f"/api/v1/vendors/{vendor['id']}/deactivate", Role.ACCOUNTANT))
    return lambda: w.post(f"/api/v1/vendors/{vendor['id']}/activate", Role.ACCOUNTANT)


@scenario("change_vendor_bank_account")
def _(w: World) -> Thunk:
    vendor = new_vendor(w, bank_account_number=IBAN, bank_name="Standard Chartered")
    body = {"account_number": OTHER_IBAN, "bank_name": "Meezan Bank", "current_password": TEST_PASSWORD}
    return lambda: w.post(f"/api/v1/vendors/{vendor['id']}/bank-account", Role.ACCOUNTANT, vendor, body)


# Expenses ------------------------------------------------------------------------------------------------------------


@scenario("create_expense")
def _(w: World) -> Thunk:
    return lambda: w.client.post("/api/v1/expenses", json=direct_expense(w.lookups), headers=w.h[Role.STAFF])


@scenario("preview_expense_allocation", audited=False, why_not="It computes a split and saves nothing.")
def _(w: World) -> Thunk:
    a, b, _ = (c.id for c in w.lookups.centres)
    body = {
        "amount": "100.00",
        "allocation": {
            "method": "percentage",
            "lines": [{"cost_center_id": a, "basis_points": 6000}, {"cost_center_id": b, "basis_points": 4000}],
        },
    }
    return lambda: w.post("/api/v1/expenses/preview-allocation", Role.STAFF, body=body)


@scenario("update_expense")
def _(w: World) -> Thunk:
    expense = w.expense()
    return lambda: w.client.patch(
        f"/api/v1/expenses/{expense['id']}",
        json={"description": "Changed"},
        headers={**w.h[Role.STAFF], "If-Match": str(expense["version"])},
    )


def document_move(
    operation: str, kind: str, action: str, state: str, role: Role, body: Any = None, *, maker: str
) -> None:
    def prepare(w: World) -> Thunk:
        doc = getattr(w, maker)(state)
        return lambda: w.post(f"/api/v1/{kind}/{doc['id']}/{action}", role, doc, body)

    scenario(operation)(prepare)


for _kind, _singular, _author in (
    ("expenses", "expense", Role.STAFF),
    ("purchases", "purchase", Role.ACCOUNTANT),
    ("vouchers", "voucher", Role.ACCOUNTANT),
):
    document_move(f"submit_{_singular}", _kind, "submit", "draft", _author, maker=_singular)
    document_move(f"approve_{_singular}", _kind, "approve", "submitted", Role.APPROVER, maker=_singular)
    document_move(
        f"reject_{_singular}", _kind, "reject", "submitted", Role.APPROVER, {"comment": "Not right"}, maker=_singular
    )
    document_move(f"reopen_{_singular}", _kind, "reopen", "rejected", _author, maker=_singular)


@scenario("upload_expense_attachment")
def _(w: World) -> Thunk:
    expense = w.expense()
    files = {"file": ("r.jpg", image_bytes("JPEG", (50, 40)), "image/jpeg")}
    return lambda: w.client.post(f"/api/v1/expenses/{expense['id']}/attachments", files=files, headers=w.h[Role.STAFF])


@scenario("generate_voucher_from_expense")
def _(w: World) -> Thunk:
    expense = w.expense("approved")
    return lambda: w.post(f"/api/v1/expenses/{expense['id']}/generate-voucher", Role.ACCOUNTANT)


@scenario("remove_attachment")
def _(w: World) -> Thunk:
    _expense, attachment = w.attached_expense()
    return lambda: w.post(f"/api/v1/attachments/{attachment['id']}/remove", Role.STAFF)


# Purchases -----------------------------------------------------------------------------------------------------------


@scenario("create_purchase")
def _(w: World) -> Thunk:
    body = purchase_body(w.lookups.vendors["unreg_nonfiler"])
    return lambda: w.post("/api/v1/purchases", Role.ACCOUNTANT, body=body)


@scenario("preview_purchase", audited=False, why_not="It prices a purchase as typed and saves nothing.")
def _(w: World) -> Thunk:
    full = purchase_body(w.lookups.vendors["unreg_nonfiler"])
    body = {"vendor_id": full["vendor_id"], "lines": full["lines"]}
    return lambda: w.post("/api/v1/purchases/preview", Role.ACCOUNTANT, body=body)


@scenario("update_purchase")
def _(w: World) -> Thunk:
    purchase = w.purchase()
    return lambda: w.client.patch(
        f"/api/v1/purchases/{purchase['id']}",
        json={"description": "Changed"},
        headers={**w.h[Role.ACCOUNTANT], "If-Match": str(purchase["version"])},
    )


@scenario("upload_purchase_attachment")
def _(w: World) -> Thunk:
    purchase = w.purchase()
    files = {"file": ("m.jpg", image_bytes("JPEG", (50, 40)), "image/jpeg")}
    return lambda: w.client.post(
        f"/api/v1/purchases/{purchase['id']}/attachments", files=files, headers=w.h[Role.ACCOUNTANT]
    )


@scenario("generate_voucher_from_purchase")
def _(w: World) -> Thunk:
    purchase = w.purchase("approved")
    body = {"category_id": w.lookups.category.id, "payment_method": "cash"}
    return lambda: w.post(f"/api/v1/purchases/{purchase['id']}/generate-voucher", Role.ACCOUNTANT, body=body)


# Vouchers ------------------------------------------------------------------------------------------------------------


@scenario("create_voucher")
def _(w: World) -> Thunk:
    return lambda: w.post("/api/v1/vouchers", Role.ACCOUNTANT, body=voucher_body(w.ledger))


@scenario("check_voucher_balance", audited=False, why_not="It adds up lines as typed and saves nothing.")
def _(w: World) -> Thunk:
    lines = [{"account_id": w.ledger.expense.id, "debit": "10.00"}, {"account_id": w.ledger.cash.id, "credit": "9.00"}]
    return lambda: w.post("/api/v1/vouchers/check-balance", Role.ACCOUNTANT, body={"lines": lines})


@scenario("update_voucher")
def _(w: World) -> Thunk:
    voucher = w.voucher()
    return lambda: w.client.patch(
        f"/api/v1/vouchers/{voucher['id']}",
        json={"description": "Changed"},
        headers={**w.h[Role.ACCOUNTANT], "If-Match": str(voucher["version"])},
    )


@scenario("post_voucher")
def _(w: World) -> Thunk:
    voucher = w.voucher("approved")
    return lambda: w.post(
        f"/api/v1/vouchers/{voucher['id']}/post", Role.ACCOUNTANT, voucher, **{"Idempotency-Key": "audit-post-key-2"}
    )


@scenario("void_voucher")
def _(w: World) -> Thunk:
    voucher = w.voucher("posted")
    return lambda: w.post(
        f"/api/v1/vouchers/{voucher['id']}/void",
        Role.ADMIN,
        voucher,
        {"reason": "Entered twice"},
        **{"Idempotency-Key": "audit-void-key-1"},
    )


# Master data ---------------------------------------------------------------------------------------------------------

_serial = iter(range(1, 10_000))


def master(prefix: str, create_body: Callable[[World], dict[str, Any]], update_body: dict[str, Any]) -> None:
    """create, update, deactivate and activate for one kind of master data."""
    plural = {"account": "accounts", "category": "categories", "cost_center": "cost-centers", "project": "projects"}[
        prefix
    ]
    path = f"/api/v1/{plural}"

    def make(w: World) -> dict[str, Any]:
        return w.create(path, create_body(w))

    @scenario(f"create_{prefix}")
    def _(w: World) -> Thunk:
        body = create_body(w)
        return lambda: w.post(path, Role.ACCOUNTANT, body=body)

    @scenario(f"update_{prefix}")
    def _(w: World) -> Thunk:
        row = make(w)
        return lambda: w.client.patch(
            f"{path}/{row['id']}", json=update_body, headers={**w.h[Role.ACCOUNTANT], "If-Match": str(row["version"])}
        )

    @scenario(f"deactivate_{prefix}")
    def _(w: World) -> Thunk:
        row = make(w)
        return lambda: w.post(f"{path}/{row['id']}/deactivate", Role.ACCOUNTANT)

    @scenario(f"activate_{prefix}")
    def _(w: World) -> Thunk:
        row = make(w)
        w.ok(w.post(f"{path}/{row['id']}/deactivate", Role.ACCOUNTANT))
        return lambda: w.post(f"{path}/{row['id']}/activate", Role.ACCOUNTANT)


master(
    "account",
    lambda _w: {"code": f"7{next(_serial):03d}", "name": "Insurance", "type": "expense"},
    {"name": "Insurance and cover"},
)
master(
    "category",
    lambda w: {"name": f"Category {next(_serial)}", "account_id": w.ledger.other_expense.id},
    {"name": "Renamed category"},
)
master("cost_center", lambda _w: {"code": f"CC{next(_serial)}", "name": "Warehouse"}, {"name": "Warehouse North"})
master(
    "project",
    lambda _w: {"code": f"P{next(_serial)}", "name": "Fit-out", "kind": "project"},
    {"name": "Fit-out phase 2"},
)


@scenario("close_period")
def _(w: World) -> Thunk:
    return lambda: w.post(
        "/api/v1/periods/close", Role.ADMIN, body={"start_date": "2026-08-01", "end_date": "2026-08-31"}
    )


@scenario("reopen_period")
def _(w: World) -> Thunk:
    period = w.ok(
        w.post("/api/v1/periods/close", Role.ADMIN, body={"start_date": "2026-08-01", "end_date": "2026-08-31"})
    )
    return lambda: w.post(f"/api/v1/periods/{period['id']}/reopen", Role.ADMIN)


@scenario("set_accounting_settings")
def _(w: World) -> Thunk:
    return lambda: w.client.put(
        "/api/v1/settings/accounting", json={"fiscal_year_start_month": 7}, headers=w.h[Role.ACCOUNTANT]
    )


@scenario("set_posting_account")
def _(w: World) -> Thunk:
    body = {"account_id": w.ledger.bank.id}
    return lambda: w.client.put("/api/v1/posting-accounts/cash", json=body, headers=w.h[Role.ADMIN])


TAX_RULE = {
    "tax_type": "income_tax_withholding",
    "supplier_filer": True,
    "category": "any",
    "rate_bp": 1000,
    "effective_from": "2025-07-01",
    "source": "Test fallback",
}


@scenario("create_tax_rule")
def _(w: World) -> Thunk:
    return lambda: w.post("/api/v1/tax-rules", Role.ADMIN, body=TAX_RULE)


@scenario("update_tax_rule")
def _(w: World) -> Thunk:
    rule = w.ok(w.post("/api/v1/tax-rules", Role.ADMIN, body=TAX_RULE))
    return lambda: w.client.patch(
        f"/api/v1/tax-rules/{rule['id']}",
        json={"source": "Checked with the accountant"},
        headers={**w.h[Role.ADMIN], "If-Match": str(rule["version"])},
    )


# The tests -----------------------------------------------------------------------------------------------------------


@pytest.fixture
def world(client: TestClient, db_session: Session, make: Make, auth: Auth, mailer: RecordingMailer) -> World:
    # The owner of the reference data is deactivated so it is not a person any scenario could mistake for an actor.
    owner = make(Role.ADMIN, active=False)
    lookups = create_lookups(db_session, owner)
    return World(client, db_session, make, auth, mailer, lookups, create_ledger(db_session, lookups, owner))


def snapshot(db: Session) -> dict[str, str]:
    """A fingerprint of every table except the audit log: any change to any column of any row changes it."""
    tables = db.execute(
        text(
            "SELECT tablename FROM pg_tables WHERE schemaname = 'public'"
            " AND tablename NOT IN ('audit_events', 'alembic_version')"
        )
    ).scalars()
    fingerprints: dict[str, str] = {}
    for table in sorted(tables):
        fingerprints[table] = db.execute(
            text(f"SELECT md5(coalesce(string_agg(t::text, ',' ORDER BY t::text), '')) FROM \"{table}\" t")
        ).scalar_one()
    return fingerprints


def audit_rows(db: Session) -> int:
    return int(db.execute(text("SELECT count(*) FROM audit_events")).scalar_one())


def mutating_operations(route_inventory: list[dict[str, Any]]) -> set[str]:
    return {op["operationId"] for op in route_inventory if op["method"] in {"POST", "PUT", "PATCH", "DELETE"}}


def test_every_mutating_route_has_a_scenario(route_inventory: list[dict[str, Any]]) -> None:
    found = mutating_operations(route_inventory)
    assert found - set(SCENARIOS) == set(), (
        "a mutating route has no audit scenario: write one, or say why it needs none"
    )
    assert set(SCENARIOS) - found == set(), "a scenario names a route that no longer exists"
    for name, entry in SCENARIOS.items():
        assert entry.audited or entry.why_not, f"{name} claims to need no audit row but gives no reason"


@pytest.mark.parametrize("operation", sorted(op for op, entry in SCENARIOS.items() if entry.audited))
def test_f3_a_change_and_its_audit_row_commit_together(
    world: World, app: FastAPI, monkeypatch: pytest.MonkeyPatch, operation: str
) -> None:
    send = SCENARIOS[operation].prepare(world)
    before, rows_before = snapshot(world.db), audit_rows(world.db)

    def audit_insert_fails(*_args: Any, **_kwargs: Any) -> None:
        raise RuntimeError("the audit log is unavailable")

    with monkeypatch.context() as patched:
        patched.setattr(audit_repository, "add", audit_insert_fails)
        failed = send()
    assert failed.status_code == 500, f"{operation}: with no audit row the request answered {failed.status_code}"
    changed = {t for t, fingerprint in snapshot(world.db).items() if fingerprint != before[t]}
    assert changed == set(), f"{operation}: changes were kept without their audit row in {sorted(changed)}"
    assert audit_rows(world.db) == rows_before

    succeeded = send()
    assert 200 <= succeeded.status_code < 300, f"{operation}: {succeeded.status_code} {succeeded.text}"
    assert audit_rows(world.db) > rows_before, f"{operation} changed data but left no audit row"


@pytest.mark.parametrize("operation", sorted(op for op, entry in SCENARIOS.items() if not entry.audited))
def test_a_route_that_needs_no_audit_row_says_why_and_still_works(world: World, operation: str) -> None:
    send = SCENARIOS[operation].prepare(world)
    rows_before = audit_rows(world.db)
    response = send()
    assert 200 <= response.status_code < 300, f"{operation}: {response.status_code} {response.text}"
    assert audit_rows(world.db) == rows_before
