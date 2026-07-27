"""Публикация задачи обработки документа в RabbitMQ."""

import json
import logging
from uuid import UUID

import pika

from app.core.config import settings

logger = logging.getLogger("docmind.queue.publisher")


def publish_document_process(document_id: UUID) -> None:
    """
    Кладет задачу в очередь.
    Сообщение простое: {"document_id": "..."}
    """
    params = pika.URLParameters(settings.rabbitmq_url)
    connection = pika.BlockingConnection(params)
    channel = connection.channel()

    # durable=True - очередь переживает рестарт брокера
    channel.queue_declare(queue=settings.rabbitmq_queue, durable=True)

    body = json.dumps({"document_id": str(document_id)})
    logger.info("publishing to rabbit doc_id=%s queue=%s", document_id, settings.rabbitmq_queue)
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
