"""KafkaManager — lazy wrapper around confluent-kafka Producer and Consumer."""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any

from confluent_kafka import Consumer, Producer

if TYPE_CHECKING:
    from collections.abc import Callable

logger = logging.getLogger(__name__)

_KNOWN_SETTINGS = {
    "kafka.bootstrap_servers": "bootstrap.servers",
    "kafka.group_id": "group.id",
    "kafka.auto_offset_reset": "auto.offset.reset",
    "kafka.client_id": "client.id",
}

_EXTRA_PREFIX = "kafka.extra."


def _build_confluent_config(settings: dict[str, Any]) -> dict[str, str]:
    """Build a confluent-kafka config dict from Pyramid settings.

    Args:
        settings: Pyramid registry settings dict.

    Returns:
        A dict suitable for ``confluent_kafka.Producer`` or ``Consumer``.
    """
    config: dict[str, str] = {}

    for pyramid_key, confluent_key in _KNOWN_SETTINGS.items():
        value = settings.get(pyramid_key)
        if value is not None:
            config[confluent_key] = value

    for key, value in settings.items():
        if key.startswith(_EXTRA_PREFIX):
            confluent_key = key[len(_EXTRA_PREFIX) :]
            config[confluent_key] = value

    return config


class KafkaManager:
    """Lazy wrapper around confluent-kafka Producer and Consumer.

    Attached to the Pyramid registry as ``config.registry.kafka``.
    Producer and Consumer are created on first access to avoid connecting
    at import/config time.
    """

    def __init__(self, settings: dict[str, Any]) -> None:
        """Initialize KafkaManager from Pyramid settings.

        Args:
            settings: The Pyramid registry settings dict.

        Raises:
            KeyError: If ``kafka.bootstrap_servers`` is missing.
        """
        if "kafka.bootstrap_servers" not in settings:
            raise KeyError(
                "pyramid_kafka requires 'kafka.bootstrap_servers' in settings"
            )

        self._settings = settings
        self._config = _build_confluent_config(settings)
        self._producer: Producer | None = None
        self._consumer: Consumer | None = None

    @property
    def producer(self) -> Producer:
        """Return a lazily-initialized confluent-kafka Producer."""
        if self._producer is None:
            producer_config = {
                k: v
                for k, v in self._config.items()
                if k != "group.id" and k != "auto.offset.reset"
            }
            self._producer = Producer(producer_config)
            logger.info("Kafka producer initialized")
        return self._producer

    @property
    def consumer(self) -> Consumer:
        """Return a lazily-initialized confluent-kafka Consumer.

        Raises:
            KeyError: If ``kafka.group_id`` is not set in settings.
        """
        if self._consumer is None:
            if "group.id" not in self._config:
                raise KeyError(
                    "pyramid_kafka consumer requires 'kafka.group_id' in settings"
                )
            consumer_config = dict(self._config)
            consumer_config.setdefault("auto.offset.reset", "earliest")
            self._consumer = Consumer(consumer_config)
            logger.info("Kafka consumer initialized")
        return self._consumer

    def produce(
        self,
        topic: str,
        value: dict[str, Any],
        key: str | None = None,
        on_delivery: Callable | None = None,
    ) -> None:
        """Serialize *value* as JSON and produce to *topic*.

        Args:
            topic: The Kafka topic to produce to.
            value: Dict payload, serialized as JSON.
            key: Optional message key.
            on_delivery: Optional delivery callback.
        """
        encoded_value = json.dumps(value).encode("utf-8")
        encoded_key = key.encode("utf-8") if key is not None else None
        self.producer.produce(
            topic,
            value=encoded_value,
            key=encoded_key,
            on_delivery=on_delivery,
        )
        self.producer.poll(0)

    def close(self) -> None:
        """Flush the producer and close the consumer."""
        if self._producer is not None:
            self._producer.flush()
            logger.info("Kafka producer flushed")
        if self._consumer is not None:
            self._consumer.close()
            logger.info("Kafka consumer closed")
