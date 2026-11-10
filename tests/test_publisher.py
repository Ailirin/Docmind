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


def test_publish_is_serialized_by_lock(monkeypatch):
    """Параллельные publish не должны одновременно работать с общим каналом (pika не thread-safe)."""
    import threading
    import time

    publisher.close_publisher()

    active = 0
    max_active = 0
    guard = threading.Lock()

    def slow_publish(**kwargs):
        nonlocal active, max_active
        with guard:
            active += 1
            max_active = max(max_active, active)
        time.sleep(0.02)
        with guard:
            active -= 1

    fake_channel = MagicMock()
    fake_channel.is_open = True
    fake_channel.basic_publish.side_effect = slow_publish
    fake_connection = MagicMock()
    fake_connection.is_open = True
    fake_connection.channel.return_value = fake_channel

    monkeypatch.setattr(publisher.pika, "BlockingConnection", lambda params: fake_connection)
    monkeypatch.setattr(publisher, "declare_process_queues", lambda ch: None)

    threads = [
        threading.Thread(target=publisher.publish_document_process, args=(uuid4(), f"r{i}"))
        for i in range(8)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert fake_channel.basic_publish.call_count == 8
    assert max_active == 1

    publisher.close_publisher()
