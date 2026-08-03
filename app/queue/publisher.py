"""Публикация задачи обработки документа в RabbitMQ."""

import json
import logging
from uuid import UUID

import pika

from app.core.config import settings
from app.core.logging import get_request_id
from app.queue.setup import declare_process_queues

logger = logging.getLogger("docmind.queue.publisher")


def publish_document_process(document_id: UUID, request_id: str | None = None) -> None:
    """
    Кладет задачу в очередь.
    Сообщение простое: {"document_id": "...", "request_id": "..."}
    """
    params = pika.URLParameters(settings.rabbitmq_url)
    connection = pika.BlockingConnection(params)
    channel = connection.channel()

    # durable=True - очередь переживает рестарт брокера
    declare_process_queues(channel)

    rid = request_id or get_request_id()
    body = json.dumps({
        "document_id": str(document_id),
        "request_id": rid,
    })
    logger.info(
        "publishing to rabbit doc_id=%s request_id=%s queue=%s", 
        document_id,
        rid, 
        settings.rabbitmq_queue,
    )
    channel.basic_publish(
        exchange="",
        routing_key=settings.rabbitmq_queue,
        body=body,
        properties=pika.BasicProperties(
            delivery_mode=2,
            content_type="application/json",
        ),
    )
    logger.info("published to rabbit doc_id=%s", document_id)
    connection.close()
