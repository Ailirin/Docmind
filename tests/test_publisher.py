from unittest.mock import MagicMock
from uuid import uuid4

from app.queue import publisher


def test_publish_reuses_channel(monkeypatch):
    publisher.close_publisher()

    fake_channel = MagicMock()
    fake_channel.is_open = True
    fake_connection = MagicMock()
    fake_connection.is_open = True
    fake_connection.channel.return_value = fake_channel

    monkeypatch.setattr(
        publisher.pika,
        "BlockingConnection",
        lambda params: fake_connection,
    )
    monkeypatch.setattr(publisher, "declare_process_queues", lambda ch: None)

    doc_id = uuid4()
    publisher.publish_document_process(doc_id, request_id="t1")
    publisher.publish_document_process(doc_id, request_id="t2")

    # соединение создали один раз, publish — два раза
    assert fake_connection.channel.call_count == 1
    assert fake_channel.basic_publish.call_count == 2

    publisher.close_publisher()
