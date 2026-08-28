from __future__ import annotations

from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.security import generate_encryption_key

TEST_TOKEN = "test-founder-token-with-more-than-thirty-two-characters"


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(
        _env_file=None,
        environment="test",
        database_url=f"sqlite:///{tmp_path / 'test.db'}",
        admin_token=TEST_TOKEN,
        encryption_key=generate_encryption_key(),
        job_token="test-job-token-with-more-than-thirty-two-characters",
    )


@pytest.fixture
def client(settings: Settings) -> Generator[TestClient, None, None]:
    with TestClient(create_app(settings)) as test_client:
        yield test_client


@pytest.fixture
def authenticated(client: TestClient) -> dict[str, str]:
    response = client.post("/api/session", json={"token": TEST_TOKEN})
    assert response.status_code == 200
    csrf = response.json()["csrf_token"]
    me = client.get("/api/me").json()
    return {"csrf": csrf, "workspace_id": me["workspaces"][0]["id"]}
