"""A live API does not publish its interactive documentation or its schema, but keeps its probes."""

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


@pytest.mark.parametrize(("environment", "published"), [("development", True), ("production", False)])
def test_the_documentation_pages_exist_only_outside_production(
    settings: Settings, environment: str, published: bool
) -> None:
    configured = settings.model_copy(update={"environment": environment})
    client = TestClient(create_app(configured))
    for path in ("/docs", "/redoc", "/openapi.json"):
        assert (client.get(path).status_code == 200) is published, path
    assert client.get("/health").status_code == 200
    assert client.get("/version").status_code == 200


@pytest.mark.parametrize(("environment", "hsts"), [("development", False), ("production", True)])
def test_every_answer_carries_the_security_headers_and_hsts_only_in_production(
    settings: Settings, environment: str, hsts: bool
) -> None:
    client = TestClient(create_app(settings.model_copy(update={"environment": environment})))
    for path in ("/health", "/api/v1/me"):  # an answer and an error answer alike
        headers = client.get(path).headers
        assert headers["x-content-type-options"] == "nosniff"
        assert headers["x-frame-options"] == "DENY"
        assert headers["referrer-policy"] == "no-referrer"
        assert ("strict-transport-security" in headers) is hsts
