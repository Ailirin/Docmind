"""Диагностические метрики: стадии обработки и состояние пула соединений."""

import pytest
from prometheus_client import REGISTRY
from sqlalchemy import create_engine
from sqlalchemy.pool import NullPool, QueuePool

from app.core.metrics import PROCESS_STAGES, observe_stage
from app.db.pool_metrics import DbPoolCollector


def _stage_count(stage: str) -> float:
    return (
        REGISTRY.get_sample_value("docmind_process_stage_duration_seconds_count", {"stage": stage})
        or 0.0
    )


def test_stage_series_are_precreated():
    for stage in PROCESS_STAGES:
        assert _stage_count(stage) >= 0
        assert (
            REGISTRY.get_sample_value(
                "docmind_process_stage_duration_seconds_count", {"stage": stage}
            )
            is not None
        )


def test_observe_stage_records_duration():
    before = _stage_count("classify")

    with observe_stage("classify"):
        pass

    assert _stage_count("classify") == before + 1


def test_observe_stage_records_even_when_stage_fails():
    """Время до сбоя тоже важно (например, таймаут LLM) — стадия пишется и при исключении."""
    before = _stage_count("extract")

    with pytest.raises(RuntimeError), observe_stage("extract"):
        raise RuntimeError("llm timeout")

    assert _stage_count("extract") == before + 1


def _sample(family, engine: str, state: str) -> float:
    return next(s.value for s in family.samples if s.labels == {"engine": engine, "state": state})


def test_pool_collector_reports_in_use_idle_and_limit():
    engine = create_engine(
        "sqlite://",
        poolclass=QueuePool,
        pool_size=2,
        max_overflow=1,
        connect_args={"check_same_thread": False},
    )
    collector = DbPoolCollector({"sync": engine}, limit=3)

    conn = engine.connect()
    try:
        (family,) = list(collector.collect())
        assert _sample(family, "sync", "in_use") == 1
        assert _sample(family, "sync", "limit") == 3
    finally:
        conn.close()

    (family,) = list(collector.collect())
    assert _sample(family, "sync", "in_use") == 0
    assert _sample(family, "sync", "idle") == 1


def test_pool_collector_skips_pools_without_statistics():
    engine = create_engine("sqlite://", poolclass=NullPool)

    (family,) = list(DbPoolCollector({"sync": engine}, limit=1).collect())

    assert family.samples == []


def test_pool_metrics_are_registered_for_app_engines():
    import app.db.session  # noqa: F401  (регистрирует коллектор при импорте)

    assert (
        REGISTRY.get_sample_value(
            "docmind_db_pool_connections", {"engine": "async", "state": "limit"}
        )
        is not None
    )
