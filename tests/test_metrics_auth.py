import base64

from fastapi.testclient import TestClient

from app.main import app


def test_metrics_requires_auth(monkeypatch):
    monkeypatch.setattr("app.main.settings.metrics_username", "metrics")
    monkeypatch.setattr("app.main.settings.metrics_password", "secret")

    client = TestClient(app)
    assert client.get("/metrics").status_code == 401

    token = base64.b64encode(b"metrics:secret").decode("ascii")
    ok = client.get("/metrics", headers={"Authorization": f"Basic {token}"})
    assert ok.status_code == 200
