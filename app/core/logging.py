import logging
import os
import sys


def configure_logging(level: str | None = None) -> None:
    """
    Настройка логирования в stdout.
    Важно для Docker: логи должны идти в консоль.
    """
    log_level = (level or os.getenv("LOG_LEVEL", "INFO")).upper()

    logging.basicConfig(
        level=log_level,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        stream=sys.stdout,
        force=True,  # чтобы конфиг применялся одинаково и для worker
    )


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
