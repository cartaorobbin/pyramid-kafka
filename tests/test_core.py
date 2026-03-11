"""Tests for pyramid_kafka.core — KafkaManager."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from pyramid_kafka.core import KafkaManager, _build_confluent_config


def test_build_confluent_config_maps_known_settings(full_settings):
    """Known kafka.* settings are mapped to confluent-kafka dot-notation."""
    config = _build_confluent_config(full_settings)

    assert config["bootstrap.servers"] == "localhost:9092"
    assert config["group.id"] == "test-group"
    assert config["auto.offset.reset"] == "latest"
    assert config["client.id"] == "test-client"


def test_build_confluent_config_includes_extra_settings(full_settings):
    """Settings with kafka.extra.* prefix pass through to confluent config."""
    config = _build_confluent_config(full_settings)

    assert config["security.protocol"] == "PLAINTEXT"


def test_build_confluent_config_ignores_non_kafka_settings():
    """Non-kafka.* settings are not included in the config."""
    settings = {
        "kafka.bootstrap_servers": "broker:9092",
        "sqlalchemy.url": "sqlite://",
    }
    config = _build_confluent_config(settings)

    assert "sqlalchemy.url" not in config
    assert len(config) == 1


def test_kafka_manager_requires_bootstrap_servers():
    """KafkaManager raises KeyError when bootstrap_servers is missing."""
    with pytest.raises(KeyError, match="kafka.bootstrap_servers"):
        KafkaManager({})


@patch("pyramid_kafka.core.Producer")
def test_kafka_manager_producer_lazy_init(mock_producer_cls, minimal_settings):
    """Producer is only created on first access, not at init time."""
    manager = KafkaManager(minimal_settings)
    mock_producer_cls.assert_not_called()

    _ = manager.producer
    mock_producer_cls.assert_called_once()


@patch("pyramid_kafka.core.Producer")
def test_kafka_manager_producer_reuses_instance(mock_producer_cls, minimal_settings):
    """Subsequent access to .producer returns the same instance."""
    manager = KafkaManager(minimal_settings)

    p1 = manager.producer
    p2 = manager.producer

    assert p1 is p2
    assert mock_producer_cls.call_count == 1


@patch("pyramid_kafka.core.Consumer")
def test_kafka_manager_consumer_requires_group_id(mock_consumer_cls, minimal_settings):
    """Consumer raises KeyError when group_id is not configured."""
    manager = KafkaManager(minimal_settings)

    with pytest.raises(KeyError, match="kafka.group_id"):
        _ = manager.consumer


@patch("pyramid_kafka.core.Consumer")
def test_kafka_manager_consumer_lazy_init(mock_consumer_cls, full_settings):
    """Consumer is only created on first access."""
    manager = KafkaManager(full_settings)
    mock_consumer_cls.assert_not_called()

    _ = manager.consumer
    mock_consumer_cls.assert_called_once()


@patch("pyramid_kafka.core.Consumer")
def test_kafka_manager_consumer_defaults_auto_offset_reset(mock_consumer_cls):
    """Consumer defaults auto.offset.reset to 'earliest' when not set."""
    settings = {
        "kafka.bootstrap_servers": "broker:9092",
        "kafka.group_id": "my-group",
    }
    manager = KafkaManager(settings)
    _ = manager.consumer

    call_config = mock_consumer_cls.call_args[0][0]
    assert call_config["auto.offset.reset"] == "earliest"


@patch("pyramid_kafka.core.Producer")
def test_kafka_manager_produce_serializes_json(mock_producer_cls, minimal_settings):
    """produce() JSON-encodes the value and calls producer.produce."""
    mock_instance = MagicMock()
    mock_producer_cls.return_value = mock_instance

    manager = KafkaManager(minimal_settings)
    manager.produce(topic="my-topic", value={"foo": "bar"}, key="k1")

    mock_instance.produce.assert_called_once()
    call_args = mock_instance.produce.call_args
    assert call_args[0][0] == "my-topic"
    assert call_args[1]["value"] == b'{"foo": "bar"}'
    assert call_args[1]["key"] == b"k1"
    mock_instance.poll.assert_called_once_with(0)


@patch("pyramid_kafka.core.Producer")
def test_kafka_manager_produce_with_none_key(mock_producer_cls, minimal_settings):
    """produce() passes None key when no key is provided."""
    mock_instance = MagicMock()
    mock_producer_cls.return_value = mock_instance

    manager = KafkaManager(minimal_settings)
    manager.produce(topic="my-topic", value={"a": 1})

    call_kwargs = mock_instance.produce.call_args[1]
    assert call_kwargs["key"] is None


@patch("pyramid_kafka.core.Consumer")
@patch("pyramid_kafka.core.Producer")
def test_kafka_manager_close(mock_producer_cls, mock_consumer_cls, full_settings):
    """close() flushes the producer and closes the consumer."""
    mock_prod = MagicMock()
    mock_cons = MagicMock()
    mock_producer_cls.return_value = mock_prod
    mock_consumer_cls.return_value = mock_cons

    manager = KafkaManager(full_settings)
    _ = manager.producer
    _ = manager.consumer
    manager.close()

    mock_prod.flush.assert_called_once()
    mock_cons.close.assert_called_once()


def test_kafka_manager_close_without_init(minimal_settings):
    """close() does nothing when producer/consumer were never accessed."""
    manager = KafkaManager(minimal_settings)
    manager.close()
