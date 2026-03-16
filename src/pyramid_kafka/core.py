"""KafkaManager — lazy wrapper around confluent-kafka Producer and Consumer."""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any

from confluent_kafka import Consumer, Producer

if TYPE_CHECKING:
    from collections.abc import Callable

logger = logging.getLogger(__name__)

COMMIT_STRATEGY_AUTO = "auto"
COMMIT_STRATEGY_TRANSACTION = "transaction"

_KNOWN_SETTINGS = {
    "kafka.bootstrap_servers": "bootstrap.servers",
    "kafka.group_id": "group.id",
    "kafka.auto_offset_reset": "auto.offset.reset",
    "kafka.client_id": "client.id",
}

_PYRAMID_KAFKA_SETTINGS = frozenset(
    {
        "kafka.commit_strategy",
        "kafka.handler",
        "kafka.topics",
    }
)

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

    When ``kafka.commit_strategy`` is set to ``transaction``, produced
    messages are buffered and only sent when the Pyramid transaction
    commits (via ``pyramid_tm``).  Consumer auto-offset-commit is
    disabled so offsets are committed manually after successful
    processing.
    """

    def __init__(self, settings: dict[str, Any]) -> None:
        """Initialize KafkaManager from Pyramid settings.

        Args:
            settings: The Pyramid registry settings dict.

        Raises:
            KeyError: If ``kafka.bootstrap_servers`` is missing.
            ValueError: If ``kafka.commit_strategy`` is not a valid value.
        """
        if "kafka.bootstrap_servers" not in settings:
            raise KeyError(
                "pyramid_kafka requires 'kafka.bootstrap_servers' in settings"
            )

        strategy = settings.get("kafka.commit_strategy", COMMIT_STRATEGY_AUTO)
        if strategy not in (COMMIT_STRATEGY_AUTO, COMMIT_STRATEGY_TRANSACTION):
            raise ValueError(
                f"kafka.commit_strategy must be '{COMMIT_STRATEGY_AUTO}' or "
                f"'{COMMIT_STRATEGY_TRANSACTION}', got '{strategy}'"
            )

        self._settings = settings
        self._config = _build_confluent_config(settings)
        self._commit_strategy = strategy
        self._producer: Producer | None = None
        self._consumer: Consumer | None = None

    @property
    def commit_strategy(self) -> str:
        """Return the configured commit strategy."""
        return self._commit_strategy

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

        When ``commit_strategy`` is ``transaction``, the consumer is
        created with ``enable.auto.commit = false`` so offsets must be
        committed explicitly.

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
            if self._commit_strategy == COMMIT_STRATEGY_TRANSACTION:
                consumer_config["enable.auto.commit"] = "false"
            self._consumer = Consumer(consumer_config)
            logger.info(
                "Kafka consumer initialized (commit_strategy=%s)",
                self._commit_strategy,
            )
        return self._consumer

    def produce(
        self,
        topic: str,
        value: dict[str, Any],
        key: str | None = None,
        on_delivery: Callable | None = None,
        request: Any | None = None,
    ) -> None:
        """Serialize *value* as JSON and produce to *topic*.

        When ``commit_strategy`` is ``transaction`` and a *request* with
        an active transaction manager is provided, the message is
        buffered in a ``KafkaDataManager`` and only delivered when the
        transaction commits.  Otherwise the message is sent immediately.

        Args:
            topic: The Kafka topic to produce to.
            value: Dict payload, serialized as JSON.
            key: Optional message key.
            on_delivery: Optional delivery callback.
            request: Optional Pyramid request.  Required for
                transactional producing.
        """
        encoded_value = json.dumps(value).encode("utf-8")
        encoded_key = key.encode("utf-8") if key is not None else None

        if self._should_buffer(request):
            dm = self._join_transaction(request)
            dm.append(topic, encoded_value, encoded_key, on_delivery)
            logger.debug("Buffered message for topic=%s (transactional)", topic)
            return

        self.producer.produce(
            topic,
            value=encoded_value,
            key=encoded_key,
            on_delivery=on_delivery,
        )
        self.producer.poll(0)

    def _should_buffer(self, request: Any | None) -> bool:
        """Return True if produce should buffer for transactional commit.

        Args:
            request: The Pyramid request, or None.

        Returns:
            True when strategy is ``transaction`` and request has a
            transaction manager.
        """
        if self._commit_strategy != COMMIT_STRATEGY_TRANSACTION:
            return False
        if request is None:
            return False
        return hasattr(request, "tm")

    def _join_transaction(self, request: Any) -> Any:
        """Get or create a KafkaDataManager joined to the active transaction.

        The data manager is cached on the request so that multiple
        ``produce()`` calls within the same request share a single
        buffer and a single join.

        Args:
            request: The Pyramid request with an active ``tm``.

        Returns:
            The ``KafkaDataManager`` for this request's transaction.
        """
        from pyramid_kafka.transaction import KafkaDataManager

        existing = getattr(request, "_kafka_data_manager", None)
        if isinstance(existing, KafkaDataManager):
            return existing

        dm = KafkaDataManager(self.producer)
        txn = request.tm.get()
        txn.join(dm)
        request._kafka_data_manager = dm
        return dm

    def close(self) -> None:
        """Flush the producer and close the consumer."""
        if self._producer is not None:
            self._producer.flush()
            logger.info("Kafka producer flushed")
        if self._consumer is not None:
            self._consumer.close()
            logger.info("Kafka consumer closed")
