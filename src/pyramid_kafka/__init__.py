"""pyramid-kafka — A Pyramid plugin for Apache Kafka integration."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pyramid_kafka.core import (
    COMMIT_STRATEGY_AUTO,
    COMMIT_STRATEGY_TRANSACTION,
    KafkaManager,
)
from pyramid_kafka.producer import KafkaEvent, register_kafka_event
from pyramid_kafka.transaction import KafkaDataManager

if TYPE_CHECKING:
    from pyramid.config import Configurator

__all__ = [
    "COMMIT_STRATEGY_AUTO",
    "COMMIT_STRATEGY_TRANSACTION",
    "KafkaDataManager",
    "KafkaEvent",
    "KafkaManager",
    "includeme",
]


def includeme(config: Configurator) -> None:
    """Pyramid entry point that wires up Kafka producer/consumer support.

    Reads ``kafka.*`` settings from the Pyramid registry, initialises a
    ``KafkaManager`` on ``config.registry.kafka``, registers the
    ``KafkaEvent`` subscriber, and exposes the
    ``config.register_kafka_event()`` directive.

    Args:
        config: The Pyramid Configurator instance.
    """
    settings = config.get_settings()
    config.registry.kafka = KafkaManager(settings)
    config.add_directive("register_kafka_event", register_kafka_event)
    config.scan("pyramid_kafka.producer")
