"""Регрессионные тесты безопасности: fail-closed секреты и ReDoS в mock-экстракторе."""

import base64
import time

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.core.config import Settings
from app.core.security import constant_time_equals
from app.main import app
from app.models.document import DocumentType
from app.services.extractors.mock import MockEntityExtractor

# ── constant_time_equals ─────────────────────────────────────────────────────


def test_equal_secrets_match():
    assert constant_time_equals("s3cret", "s3cret") is True


def test_different_secrets_do_not_match():
    assert constant_time_equals("s3cret", "other") is False


def test_empty_expected_secret_never_authenticates():
    """Главная регрессия: compare_digest('', '') == True пускал бы по пустому ключу."""
    assert constant_time_equals("", "") is False
    assert constant_time_equals("anything", "") is False


def test_unicode_secret_is_supported():
    assert constant_time_equals("пароль", "пароль") is True


# ── пустые секреты не дают обойти аутентификацию ─────────────────────────────


def test_api_rejects_empty_key_when_configured_key_is_empty(monkeypatch):
    monkeypatch.setattr("app.api.deps.settings.api_key", "")

    with TestClient(app) as client:
        response = client.get("/api/v1/documents", headers={"X-API-Key": ""})

    assert response.status_code == 401


def test_metrics_rejects_empty_password_when_configured_password_is_empty(monkeypatch):
    monkeypatch.setattr("app.main.settings.metrics_username", "metrics")
    monkeypatch.setattr("app.main.settings.metrics_password", "")
    token = base64.b64encode(b"metrics:").decode("ascii")

    with TestClient(app) as client:
        response = client.get("/metrics/", headers={"Authorization": f"Basic {token}"})

    assert response.status_code == 401


def test_admin_rejects_empty_password_when_configured_password_is_empty(monkeypatch):
    monkeypatch.setattr("app.admin.auth.settings.admin_username", "admin")
    monkeypatch.setattr("app.admin.auth.settings.admin_password", "")

    with TestClient(app) as client:
        response = client.get("/admin/", auth=("admin", ""))

    assert response.status_code == 401


# ── валидация настроек ───────────────────────────────────────────────────────


@pytest.mark.parametrize("field", ["api_key", "admin_password", "metrics_password"])
def test_settings_refuse_empty_secret(field):
    """Приложение не стартует с пустым секретом (fail closed), даже в debug."""
    with pytest.raises(ValidationError, match="не может быть пустым"):
        Settings(_env_file=None, debug=True, **{field: ""})


def test_settings_refuse_whitespace_only_secret():
    with pytest.raises(ValidationError):
        Settings(_env_file=None, api_key="   ")


def test_settings_warn_on_weak_admin_password_from_compose():
    """admin_password=change-me (значение из docker-compose) тоже считается слабым."""
    with pytest.warns(UserWarning, match="admin_password"):
        Settings(
            _env_file=None,
            api_key="a-strong-key",
            admin_password="change-me",
            metrics_password="a-strong-password",
        )


def test_settings_ignore_compose_only_variables_in_env_file(tmp_path):
    """.env общий с docker compose: его переменные не должны ронять приложение."""
    env_file = tmp_path / ".env"
    env_file.write_text(
        "API_KEY=a-strong-key\n"
        "ADMIN_PASSWORD=a-strong-admin-password\n"
        "METRICS_PASSWORD=a-strong-metrics-password\n"
        "POSTGRES_PASSWORD=pg\n"
        "GRAFANA_ADMIN_PASSWORD=grafana\n",
        encoding="utf-8",
    )

    cfg = Settings(_env_file=env_file)

    assert cfg.api_key == "a-strong-key"


def test_settings_no_warning_for_strong_secrets(recwarn):
    Settings(
        _env_file=None,
        api_key="a-strong-key",
        admin_password="a-strong-admin-password",
        metrics_password="a-strong-metrics-password",
    )
    assert not [w for w in recwarn if "SECURITY" in str(w.message)]


# ── ReDoS в MockEntityExtractor ──────────────────────────────────────────────

_PATHOLOGICAL = " " * 20_000


@pytest.mark.parametrize(
    "text",
    [
        f"Patient: a{_PATHOLOGICAL}b",
        f"Diagnosis: J06.9 a{_PATHOLOGICAL}b",
        f"Medication: a{_PATHOLOGICAL}b",
        f"Dosage: a{_PATHOLOGICAL}b",
        f"Rp: a{_PATHOLOGICAL}b",
    ],
    ids=["patient", "diagnosis", "medication", "dosage", "rp"],
)
def test_mock_extractor_is_linear_on_long_whitespace(text):
    """
    Раньше `\\s+` в терминаторе давал O(n^2): 16 000 пробелов ≈ 15 с, и один PDF
    вешал воркер. Теперь должно укладываться в доли секунды (запас на медленный CI).
    """
    started = time.perf_counter()
    MockEntityExtractor().extract(text, DocumentType.DISCHARGE)
    elapsed = time.perf_counter() - started

    assert elapsed < 2.0, f"regex стал нелинейным: {elapsed:.1f} с"
