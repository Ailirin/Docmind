"""Единая настройка логирования в stdout (удобно для Docker/Loki)."""

import logging
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


def _build_text_handler() -> logging.StreamHandler:
    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter(
        "%(asctime)s %(levelname)s [%(name)s] request_id=%(request_id)s %(message)s"
    )
    handler.setFormatter(formatter)
    return handler


def _build_json_handler() -> logging.StreamHandler:
    """JSON-формат для Loki/ELK: каждая строка — валидный JSON-объект."""
    try:
        from pythonjsonlogger.jsonlogger import JsonFormatter  # type: ignore[import-untyped]
    except ImportError as exc:
        raise RuntimeError(
            "python-json-logger не установлен. Добавьте его в requirements.txt."
        ) from exc

    handler = logging.StreamHandler(sys.stdout)
    formatter = JsonFormatter(
        fmt="%(asctime)s %(levelname)s %(name)s %(request_id)s %(message)s",
        rename_fields={"levelname": "level", "asctime": "timestamp", "name": "logger"},
    )
    handler.setFormatter(formatter)
    return handler


def configure_logging(level: str | None = None, log_format: str | None = None) -> None:
    """
    Настройка логирования в stdout.

    Args:
        level: уровень логирования (INFO, DEBUG, …). Если None — берётся
               из настроек приложения или переменной LOG_LEVEL.
        log_format: "text" (default) или "json" (для Docker/Loki).
    """
    # Ленивый импорт чтобы не создавать циклическую зависимость settings → logging → settings
    from app.core.config import settings as _settings

    resolved_level = (level or _settings.log_level).upper()
    resolved_format = (log_format or _settings.log_format).lower()

    if resolved_format == "json":
        handler = _build_json_handler()
    else:
        handler = _build_text_handler()

    request_id_filter = RequestIdFilter()
    handler.addFilter(request_id_filter)

    root = logging.getLogger()
    root.setLevel(resolved_level)
    # Сбрасываем старые обработчики, чтобы force=True не нужен
    root.handlers.clear()
    root.addHandler(handler)

    # Заглушаем шумные библиотеки
    logging.getLogger("pika").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("openai").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
