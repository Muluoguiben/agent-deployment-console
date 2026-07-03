from fastapi.testclient import TestClient

from agent_service.main import app

client = TestClient(app)


def test_healthz() -> None:
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_meta() -> None:
    resp = client.get("/api/meta")
    assert resp.status_code == 200
    assert resp.json()["milestone"] == "M0"
