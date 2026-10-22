"""Unit-тесты worker: обработка сообщений, backoff, graceful shutdown."""

import json
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pika
import pytest

DOC_ID = uuid4()
VALID_BODY = json.dumps({"document_id": str(DOC_ID)}).encode()
VALID_BODY_WITH_RID = json.dumps({"document_id": str(DOC_ID), "request_id": "req-abc"}).encode()


# ── handle_message ───────────────────────────────────────────────────────────


def _make_channel():
    ch = MagicMock()
    ch.basic_ack = MagicMock()
    ch.basic_nack = MagicMock()
    return ch


def _make_method(tag=1):
    method = MagicMock()
    method.delivery_tag = tag
    return method


@patch("app.worker.process_document")
@patch("app.worker.SessionLocal")
def test_handle_message_success(mock_session, mock_process):
    """Валидное сообщение → process_document вызван → ack."""
    from app.worker import handle_message

    ch = _make_channel()
    handle_message(ch, _make_method(), MagicMock(), VALID_BODY)

    mock_process.assert_called_once()
    ch.basic_ack.assert_called_once_with(delivery_tag=1)
    ch.basic_nack.assert_not_called()


@patch("app.worker.process_document")
@patch("app.worker.SessionLocal")
def test_handle_message_with_request_id(mock_session, mock_process):
    """request_id из тела устанавливается в контекст (не бросает исключений)."""
    from app.worker import handle_message

    ch = _make_channel()
    handle_message(ch, _make_method(), MagicMock(), VALID_BODY_WITH_RID)

    ch.basic_ack.assert_called_once()


@patch("app.worker.SessionLocal")
def test_handle_message_malformed_json(mock_session):
    """Сломанный JSON → nack без requeue (уйдёт в DLQ)."""
    from app.worker import handle_message

    ch = _make_channel()
    handle_message(ch, _make_method(), MagicMock(), b"not-json")

    ch.basic_nack.assert_called_once_with(delivery_tag=1, requeue=False)
    ch.basic_ack.assert_not_called()


@patch("app.worker.process_document", side_effect=RuntimeError("db error"))
@patch("app.worker.SessionLocal")
def test_handle_message_process_exception_sends_to_dlq(mock_session, mock_process):
    """Исключение в process_document → nack без requeue."""
    from app.worker import handle_message

    ch = _make_channel()
    handle_message(ch, _make_method(), MagicMock(), VALID_BODY)

    ch.basic_nack.assert_called_once_with(delivery_tag=1, requeue=False)
    ch.basic_ack.assert_not_called()


@patch("app.worker.SessionLocal")
def test_handle_message_missing_document_id_key(mock_session):
    """JSON без поля document_id → KeyError → nack."""
    from app.worker import handle_message

    body = json.dumps({"foo": "bar"}).encode()
    ch = _make_channel()
    handle_message(ch, _make_method(), MagicMock(), body)

    ch.basic_nack.assert_called_once_with(delivery_tag=1, requeue=False)


@patch("app.worker.SessionLocal")
def test_handle_message_invalid_uuid(mock_session):
    """document_id не UUID-формата → ValueError → nack."""
    from app.worker import handle_message

    body = json.dumps({"document_id": "not-a-uuid"}).encode()
    ch = _make_channel()
    handle_message(ch, _make_method(), MagicMock(), body)

    ch.basic_nack.assert_called_once_with(delivery_tag=1, requeue=False)


@patch("app.worker.process_document")
@patch("app.worker.SessionLocal")
def test_handle_message_always_closes_db(mock_session_cls, mock_process):
    """db.close() вызывается даже при исключении."""
    from app.worker import handle_message

    mock_db = MagicMock()
    mock_session_cls.return_value = mock_db
    mock_process.side_effect = RuntimeError("boom")

    ch = _make_channel()
    handle_message(ch, _make_method(), MagicMock(), VALID_BODY)

    mock_db.close.assert_called_once()


# ── _connect_with_backoff ────────────────────────────────────────────────────


@patch("app.worker.time.sleep")
@patch("app.worker.pika.BlockingConnection")
def test_connect_with_backoff_success_first_try(mock_conn_cls, mock_sleep):
    """Если RabbitMQ доступен сразу — возвращает соединение без sleep."""
    from app.worker import _connect_with_backoff

    mock_conn = MagicMock()
    mock_conn_cls.return_value = mock_conn
    params = MagicMock()

    conn = _connect_with_backoff(params, max_attempts=3)

    assert conn is mock_conn
    mock_sleep.assert_not_called()


@patch("app.worker.time.sleep")
@patch("app.worker.pika.BlockingConnection")
def test_connect_with_backoff_retries_then_connects(mock_conn_cls, mock_sleep):
    """Первые 2 попытки — AMQPConnectionError, третья — успех."""
    from app.worker import _connect_with_backoff

    mock_conn = MagicMock()
    mock_conn_cls.side_effect = [
        pika.exceptions.AMQPConnectionError,
        pika.exceptions.AMQPConnectionError,
        mock_conn,
    ]

    conn = _connect_with_backoff(MagicMock(), max_attempts=5)

    assert conn is mock_conn
    assert mock_sleep.call_count == 2


@patch("app.worker.time.sleep")
@patch("app.worker.pika.BlockingConnection", side_effect=pika.exceptions.AMQPConnectionError)
def test_connect_with_backoff_raises_after_max_attempts(mock_conn_cls, mock_sleep):
    """Все попытки исчерпаны → AMQPConnectionError пробрасывается."""
    from app.worker import _connect_with_backoff

    with pytest.raises(pika.exceptions.AMQPConnectionError):
        _connect_with_backoff(MagicMock(), max_attempts=3)

    assert mock_sleep.call_count == 2  # sleep между попытками, не после последней


# ── SIGTERM/SIGINT handler ───────────────────────────────────────────────────


def test_handle_signal_sets_shutdown_flag():
    """_handle_signal устанавливает _shutdown_requested = True."""
    import app.worker as worker_module

    original = worker_module._shutdown_requested
    try:
        worker_module._shutdown_requested = False
        worker_module._handle_signal(15, None)  # SIGTERM
        assert worker_module._shutdown_requested is True
    finally:
        worker_module._shutdown_requested = original
