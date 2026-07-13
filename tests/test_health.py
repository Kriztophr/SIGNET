from fastapi.testclient import TestClient

from app.main import create_app


def test_health_returns_ok() -> None:
    """The health endpoint reports ok with the product name and version."""
    client = TestClient(create_app())
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["name"] == "Signet"
    assert body["version"] == "0.1.0"


def test_docs_exposed_outside_production() -> None:
    client = TestClient(create_app())
    assert client.get("/docs").status_code == 200
