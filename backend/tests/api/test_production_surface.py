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
