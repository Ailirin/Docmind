"""HTTP-метрики: шаблон роута вместо реального URL, статусы, исключения, игнор /metrics."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from prometheus_client import REGISTRY

from app.core.http_metrics import HttpMetricsMiddleware


def _value(name: str, **labels: str) -> float:
    return REGISTRY.get_sample_value(name, labels) or 0.0


@pytest.fixture
def client() -> TestClient:
    app = FastAPI()
    app.add_middleware(HttpMetricsMiddleware)

    @app.get("/items/{item_id}")
    def get_item(item_id: str):
        return {"id": item_id}

    @app.get("/boom")
    def boom():
        raise RuntimeError("boom")

    @app.get("/metrics/x")
    def metrics_like():
        return {"ok": True}

    return TestClient(app, raise_server_exceptions=False)


def test_route_template_is_used_instead_of_real_path(client):
    labels = {"method": "GET", "route": "/items/{item_id}", "status": "200"}
    before = _value("docmind_http_requests_total", **labels)

    client.get("/items/abc")
    client.get("/items/def")

    assert _value("docmind_http_requests_total", **labels) == before + 2
    # Реальные значения не должны попадать в лейблы (кардинальность!).
    assert (
        _value("docmind_http_requests_total", method="GET", route="/items/abc", status="200") == 0
    )


def test_unmatched_paths_are_grouped_in_one_series(client):
    labels = {"method": "GET", "route": "unmatched", "status": "404"}
    before = _value("docmind_http_requests_total", **labels)

    client.get("/no-such-1")
    client.get("/no-such-2")

    assert _value("docmind_http_requests_total", **labels) == before + 2


def test_unhandled_exception_is_counted_as_500(client):
    labels = {"method": "GET", "route": "/boom", "status": "500"}
    before = _value("docmind_http_requests_total", **labels)

    assert client.get("/boom").status_code == 500

    assert _value("docmind_http_requests_total", **labels) == before + 1


def test_duration_histogram_is_observed(client):
    labels = {"method": "GET", "route": "/items/{item_id}"}
    before = _value("docmind_http_request_duration_seconds_count", **labels)

    client.get("/items/1")

    assert _value("docmind_http_request_duration_seconds_count", **labels) == before + 1


def test_metrics_paths_are_not_counted(client):
    before = sum(
        s.value
        for m in REGISTRY.collect()
        if m.name == "docmind_http_requests"
        for s in m.samples
        if s.name.endswith("_total") and s.labels.get("route") == "/metrics/x"
    )

    assert client.get("/metrics/x").status_code == 200

    after = sum(
        s.value
        for m in REGISTRY.collect()
        if m.name == "docmind_http_requests"
        for s in m.samples
        if s.name.endswith("_total") and s.labels.get("route") == "/metrics/x"
    )
    assert after == before == 0


def test_process_metrics_series_exist_before_first_event():
    """Серии предсозданы, чтобы rate()/increase() на дашборде не давали «No data»."""
    for status in ("done", "failed"):
        assert (
            REGISTRY.get_sample_value("docmind_documents_processed_total", {"status": status})
            is not None
        )
    for result in ("success", "validation_error", "request_error"):
        assert (
            REGISTRY.get_sample_value("docmind_llm_extractions_total", {"result": result})
            is not None
        )
