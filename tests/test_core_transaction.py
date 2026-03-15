"""Tests for transactional produce flow in KafkaManager."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from pyramid_kafka.core import KafkaManager


def test_kafka_manager_commit_strategy_defaults_to_auto(minimal_settings):
    """KafkaManager defaults to 'auto' commit strategy."""
    manager = KafkaManager(minimal_settings)

    assert manager.commit_strategy == "auto"


def test_kafka_manager_commit_strategy_accepts_auto(minimal_settings):
    """KafkaManager accepts 'auto' commit strategy explicitly."""
    minimal_settings["kafka.commit_strategy"] = "auto"
    manager = KafkaManager(minimal_settings)

    assert manager.commit_strategy == "auto"


def test_kafka_manager_commit_strategy_accepts_transaction(minimal_settings):
    """KafkaManager accepts 'transaction' commit strategy."""
    minimal_settings["kafka.commit_strategy"] = "transaction"
    manager = KafkaManager(minimal_settings)

    assert manager.commit_strategy == "transaction"


def test_kafka_manager_commit_strategy_rejects_invalid(minimal_settings):
    """KafkaManager raises ValueError for unknown commit strategy."""
    minimal_settings["kafka.commit_strategy"] = "manual"

    with pytest.raises(ValueError, match="manual"):
        KafkaManager(minimal_settings)


@patch("pyramid_kafka.core.Producer")
def test_produce_auto_sends_immediately(mock_producer_cls, minimal_settings):
    """With auto strategy, produce() sends to Kafka immediately."""
    mock_prod = MagicMock()
    mock_producer_cls.return_value = mock_prod

    manager = KafkaManager(minimal_settings)
    manager.produce(topic="t1", value={"a": 1})

    mock_prod.produce.assert_called_once()
    mock_prod.poll.assert_called_once_with(0)


@patch("pyramid_kafka.core.Producer")
def test_produce_auto_with_request_still_sends_immediately(
    mock_producer_cls, minimal_settings
):
    """With auto strategy, produce() ignores request and sends immediately."""
    mock_prod = MagicMock()
    mock_producer_cls.return_value = mock_prod
    request = MagicMock()
    request.tm = MagicMock()

    manager = KafkaManager(minimal_settings)
    manager.produce(topic="t1", value={"a": 1}, request=request)

    mock_prod.produce.assert_called_once()


@patch("pyramid_kafka.core.Producer")
def test_produce_transaction_buffers_when_request_has_tm(
    mock_producer_cls, transactional_settings
):
    """With transaction strategy, produce() buffers when request has tm."""
    mock_prod = MagicMock()
    mock_producer_cls.return_value = mock_prod
    mock_txn = MagicMock()
    mock_tm = MagicMock()
    mock_tm.get.return_value = mock_txn

    request = MagicMock()
    request.tm = mock_tm

    manager = KafkaManager(transactional_settings)
    manager.produce(topic="orders", value={"id": "o1"}, key="k1", request=request)

    mock_prod.produce.assert_not_called()
    mock_txn.join.assert_called_once()


@patch("pyramid_kafka.core.Producer")
def test_produce_transaction_falls_back_without_request(
    mock_producer_cls, transactional_settings
):
    """With transaction strategy, produce() sends immediately without request."""
    mock_prod = MagicMock()
    mock_producer_cls.return_value = mock_prod

    manager = KafkaManager(transactional_settings)
    manager.produce(topic="t1", value={"a": 1})

    mock_prod.produce.assert_called_once()
    mock_prod.poll.assert_called_once_with(0)


@patch("pyramid_kafka.core.Producer")
def test_produce_transaction_falls_back_without_tm(
    mock_producer_cls, transactional_settings
):
    """With transaction strategy, produce() sends immediately if request has no tm."""
    mock_prod = MagicMock()
    mock_producer_cls.return_value = mock_prod
    request = MagicMock(spec=[])

    manager = KafkaManager(transactional_settings)
    manager.produce(topic="t1", value={"a": 1}, request=request)

    mock_prod.produce.assert_called_once()


@patch("pyramid_kafka.core.Producer")
def test_produce_transaction_reuses_data_manager(
    mock_producer_cls, transactional_settings
):
    """Multiple produce() calls within one request share a KafkaDataManager."""
    mock_prod = MagicMock()
    mock_producer_cls.return_value = mock_prod
    mock_txn = MagicMock()
    mock_tm = MagicMock()
    mock_tm.get.return_value = mock_txn

    request = MagicMock(spec=["tm", "registry", "_kafka_data_manager"])
    request.tm = mock_tm
    request._kafka_data_manager = None
    del request._kafka_data_manager

    manager = KafkaManager(transactional_settings)
    manager.produce(topic="t1", value={"a": 1}, request=request)
    manager.produce(topic="t2", value={"b": 2}, request=request)

    mock_txn.join.assert_called_once()
    dm = request._kafka_data_manager
    assert len(dm._buffer) == 2


@patch("pyramid_kafka.core.Producer")
def test_produce_transaction_buffers_correct_data(
    mock_producer_cls, transactional_settings
):
    """Transactional produce buffers the correct serialized message."""
    mock_prod = MagicMock()
    mock_producer_cls.return_value = mock_prod
    mock_txn = MagicMock()
    mock_tm = MagicMock()
    mock_tm.get.return_value = mock_txn

    request = MagicMock()
    request.tm = mock_tm

    manager = KafkaManager(transactional_settings)
    manager.produce(
        topic="payments", value={"amount": 100}, key="pay-1", request=request
    )

    dm = request._kafka_data_manager
    assert len(dm._buffer) == 1
    topic, value, key, _ = dm._buffer[0]
    assert topic == "payments"
    assert json.loads(value) == {"amount": 100}
    assert key == b"pay-1"


@patch("pyramid_kafka.core.Consumer")
def test_consumer_transaction_disables_auto_commit(mock_consumer_cls):
    """Consumer disables auto-commit when commit_strategy is transaction."""
    settings = {
        "kafka.bootstrap_servers": "broker:9092",
        "kafka.group_id": "grp",
        "kafka.commit_strategy": "transaction",
    }
    manager = KafkaManager(settings)
    _ = manager.consumer

    call_config = mock_consumer_cls.call_args[0][0]
    assert call_config["enable.auto.commit"] == "false"


@patch("pyramid_kafka.core.Consumer")
def test_consumer_auto_does_not_set_auto_commit(mock_consumer_cls):
    """Consumer with auto strategy does not set enable.auto.commit."""
    settings = {
        "kafka.bootstrap_servers": "broker:9092",
        "kafka.group_id": "grp",
    }
    manager = KafkaManager(settings)
    _ = manager.consumer

    call_config = mock_consumer_cls.call_args[0][0]
    assert "enable.auto.commit" not in call_config
