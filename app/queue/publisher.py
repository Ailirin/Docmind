"""Публикация задачи обработки документа в RabbitMQ."""

import json
import logging
import threading
from uuid import UUID

import pika
from pika.exceptions import AMQPChannelError, AMQPConnectionError

from app.core.config import settings
from app.core.logging import get_request_id
from app.queue.setup import declare_process_queues

logger = logging.getLogger("docmind.queue.publisher")

_connection: pika.BlockingConnection | None = None
_channel: pika.adapters.blocking_connection.BlockingChannel | None = None

# pika.BlockingConnection НЕ потокобезопасна, а API вызывает publisher из пула потоков
# (anyio.to_thread). RLock сериализует доступ к общему соединению/каналу.
_lock = threading.RLock()


def _get_channel():
    """Вернуть живой канал. При обрыве — пересоздать соединение."""
    global _connection, _channel

    if (
        _channel is not None
        and _channel.is_open
        and _connection is not None
        and _connection.is_open
    ):
        return _channel

    # старое соединение могло умереть — закрываем без шума
    close_publisher()

    params = pika.URLParameters(settings.rabbitmq_url)
    _connection = pika.BlockingConnection(params)
    _channel = _connection.channel()
    declare_process_queues(_channel)
    logger.info("RabbitMQ publisher connected")
    return _channel


def close_publisher() -> None:
    """Закрыть соединение publisher (вызывать при shutdown API)."""
    global _connection, _channel

    with _lock:
        if _channel is not None:
            try:
                if _channel.is_open:
                    _channel.close()
            except Exception:
                pass
            _channel = None

        if _connection is not None:
            try:
                if _connection.is_open:
                    _connection.close()
            except Exception:
                pass
            _connection = None


def publish_document_process(document_id: UUID, request_id: str | None = None) -> None:
    """
    Кладет задачу в очередь.
    Сообщение: {"document_id": "...", "request_id": "..."}
    """
    rid = request_id or get_request_id()
    body = json.dumps(
        {
            "document_id": str(document_id),
            "request_id": rid,
        }
    )
    logger.info(
        "publishing to rabbit doc_id=%s request_id=%s queue=%s",
        document_id,
        rid,
        settings.rabbitmq_queue,
    )

    def _publish() -> None:
        _get_channel().basic_publish(
            exchange="",
            routing_key=settings.rabbitmq_queue,
            body=body,
            properties=pika.BasicProperties(
                delivery_mode=2,
                content_type="application/json",
            ),
        )

    with _lock:
        try:
            _publish()
        except (AMQPConnectionError, AMQPChannelError, OSError):
            # один retry после сброса соединения
            logger.warning("RabbitMQ publish failed, reconnecting once")
            close_publisher()
            _publish()
    logger.info("published to rabbit doc_id=%s", document_id)
