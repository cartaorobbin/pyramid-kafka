"""Tests for consumer message processing commit strategies."""

from __future__ import annotations

import logging
from unittest.mock import MagicMock

import pytest

import pyramid_kafka.consumer as consumer_mod
from pyramid_kafka.consumer import (
    _process_message,
    _process_message_auto,
    _process_message_transaction,
)


@pytest.fixture()
def kafka_message() -> MagicMock:
    """Return a Kafka message double with topic, partition, and offset."""
    msg = MagicMock()
    msg.topic.return_value = "t1"
    msg.partition.return_value = 0
    msg.offset.return_value = 42
    return msg


@pytest.fixture()
def kafka_consumer() -> MagicMock:
    """Return a confluent-kafka Consumer double."""
    return MagicMock()


def test_process_message_auto_commits_after_handler(kafka_message, kafka_consumer):
    """Auto strategy commits the offset after the handler returns."""
    order: list[str] = []
    handler = MagicMock(side_effect=lambda *_args: order.append("handler"))
    kafka_consumer.commit.side_effect = lambda **_kwargs: order.append("commit")
    request = MagicMock()

    _process_message_auto(handler, request, kafka_message, kafka_consumer)

    assert order == ["handler", "commit"]
    kafka_consumer.commit.assert_called_once_with(
        message=kafka_message, asynchronous=False
    )


def test_process_message_auto_handler_receives_request_and_message(
    kafka_message, kafka_consumer
):
    """Auto strategy calls the handler with request and message only."""
    handler = MagicMock()
    request = MagicMock()

    _process_message_auto(handler, request, kafka_message, kafka_consumer)

    handler.assert_called_once_with(request, kafka_message)


def test_process_message_auto_does_not_commit_when_handler_raises(
    kafka_message, kafka_consumer
):
    """Auto strategy skips offset commit when the handler raises."""
    handler = MagicMock(side_effect=RuntimeError("boom"))
    request = MagicMock()

    _process_message_auto(handler, request, kafka_message, kafka_consumer)

    handler.assert_called_once()
    kafka_consumer.commit.assert_not_called()


def test_process_message_auto_does_not_raise_when_handler_raises(
    kafka_message, kafka_consumer, caplog
):
    """Auto strategy logs handler errors and does not propagate them."""
    handler = MagicMock(side_effect=RuntimeError("boom"))
    request = MagicMock()

    with caplog.at_level(logging.ERROR):
        _process_message_auto(handler, request, kafka_message, kafka_consumer)

    handler.assert_called_once()
    kafka_consumer.commit.assert_not_called()
    assert "Error processing message" in caplog.text
    assert "boom" in caplog.text


def test_process_message_auto_logs_when_commit_raises(
    kafka_message, kafka_consumer, caplog
):
    """Auto strategy logs a failed offset commit and does not raise."""
    handler = MagicMock()
    kafka_consumer.commit.side_effect = RuntimeError("commit failed")
    request = MagicMock()

    with caplog.at_level(logging.ERROR):
        _process_message_auto(handler, request, kafka_message, kafka_consumer)

    handler.assert_called_once()
    assert "Failed to commit offset" in caplog.text
    assert "Error processing message" not in caplog.text
    assert "t1" in caplog.text


def test_process_message_transaction_commits_offset_after_txn_success(
    kafka_message, kafka_consumer, monkeypatch
):
    """Transaction strategy commits the offset after the txn and handler succeed."""
    order: list[str] = []

    class TrackingTM(consumer_mod.txn_mod.TransactionManager):
        def commit(self) -> None:
            order.append("txn")
            super().commit()

    monkeypatch.setattr(consumer_mod.txn_mod, "TransactionManager", TrackingTM)

    handler = MagicMock(side_effect=lambda *_args: order.append("handler"))
    kafka_consumer.commit.side_effect = lambda **_kwargs: order.append("commit")
    request = MagicMock()

    _process_message_transaction(handler, request, kafka_message, kafka_consumer)

    assert order == ["handler", "txn", "commit"]
    kafka_consumer.commit.assert_called_once_with(
        message=kafka_message, asynchronous=False
    )


def test_process_message_transaction_does_not_commit_offset_on_handler_failure(
    kafka_message, kafka_consumer
):
    """Transaction strategy does not commit the offset when the handler raises."""
    handler = MagicMock(side_effect=RuntimeError("db error"))
    request = MagicMock()

    _process_message_transaction(handler, request, kafka_message, kafka_consumer)

    handler.assert_called_once()
    kafka_consumer.commit.assert_not_called()


def test_process_message_transaction_aborts_on_handler_failure(
    kafka_message, kafka_consumer, monkeypatch
):
    """Transaction strategy aborts the transaction when the handler raises."""
    order: list[str] = []

    class TrackingTM(consumer_mod.txn_mod.TransactionManager):
        def abort(self) -> None:
            order.append("abort")
            super().abort()

    monkeypatch.setattr(consumer_mod.txn_mod, "TransactionManager", TrackingTM)

    handler = MagicMock(side_effect=RuntimeError("db error"))
    request = MagicMock()

    _process_message_transaction(handler, request, kafka_message, kafka_consumer)

    assert order == ["abort"]
    kafka_consumer.commit.assert_not_called()


def test_process_message_transaction_handler_receives_request_and_message(
    kafka_message, kafka_consumer
):
    """Transaction strategy calls the handler with request and message only."""
    handler = MagicMock()
    request = MagicMock()

    _process_message_transaction(handler, request, kafka_message, kafka_consumer)

    handler.assert_called_once_with(request, kafka_message)


def test_process_message_transaction_does_not_abort_when_offset_commit_raises(
    kafka_message, kafka_consumer, monkeypatch
):
    """Offset commit failure after txn success must not call abort()."""
    order: list[str] = []

    class TrackingTM(consumer_mod.txn_mod.TransactionManager):
        def abort(self) -> None:
            order.append("abort")
            super().abort()

    monkeypatch.setattr(consumer_mod.txn_mod, "TransactionManager", TrackingTM)

    handler = MagicMock()
    kafka_consumer.commit.side_effect = RuntimeError("commit failed")
    request = MagicMock()

    _process_message_transaction(handler, request, kafka_message, kafka_consumer)

    handler.assert_called_once()
    assert order == []


def test_process_message_transaction_does_not_raise_when_offset_commit_raises(
    kafka_message, kafka_consumer, caplog
):
    """Offset commit failure after txn success is logged and does not propagate."""
    handler = MagicMock()
    kafka_consumer.commit.side_effect = RuntimeError("commit failed")
    request = MagicMock()

    with caplog.at_level(logging.ERROR):
        _process_message_transaction(handler, request, kafka_message, kafka_consumer)

    handler.assert_called_once()
    assert "Failed to commit offset" in caplog.text
    assert "Transaction aborted" not in caplog.text


def test_process_message_dispatches_auto(kafka_message, kafka_consumer):
    """_process_message with auto runs the handler then commits."""
    order: list[str] = []
    handler = MagicMock(side_effect=lambda *_args: order.append("handler"))
    kafka_consumer.commit.side_effect = lambda **_kwargs: order.append("commit")
    request = MagicMock()

    _process_message("auto", handler, request, kafka_message, kafka_consumer)

    assert order == ["handler", "commit"]
    handler.assert_called_once_with(request, kafka_message)


def test_process_message_dispatches_transaction(kafka_message, kafka_consumer):
    """_process_message with transaction runs the handler then commits."""
    order: list[str] = []
    handler = MagicMock(side_effect=lambda *_args: order.append("handler"))
    kafka_consumer.commit.side_effect = lambda **_kwargs: order.append("commit")
    request = MagicMock()

    _process_message("transaction", handler, request, kafka_message, kafka_consumer)

    assert order == ["handler", "commit"]
    handler.assert_called_once_with(request, kafka_message)
    kafka_consumer.commit.assert_called_once_with(
        message=kafka_message, asynchronous=False
    )
