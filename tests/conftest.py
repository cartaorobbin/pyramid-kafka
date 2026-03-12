"""Shared fixtures for pyramid-kafka tests."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from pyramid import testing


@pytest.fixture()
def minimal_settings() -> dict[str, str]:
    """Return the minimal settings dict for KafkaManager."""
    return {
        "kafka.bootstrap_servers": "localhost:9092",
    }


@pytest.fixture()
def full_settings() -> dict[str, str]:
    """Return a complete settings dict including consumer config."""
    return {
        "kafka.bootstrap_servers": "localhost:9092",
        "kafka.group_id": "test-group",
        "kafka.auto_offset_reset": "latest",
        "kafka.client_id": "test-client",
        "kafka.extra.security.protocol": "PLAINTEXT",
        "kafka.topics": "topic-a topic-b",
        "kafka.handler": "tests.conftest:_dummy_handler",
    }


@pytest.fixture()
def pyramid_config(full_settings):
    """Return a Pyramid Configurator wired with pyramid_kafka."""
    config = testing.setUp(settings=full_settings)
    config.include("pyramid_kafka")
    config.commit()
    yield config
    testing.tearDown()


@pytest.fixture()
def mock_producer() -> MagicMock:
    """Return a MagicMock standing in for confluent_kafka.Producer."""
    producer = MagicMock()
    producer.produce = MagicMock()
    producer.poll = MagicMock()
    producer.flush = MagicMock()
    return producer


def _dummy_handler(request, message) -> None:
    """No-op handler used in tests."""
