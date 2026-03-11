"""KafkaEvent base class, Pyramid subscriber, and event registration directive."""

from __future__ import annotations

import dataclasses
import logging
from typing import TYPE_CHECKING, Any

from pyramid.events import subscriber

if TYPE_CHECKING:
    from collections.abc import Callable

    from pyramid.config import Configurator

logger = logging.getLogger(__name__)


class KafkaEvent:
    """Base event class for Kafka-bound messages.

    Subclass this and fire via ``request.registry.notify(MyEvent(request, ...))``
    to automatically produce to Kafka.

    Args:
        request: The current Pyramid request.
        topic: The Kafka topic to produce to.
        key: Optional message key.
        **kwargs: Payload fields serialized as JSON.
    """

    def __init__(
        self,
        request: Any,
        topic: str,
        key: str | None = None,
        **kwargs: Any,
    ) -> None:
        self.request = request
        self.topic = topic
        self.key = key
        self.kwargs = kwargs


@subscriber(KafkaEvent)
def kafka_event_subscriber(event: KafkaEvent) -> None:
    """Pyramid event subscriber that produces KafkaEvent subclasses to Kafka.

    Args:
        event: The KafkaEvent instance fired by the application.
    """
    manager = event.request.registry.kafka
    manager.produce(topic=event.topic, value=event.kwargs, key=event.key)
    logger.debug("Produced KafkaEvent to topic=%s key=%s", event.topic, event.key)


def _get_kafka_manager(event: Any) -> Any | None:
    """Resolve the KafkaManager from an event's request registry.

    Args:
        event: A Pyramid event with a ``request`` attribute.

    Returns:
        The KafkaManager instance, or None if unavailable.
    """
    request = getattr(event, "request", None)
    if request is not None:
        registry = getattr(request, "registry", None)
        if registry is not None and hasattr(registry, "kafka"):
            return registry.kafka
    return None


def _extract_value(event: Any) -> dict[str, Any]:
    """Extract a serializable dict from an event object.

    Args:
        event: The event instance.

    Returns:
        A dict of the event's public data.
    """
    if dataclasses.is_dataclass(event) and not isinstance(event, type):
        data = {
            f.name: getattr(event, f.name)
            for f in dataclasses.fields(event)
            if not f.name.startswith("_") and f.name != "request"
        }
    else:
        data = {
            k: v
            for k, v in vars(event).items()
            if not k.startswith("_") and k != "request"
        }
    return data


def _make_registered_subscriber(
    topic: str | Callable,
    key: Callable | None,
    value: Callable | None,
) -> Callable:
    """Create a Pyramid subscriber function for a registered event type.

    Args:
        topic: Static topic string or callable ``(event) -> str``.
        key: Optional callable ``(event) -> str`` to extract the message key.
        value: Optional callable ``(event) -> dict`` to extract the payload.

    Returns:
        A subscriber callable suitable for ``config.add_subscriber``.
    """

    def _subscriber(event: Any) -> None:
        resolved_topic = topic(event) if callable(topic) else topic
        resolved_key = key(event) if key is not None else None
        resolved_value = value(event) if value is not None else _extract_value(event)

        manager = _get_kafka_manager(event)
        if manager is None:
            logger.warning(
                "Cannot produce registered event to topic=%s: "
                "no kafka manager on registry",
                resolved_topic,
            )
            return

        manager.produce(topic=resolved_topic, value=resolved_value, key=resolved_key)
        logger.debug(
            "Produced registered event to topic=%s key=%s",
            resolved_topic,
            resolved_key,
        )

    return _subscriber


def register_kafka_event(
    config: Configurator,
    event_type: type,
    topic: str | Callable,
    key: Callable | None = None,
    value: Callable | None = None,
) -> None:
    """Pyramid config directive to register an event type for Kafka forwarding.

    Args:
        config: The Pyramid Configurator instance (injected by Pyramid).
        event_type: The Pyramid event class to subscribe to.
        topic: Static topic string or callable ``(event) -> str``.
        key: Optional callable ``(event) -> str`` to extract the message key.
        value: Optional callable ``(event) -> dict`` to extract the payload.
    """
    sub = _make_registered_subscriber(topic, key, value)
    config.add_subscriber(sub, event_type)
    logger.info(
        "Registered Kafka subscriber for event_type=%s topic=%s",
        event_type.__name__,
        topic if isinstance(topic, str) else topic.__name__,
    )
