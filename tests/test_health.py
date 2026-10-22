"""Unit-тесты health-эндпоинтов."""


async def _ok() -> bool:
    return True


async def _fail() -> bool:
    return False


def test_health(client):
    test_client, _ = client
    response = test_client.get("/api/v1/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert "app" in body
    assert "version" in body


def test_health_ready_ok(client, monkeypatch):
    test_client, _ = client
    monkeypatch.setattr("app.api.v1.router.check_database", _ok)
    monkeypatch.setattr("app.api.v1.router.check_rabbitmq", _ok)

    response = test_client.get("/api/v1/health/ready")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["database"] == "ok"
    assert body["rabbitmq"] == "ok"


def test_health_ready_db_down(client, monkeypatch):
    test_client, _ = client
    monkeypatch.setattr("app.api.v1.router.check_database", _fail)
    monkeypatch.setattr("app.api.v1.router.check_rabbitmq", _ok)

    response = test_client.get("/api/v1/health/ready")

    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "unavailable"
    assert body["database"] == "error"
    assert body["rabbitmq"] == "ok"


def test_health_ready_without_api_key(client):
    test_client, _ = client
    test_client.headers.pop("X-API-Key", None)

    # без моков: в unit-тестах БД/Rabbit недоступны → 200 или 503, но не 401
    response = test_client.get("/api/v1/health/ready")
    assert response.status_code in (200, 503)
