"""Consumer RabbitMQ: читает document_id и запускает process_document."""

import json
import logging
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


def handle_message(ch, method, properties, body: bytes) -> None:
    db = SessionLocal()
    token = None
    try:
        payload = json.loads(body.decode("utf-8"))
        document_id = UUID(payload["document_id"])

        # id из очереди(если старое сообщение без поля - будет "-")
        rid = payload.get("request_id") or "-"
        token = set_request_id(rid)

        logger.info("Processing document_id=%s", document_id)

        process_document(db, document_id)
        ch.basic_ack(delivery_tag=method.delivery_tag)
        logger.info("Done document_id=%s", document_id)
    except Exception:
        logger.exception("Failed to process message: %s", body)
        logger.warning("Sending message to DLQ queue=%s", settings.rabbitmq_dlq)
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
    finally:
        if token is not None:
            clear_request_id(token)
        db.close()


def main() -> None:
    start_http_server(8001)
    logger.info("Worker metrics on :8001/metrics")
    params = pika.URLParameters(settings.rabbitmq_url)

    connection = None
    for attempt in range(1, 31):
        try:
            connection = pika.BlockingConnection(params)
            break
        except pika.exceptions.AMQPConnectionError:
            logger.warning(
                "RabbitMQ unavailable (attempt %s/30), retry in 2s...",
                attempt,
            )
            time.sleep(2)

    if connection is None:
        raise RuntimeError("Could not connect to RabbitMQ after retries")

    channel = connection.channel()
    declare_process_queues(channel)
    channel.basic_qos(prefetch_count=1)
    channel.basic_consume(
        queue=settings.rabbitmq_queue,
        on_message_callback=handle_message,
    )

    logger.info("Worker started. Queue=%s", settings.rabbitmq_queue)
    channel.start_consuming()


if __name__ == "__main__":
    main()
