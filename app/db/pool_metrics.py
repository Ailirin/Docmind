"""Метрики пула соединений SQLAlchemy (читаются в момент скрейпа, без накладных расходов)."""

from collections.abc import Iterable

from prometheus_client.core import GaugeMetricFamily
from sqlalchemy.engine import Engine


class DbPoolCollector:
    """
    docmind_db_pool_connections{engine, state}:
      in_use — соединения, выданные приложению прямо сейчас;
      idle   — свободные соединения в пуле;
      limit  — потолок (pool_size + max_overflow).

    Когда in_use упирается в limit, запросы начинают ждать соединения
    (pool_timeout), и это выглядит как «API тормозит», хотя БД ни при чём.
    """

    def __init__(self, engines: dict[str, Engine], limit: int) -> None:
        self._engines = engines
        self._limit = limit

    def collect(self) -> Iterable[GaugeMetricFamily]:
        family = GaugeMetricFamily(
            "docmind_db_pool_connections",
            "SQLAlchemy connection pool state",
            labels=["engine", "state"],
        )
        for name, engine in self._engines.items():
            pool = engine.pool
            if not hasattr(pool, "checkedout"):  # NullPool и т.п. не имеют статистики
                continue
            family.add_metric([name, "in_use"], pool.checkedout())
            family.add_metric([name, "idle"], pool.checkedin())
            family.add_metric([name, "limit"], self._limit)
        yield family
