import io
import json
import logging
from collections.abc import Iterator
from datetime import datetime
from decimal import Decimal
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.core.enums import Role
from app.core.errors import (
    ConflictError,
    ErrorCode,
    FieldError,
    NotFoundError,
    RateLimitedError,
)
from app.core.logging import CorrelationFilter, JsonFormatter
from app.db import get_session
from app.schemas.base import Money, RequestModel, UtcInstant


class ProbeBody(RequestModel):
    amount: Money
    happened_at: UtcInstant | None = None


@pytest.fixture
def probe_app(app: FastAPI) -> FastAPI:
    """The real app plus routes that fail in every way the handlers must cover."""

    def raise_domain() -> None:
        raise ConflictError("That name is taken.", errors=[FieldError("name", "Already in use", "duplicate")])

    def raise_not_found() -> None:
        raise NotFoundError("No such vendor.")

    def raise_rate_limited() -> None:
        raise RateLimitedError("Too many attempts.", retry_after_seconds=90)

    def explode() -> None:
        raise RuntimeError("boom: secret internal detail")

    def echo(body: ProbeBody) -> dict[str, Any]:
        return {"amount": str(body.amount)}

    app.add_api_route("/api/v1/_probe/conflict", raise_domain, methods=["GET"])
    app.add_api_route("/api/v1/_probe/missing", raise_not_found, methods=["GET"])
    app.add_api_route("/api/v1/_probe/limited", raise_rate_limited, methods=["GET"])
    app.add_api_route("/api/v1/_probe/explode", explode, methods=["GET"])
    app.add_api_route("/api/v1/_probe/echo", echo, methods=["POST"])
    return app


@pytest.fixture
def probe(probe_app: FastAPI) -> Iterator[TestClient]:
    with TestClient(probe_app, raise_server_exceptions=False) as test_client:
        yield test_client


def assert_problem(response: Any, status: int, code: ErrorCode) -> dict[str, Any]:
    assert response.status_code == status
    assert response.headers["content-type"].startswith("application/problem+json")
    body: dict[str, Any] = response.json()
    assert body["code"] == code.value
    assert body["status"] == status
    assert body["type"] == f"urn:daftar:error:{code.value}"
    assert body["correlation_id"] == response.headers["X-Correlation-ID"]
    return body


# Probes --------------------------------------------------------------------------------------------------------------


def test_health(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_ready_when_the_database_answers(client: TestClient) -> None:
    assert client.get("/ready").json() == {"status": "ok"}


def test_ready_is_503_when_the_database_is_down(app: FastAPI) -> None:
    dead = create_engine("postgresql+psycopg://x:y@127.0.0.1:1/none", connect_args={"connect_timeout": 1})
    app.dependency_overrides[get_session] = lambda: Session(bind=dead)
    with TestClient(app, raise_server_exceptions=False) as test_client:
        body = assert_problem(test_client.get("/ready"), 503, ErrorCode.SERVICE_UNAVAILABLE)
    assert "127.0.0.1" not in json.dumps(body)


def test_version_reports_the_git_sha(client: TestClient) -> None:
    body = client.get("/version").json()
    assert body["version"] == "0.1.0"
    assert body["git_sha"]


def test_me_reports_the_user_and_the_display_zone(client: TestClient, make: Any, auth: Any) -> None:
    user = make(Role.STAFF)
    body = client.get("/api/v1/me", headers=auth(user)).json()
    assert body["display_timezone"] == "Asia/Karachi"
    assert (body["id"], body["email"], body["role"]) == (user.id, user.email, "staff")
    assert "password_hash" not in body


def test_me_needs_a_sign_in(client: TestClient) -> None:
    assert_problem(client.get("/api/v1/me"), 401, ErrorCode.UNAUTHENTICATED)


# Errors --------------------------------------------------------------------------------------------------------------


def test_unknown_path_is_a_problem_with_a_code(client: TestClient) -> None:
    assert_problem(client.get("/api/v1/nothing-here"), 404, ErrorCode.NOT_FOUND)


def test_wrong_method_is_a_problem_and_keeps_the_allow_header(client: TestClient) -> None:
    response = client.post("/health")
    assert_problem(response, 405, ErrorCode.METHOD_NOT_ALLOWED)
    assert "GET" in response.headers["allow"]


def test_domain_errors_carry_their_code_and_field_errors(probe: TestClient) -> None:
    body = assert_problem(probe.get("/api/v1/_probe/conflict"), 409, ErrorCode.CONFLICT)
    assert body["errors"] == [{"field": "name", "message": "Already in use", "code": "duplicate"}]
    assert_problem(probe.get("/api/v1/_probe/missing"), 404, ErrorCode.NOT_FOUND)


def test_rate_limited_answers_429_with_retry_after(probe: TestClient) -> None:
    response = probe.get("/api/v1/_probe/limited")
    assert_problem(response, 429, ErrorCode.RATE_LIMITED)
    assert response.headers["Retry-After"] == "90"


def test_unknown_fields_are_rejected_with_a_field_path(probe: TestClient) -> None:
    body = assert_problem(
        probe.post("/api/v1/_probe/echo", json={"amount": "1.00", "role": "admin"}),
        422,
        ErrorCode.VALIDATION_ERROR,
    )
    assert [e["field"] for e in body["errors"]] == ["role"]


@pytest.mark.parametrize("amount", [10.5, "1.005", "-1.00", "abc"])
def test_money_must_be_an_exact_string(probe: TestClient, amount: object) -> None:
    body = assert_problem(probe.post("/api/v1/_probe/echo", json={"amount": amount}), 422, ErrorCode.VALIDATION_ERROR)
    assert body["errors"][0]["field"] == "amount"


def test_a_naive_timestamp_is_rejected(probe: TestClient) -> None:
    payload = {"amount": "1.00", "happened_at": "2026-10-12T14:05:00"}
    body = assert_problem(probe.post("/api/v1/_probe/echo", json=payload), 422, ErrorCode.VALIDATION_ERROR)
    assert body["errors"][0]["field"] == "happened_at"


def test_a_valid_body_passes(probe: TestClient) -> None:
    response = probe.post("/api/v1/_probe/echo", json={"amount": "1250.5", "happened_at": "2026-10-12T14:05:00Z"})
    assert response.json() == {"amount": str(Decimal("1250.50"))}


def test_an_unhandled_error_is_a_bare_500_with_a_correlation_id(
    probe: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.ERROR, logger="app.errors"):
        response = probe.get("/api/v1/_probe/explode")
    body = assert_problem(response, 500, ErrorCode.INTERNAL_ERROR)
    for leaked in ("boom", "Traceback", "secret"):
        assert leaked not in response.text
    assert set(body) == {"type", "title", "status", "detail", "code", "correlation_id", "errors"}
    # The trace is in the log, tied to the same id.
    assert any(r.exc_info and "boom" in str(r.exc_info[1]) for r in caplog.records)


# Correlation id and logs ---------------------------------------------------------------------------------------------


def test_a_valid_incoming_correlation_id_is_kept_and_an_odd_one_replaced(client: TestClient) -> None:
    assert (
        client.get("/health", headers={"X-Correlation-ID": "req-abc-12345"}).headers["X-Correlation-ID"]
        == "req-abc-12345"
    )
    replaced = client.get("/health", headers={"X-Correlation-ID": "bad value with spaces!"}).headers["X-Correlation-ID"]
    assert replaced != "bad value with spaces!"
    assert len(replaced) == 32


def test_every_request_gets_its_own_id(client: TestClient) -> None:
    ids = {client.get("/health").headers["X-Correlation-ID"] for _ in range(5)}
    assert len(ids) == 5


def test_the_request_log_has_the_correlation_id_and_no_secrets(client: TestClient) -> None:
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JsonFormatter())
    handler.addFilter(CorrelationFilter())
    # Only the server's own loggers: the test client logs the full URL on its side, which is not our output.
    app_logger = logging.getLogger("app")
    app_logger.addHandler(handler)
    previous = app_logger.level
    app_logger.setLevel(logging.INFO)
    try:
        response = client.get(
            "/health?email=ayesha@example.com&token=reset-token-xyz",
            headers={"Authorization": "Bearer access-token-123", "Cookie": "session=cookie-value-456"},
        )
    finally:
        app_logger.removeHandler(handler)
        app_logger.setLevel(previous)
    lines = [json.loads(line) for line in stream.getvalue().splitlines()]
    request_lines = [line for line in lines if line["message"] == "request"]
    assert len(request_lines) == 1
    entry = request_lines[0]
    assert entry["correlation_id"] == response.headers["X-Correlation-ID"]
    assert (entry["method"], entry["path"], entry["status"]) == ("GET", "/health", 200)
    assert datetime.fromisoformat(entry["ts"]).tzinfo is not None
    assert entry["ts"].endswith("Z")
    logged = stream.getvalue()
    for secret in ("ayesha@example.com", "reset-token-xyz", "access-token-123", "cookie-value-456"):
        assert secret not in logged
