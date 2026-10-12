from typing import Any

from fastapi import FastAPI

from app.core.errors import ErrorCode

PROBE_PATHS = {"/health", "/ready", "/version"}
DOCUMENTED_ERRORS = {"400", "401", "403", "404", "409", "413", "422", "429", "500"}


def test_every_operation_has_a_unique_id(route_inventory: list[dict[str, Any]]) -> None:
    ids = [operation["operationId"] for operation in route_inventory]
    assert len(ids) == len(set(ids))
    assert all(not identifier.startswith("get_api_") for identifier in ids), "ids should be named, not generated"


def test_every_path_is_a_probe_or_under_the_versioned_base(route_inventory: list[dict[str, Any]]) -> None:
    for operation in route_inventory:
        assert operation["path"] in PROBE_PATHS or operation["path"].startswith("/api/v1/"), operation["path"]


def test_versioned_operations_document_every_error_status(route_inventory: list[dict[str, Any]]) -> None:
    for operation in route_inventory:
        if operation["path"].startswith("/api/v1/"):
            assert set(operation["responses"]) >= DOCUMENTED_ERRORS, operation["path"]


def test_the_error_code_enum_is_published(app: FastAPI) -> None:
    schema = app.openapi()["components"]["schemas"]
    assert set(schema["ErrorCode"]["enum"]) == {code.value for code in ErrorCode}
    assert "ProblemDetail" in schema


def test_the_inventory_is_not_empty(route_inventory: list[dict[str, Any]]) -> None:
    assert {(o["method"], o["path"]) for o in route_inventory} >= {
        ("GET", "/health"),
        ("GET", "/ready"),
        ("GET", "/version"),
        ("GET", "/api/v1/me"),
    }
