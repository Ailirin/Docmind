"""Единая настройка логирования в stdout (удобно для Docker)."""

import logging
import os
import sys
from contextvars import ContextVar

request_id_var: ContextVar[str] = ContextVar("request_id", default="-")


def get_request_id() -> str:
    return request_id_var.get()


def set_request_id(value: str):
    """Ставит request_id. Возвращает token для reset в finally."""
    return request_id_var.set(value)


def clear_request_id(token) -> None:
    request_id_var.reset(token)


class RequestIdFilter(logging.Filter):
    """Подставляет request_id из ContextVar в каждую запись лога."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get()
        return True


def configure_logging(level: str | None = None) -> None:
    """
    Настройка логирования в stdout.
    Важно для Docker: логи должны идти в консоль.
    """
    log_level = (level or os.getenv("LOG_LEVEL", "INFO")).upper()

    logging.basicConfig(
        level=log_level,
        format="%(asctime)s %(levelname)s [%(name)s] request_id=%(request_id)s %(message)s",
        stream=sys.stdout,
        force=True,  # чтобы конфиг применялся одинаково и для worker
    )
    root = logging.getLogger()
    request_id_filter = RequestIdFilter()
    for handler in root.handlers:
        handler.addFilter(request_id_filter)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
