"""Объявление основной очереди и DLQ."""

import pika

from app.core.config import settings

def declare_process_queues(channel: pika.channel.Channel) -> None:
    # 1) очередь для "ядовитых" сообщений
    channel.queue_declare(queue=settings.rabbitmq_dlq, durable=True)

    # 2) основная очередь: при nack/reject без requeue -> в DLQ
    channel.queue_declare(
        queue=settings.rabbitmq_queue,
        durable=True,
        arguments={
            "x-dead-letter-exchange": "",
            "x-dead-letter-routing-key": settings.rabbitmq_dlq,
        }
    )