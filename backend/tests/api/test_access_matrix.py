"""Story A3: every endpoint declares who may call it, and the API refuses everyone else.

The roles come from the OpenAPI file (`x-roles`), written by the same `roles(...)` helper that enforces them, so a
route cannot be added without declaring them, and this test grows with each endpoint. Run at review steps."""

from collections.abc import Callable
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.core.enums import Role
from app.models.user import User

PROBES = {"/health", "/ready", "/version"}
EXPECTED_PUBLIC = {
    "login",
    "refresh_session",
    "logout",
    "forgot_password",
    "reset_password",
    "inspect_invite",
    "accept_invite",
}
MISSING = "2000000000"  # no row has this id, so an allowed call cannot touch real data
SEND_BODY = {"POST", "PUT", "PATCH"}

pytestmark = pytest.mark.slow


def concrete(path: str) -> str:
    out = path
    for name in (
        "user_id",
        "invite_id",
        "vendor_id",
        "account_id",
        "category_id",
        "cost_center_id",
        "project_id",
        "period_id",
        "rule_id",
        "expense_id",
        "purchase_id",
        "attachment_id",
    ):
        out = out.replace("{" + name + "}", MISSING)
    return out.replace("{key}", "cash")


def operations(inventory: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [op for op in inventory if op["path"] not in PROBES]


def test_a3_every_operation_is_public_on_purpose_or_declares_its_roles(route_inventory: list[dict[str, Any]]) -> None:
    public = {op["operationId"] for op in operations(route_inventory) if op.get("x-public")}
    assert public == EXPECTED_PUBLIC, "a public route was added or removed; that is a security decision"
    valid = {role.value for role in Role}
    for op in operations(route_inventory):
        if op.get("x-public"):
            assert "x-roles" not in op
            continue
        assert op.get("x-roles"), f"{op['method']} {op['path']} declares no roles"
        assert set(op["x-roles"]) <= valid


def test_a3_nothing_but_the_public_screens_and_probes_answers_without_a_sign_in(
    client: TestClient, route_inventory: list[dict[str, Any]]
) -> None:
    for op in operations(route_inventory):
        if op.get("x-public"):
            continue
        response = client.request(op["method"], concrete(op["path"]), json={} if op["method"] in SEND_BODY else None)
        assert response.status_code == 401, (
            f"{op['method']} {op['path']} answered {response.status_code} without a sign-in"
        )
        assert response.json()["code"] == "UNAUTHENTICATED"


@pytest.mark.parametrize("role", list(Role))
def test_a3_each_role_is_refused_exactly_where_it_should_be(
    client: TestClient,
    route_inventory: list[dict[str, Any]],
    make: Callable[..., User],
    auth: Callable[[User], dict[str, str]],
    role: Role,
) -> None:
    headers = {**auth(make(role)), "If-Match": "1"}
    refused = allowed = 0
    for op in operations(route_inventory):
        if op.get("x-public"):
            continue
        response = client.request(
            op["method"], concrete(op["path"]), headers=headers, json={} if op["method"] in SEND_BODY else None
        )
        where = f"{role.value} {op['method']} {op['path']} -> {response.status_code}"
        if role.value in op["x-roles"]:
            assert response.status_code not in (401, 403), where
            allowed += 1
        else:
            assert response.status_code == 403, where
            assert response.json()["code"] == "FORBIDDEN", where
            refused += 1
    assert allowed > 0
    if role is not Role.ADMIN:
        assert refused > 0  # only the Admin can do everything


def test_a3_the_403_names_the_role_that_is_needed(
    client: TestClient, make: Callable[..., User], auth: Callable[[User], dict[str, str]]
) -> None:
    response = client.get("/api/v1/users", headers=auth(make(Role.STAFF)))
    assert response.status_code == 403
    assert "Admin" in response.json()["detail"]
