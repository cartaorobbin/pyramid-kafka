"""Tests for pyramid_kafka includeme() — Pyramid integration."""

from __future__ import annotations

from unittest.mock import patch

from pyramid import testing

from pyramid_kafka.core import KafkaManager


@patch("pyramid_kafka.core.Producer")
def test_includeme_attaches_kafka_manager(mock_producer_cls):
    """includeme() attaches a KafkaManager to config.registry.kafka."""
    config = testing.setUp(settings={"kafka.bootstrap_servers": "broker:9092"})
    config.include("pyramid_kafka")
    config.commit()

    assert hasattr(config.registry, "kafka")
    assert isinstance(config.registry.kafka, KafkaManager)

    testing.tearDown()


@patch("pyramid_kafka.core.Producer")
def test_includeme_registers_directive(mock_producer_cls):
    """includeme() makes register_kafka_event available as a config directive."""
    config = testing.setUp(settings={"kafka.bootstrap_servers": "broker:9092"})
    config.include("pyramid_kafka")
    config.commit()

    assert hasattr(config, "register_kafka_event")

    testing.tearDown()


def test_includeme_raises_without_bootstrap_servers():
    """includeme() raises KeyError when kafka.bootstrap_servers is missing."""
    config = testing.setUp(settings={})

    try:
        config.include("pyramid_kafka")
        raised = False
    except KeyError:
        raised = True

    assert raised

    testing.tearDown()
