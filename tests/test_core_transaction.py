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


@pytest.mark.parametrize("strategy", ["manual", "bogus", "auto_early"])
def test_kafka_manager_commit_strategy_rejects_unknown(minimal_settings, strategy):
    """KafkaManager raises ValueError for unknown commit strategy."""
    minimal_settings["kafka.commit_strategy"] = strategy

    with pytest.raises(ValueError, match=strategy):
        KafkaManager(minimal_settings)


def test_kafka_manager_commit_strategy_error_lists_valid_values(minimal_settings):
    """ValueError for an unknown strategy names the valid options."""
    minimal_settings["kafka.commit_strategy"] = "bogus"

    with pytest.raises(ValueError, match="must be 'auto' or 'transaction'"):
        KafkaManager(minimal_settings)


@pytest.mark.parametrize("settings_update", [{}, {"kafka.commit_strategy": "auto"}])
@patch("pyramid_kafka.core.Producer")
def test_produce_auto_sends_immediately(
    mock_producer_cls, minimal_settings, settings_update
):
    """With auto strategy, produce() sends to Kafka immediately."""
    minimal_settings.update(settings_update)
    mock_prod = MagicMock()
    mock_producer_cls.return_value = mock_prod

    manager = KafkaManager(minimal_settings)
    manager.produce(topic="t1", value={"a": 1})

    mock_prod.produce.assert_called_once()
    mock_prod.poll.assert_called_once_with(0)


@pytest.mark.parametrize("settings_update", [{}, {"kafka.commit_strategy": "auto"}])
@patch("pyramid_kafka.core.Producer")
def test_produce_auto_with_request_still_sends_immediately(
    mock_producer_cls, minimal_settings, settings_update
):
    """With auto strategy, produce() ignores request and sends immediately."""
    minimal_settings.update(settings_update)
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


@pytest.mark.parametrize(
    "settings_update",
    [{}, {"kafka.commit_strategy": "auto"}, {"kafka.commit_strategy": "transaction"}],
)
@patch("pyramid_kafka.core.Consumer")
def test_consumer_disables_librdkafka_auto_commit_for_strategy(
    mock_consumer_cls, settings_update
):
    """Consumer always sets enable.auto.commit to false."""
    settings = {
        "kafka.bootstrap_servers": "broker:9092",
        "kafka.group_id": "grp",
        **settings_update,
    }
    manager = KafkaManager(settings)
    _ = manager.consumer

    call_config = mock_consumer_cls.call_args[0][0]
    assert call_config["enable.auto.commit"] == "false"


@patch("pyramid_kafka.core.Consumer")
def test_consumer_overwrites_extra_enable_auto_commit(mock_consumer_cls):
    """commit_strategy owns enable.auto.commit even if set via kafka.extra."""
    settings = {
        "kafka.bootstrap_servers": "broker:9092",
        "kafka.group_id": "grp",
        "kafka.extra.enable.auto.commit": "true",
    }
    manager = KafkaManager(settings)
    _ = manager.consumer

    call_config = mock_consumer_cls.call_args[0][0]
    assert call_config["enable.auto.commit"] == "false"
