import json
import logging
from uuid import UUID

import pika

from app.core.config import settings
from app.db.session import SessionLocal
from app.services.processor import process_document


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("docmind.worker")

def handle_message(ch, method, propertis, body: bytes) -> None:
    db = SessionLocal()
    try:
        payload = json.loads(body.decode("utf-8"))
        document_id = UUID(payload["document_id"])
        logger.info("Processing document_id=%s", document_id)

        process_document(db, document_id)
        ch.basic_ack(delivery_tag=method.delivery_tag)
        logger.info("Done document_id=%s", document_id)
    except Exception:
        logger.exception("Failed to process message: %s", body)
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
    finally:
        db.close()

def main() -> None:
    params = pika.URLParameters(settings.rabbitmq_url)
    connection = pika.BlockingConnection(params)
    channel = connection.channel()
    channel.queue_declare(queue=settings.rabbitmq_queue, durable=True)

    #по одной задаче за раз - LLM тяжелый
    channel.basic_qos(prefetch_count=1)
    channel.basic_consume(
        queue=settings.rabbitmq_queue,
        on_message_callback=handle_message,
    )

    logger.info("Worker started. Queue=%s", settings.rabbitmq_queue)
    channel.start_consuming()

if __name__=="__main__":
    main()