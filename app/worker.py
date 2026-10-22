"""Consumer RabbitMQ: читает document_id и запускает process_document.

Особенности:
- Graceful shutdown по SIGTERM/SIGINT: дожидаемся завершения текущего сообщения.
- Exponential backoff при потере соединения с RabbitMQ.
- Метрики worker-а на отдельном порту :8001.
"""

import json
import logging
import signal
import sys
import time
from uuid import UUID

import pika
from prometheus_client import start_http_server

from app.core.config import settings
from app.core.logging import clear_request_id, configure_logging, set_request_id
from app.db.session import SessionLocal
from app.queue.setup import declare_process_queues
from app.services.processor import process_document

configure_logging()

logger = logging.getLogger("docmind.worker")

# ── Graceful shutdown ────────────────────────────────────────────────────────
_shutdown_requested = False


def _handle_signal(signum, frame) -> None:  # noqa: ANN001
    global _shutdown_requested
    logger.info("Signal %s received, finishing current message then shutting down...", signum)
    _shutdown_requested = True


signal.signal(signal.SIGTERM, _handle_signal)
signal.signal(signal.SIGINT, _handle_signal)
# ────────────────────────────────────────────────────────────────────────────


def handle_message(ch, method, properties, body: bytes) -> None:
    """Обрабатывает одно сообщение из очереди."""
    db = SessionLocal()
    token = None
    try:
        payload = json.loads(body.decode("utf-8"))
        document_id = UUID(payload["document_id"])

        # id из очереди (если старое сообщение без поля — будет "-")
        rid = payload.get("request_id") or "-"
        token = set_request_id(rid)

        logger.info("Processing document_id=%s", document_id)
        process_document(db, document_id)
        ch.basic_ack(delivery_tag=method.delivery_tag)
        logger.info("Done document_id=%s", document_id)

    except json.JSONDecodeError:
        logger.exception("Malformed JSON in message body, sending to DLQ: %s", body)
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

    except Exception:
        logger.exception("Failed to process message: %s", body)
        logger.warning("Sending message to DLQ queue=%s", settings.rabbitmq_dlq)
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

    finally:
        if token is not None:
            clear_request_id(token)
        db.close()


def _connect_with_backoff(params: pika.URLParameters, max_attempts: int = 30) -> pika.BlockingConnection:
    """Подключается к RabbitMQ с экспоненциальным backoff."""
    delay = 2.0
    for attempt in range(1, max_attempts + 1):
        try:
            connection = pika.BlockingConnection(params)
            logger.info("Connected to RabbitMQ (attempt %s)", attempt)
            return connection
        except pika.exceptions.AMQPConnectionError:
            if attempt == max_attempts:
                logger.error("Could not connect to RabbitMQ after %s attempts", max_attempts)
                raise
            logger.warning(
                "RabbitMQ unavailable (attempt %s/%s), retry in %.1fs...",
                attempt,
                max_attempts,
                delay,
            )
            time.sleep(delay)
            delay = min(delay * 1.5, 30.0)  # backoff до 30 секунд

    raise RuntimeError("Could not connect to RabbitMQ after retries")


def main() -> None:
    start_http_server(8001)
    logger.info("Worker metrics on :8001/metrics")

    params = pika.URLParameters(settings.rabbitmq_url)
    connection = _connect_with_backoff(params)

    channel = connection.channel()
    declare_process_queues(channel)
    channel.basic_qos(prefetch_count=1)
    channel.basic_consume(
        queue=settings.rabbitmq_queue,
        on_message_callback=handle_message,
    )

    logger.info("Worker started. Queue=%s", settings.rabbitmq_queue)

    try:
        while not _shutdown_requested:
            # process_data_events с таймаутом позволяет проверять флаг shutdown
            connection.process_data_events(time_limit=1)
    except Exception:
        logger.exception("Unexpected error in worker loop")
        sys.exit(1)
    finally:
        logger.info("Worker shutting down gracefully")
        if connection.is_open:
            connection.close()


if __name__ == "__main__":
    main()
