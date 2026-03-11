"""Tests for pyramid_kafka.producer — KafkaEvent, subscriber, and registration."""

from __future__ import annotations

import dataclasses
import json
from unittest.mock import MagicMock, patch

from pyramid import testing

from pyramid_kafka.producer import (
    KafkaEvent,
    _extract_value,
    _make_registered_subscriber,
    kafka_event_subscriber,
)


def test_kafka_event_stores_attributes():
    """KafkaEvent stores request, topic, key, and kwargs."""
    request = MagicMock()
    event = KafkaEvent(request, "my-topic", key="k1", foo="bar", num=42)

    assert event.request is request
    assert event.topic == "my-topic"
    assert event.key == "k1"
    assert event.kwargs == {"foo": "bar", "num": 42}


def test_kafka_event_key_defaults_to_none():
    """KafkaEvent key defaults to None when omitted."""
    event = KafkaEvent(MagicMock(), "topic")

    assert event.key is None
    assert event.kwargs == {}


@patch("pyramid_kafka.core.Producer")
def test_kafka_event_subscriber_produces_message(mock_producer_cls):
    """The subscriber serializes kwargs and produces to the correct topic."""
    mock_prod = MagicMock()
    mock_producer_cls.return_value = mock_prod

    config = testing.setUp(settings={"kafka.bootstrap_servers": "broker:9092"})
    config.include("pyramid_kafka")
    config.commit()

    request = testing.DummyRequest()
    request.registry = config.registry

    event = KafkaEvent(request, "test-topic", key="k", status="paid")
    kafka_event_subscriber(event)

    mock_prod.produce.assert_called_once()
    call_args = mock_prod.produce.call_args
    assert call_args[0][0] == "test-topic"
    assert json.loads(call_args[1]["value"]) == {"status": "paid"}
    assert call_args[1]["key"] == b"k"
    mock_prod.poll.assert_called_once_with(0)

    testing.tearDown()


@patch("pyramid_kafka.core.Producer")
def test_kafka_event_subclass_caught_by_subscriber(mock_producer_cls):
    """Subclasses of KafkaEvent are caught by the subscriber."""
    mock_prod = MagicMock()
    mock_producer_cls.return_value = mock_prod

    class MyEvent(KafkaEvent):
        def __init__(self, request):
            super().__init__(request, "sub-topic", amount=100)

    config = testing.setUp(settings={"kafka.bootstrap_servers": "broker:9092"})
    config.include("pyramid_kafka")
    config.commit()

    request = testing.DummyRequest()
    request.registry = config.registry

    config.registry.notify(MyEvent(request))

    mock_prod.produce.assert_called_once()
    call_args = mock_prod.produce.call_args
    assert call_args[0][0] == "sub-topic"
    assert json.loads(call_args[1]["value"]) == {"amount": 100}

    testing.tearDown()


def test_extract_value_from_dataclass():
    """_extract_value converts a dataclass instance to a dict."""

    @dataclasses.dataclass
    class MyData:
        name: str
        count: int

    result = _extract_value(MyData(name="test", count=5))
    assert result == {"name": "test", "count": 5}


def test_extract_value_from_regular_object():
    """_extract_value uses vars(), excluding private attrs and request."""

    class Obj:
        def __init__(self):
            self.request = "skip"
            self.name = "hello"
            self._internal = "skip"

    result = _extract_value(Obj())
    assert result == {"name": "hello"}


@patch("pyramid_kafka.core.Producer")
def test_register_kafka_event_directive(mock_producer_cls):
    """config.register_kafka_event() wires a subscriber for the given event type."""
    mock_prod = MagicMock()
    mock_producer_cls.return_value = mock_prod

    @dataclasses.dataclass
    class OrderPlaced:
        request: object
        order_id: str
        amount: float

    config = testing.setUp(settings={"kafka.bootstrap_servers": "broker:9092"})
    config.include("pyramid_kafka")
    config.register_kafka_event(
        OrderPlaced,
        topic="orders.placed.v1",
        key=lambda e: e.order_id,
        value=lambda e: {"order_id": e.order_id, "amount": e.amount},
    )
    config.commit()

    request = testing.DummyRequest()
    request.registry = config.registry

    config.registry.notify(OrderPlaced(request=request, order_id="o-1", amount=99.5))

    mock_prod.produce.assert_called_once()
    call_args = mock_prod.produce.call_args
    assert call_args[0][0] == "orders.placed.v1"
    produced_value = json.loads(call_args[1]["value"])
    assert produced_value == {"order_id": "o-1", "amount": 99.5}
    assert call_args[1]["key"] == b"o-1"

    testing.tearDown()


@patch("pyramid_kafka.core.Producer")
def test_register_kafka_event_auto_value_extraction(mock_producer_cls):
    """register_kafka_event without value= auto-extracts from dataclass."""
    mock_prod = MagicMock()
    mock_producer_cls.return_value = mock_prod

    @dataclasses.dataclass
    class UserCreated:
        request: object
        user_id: str

    config = testing.setUp(settings={"kafka.bootstrap_servers": "broker:9092"})
    config.include("pyramid_kafka")
    config.register_kafka_event(UserCreated, topic="users.created.v1")
    config.commit()

    request = testing.DummyRequest()
    request.registry = config.registry

    config.registry.notify(UserCreated(request=request, user_id="u-42"))

    mock_prod.produce.assert_called_once()
    produced_value = json.loads(mock_prod.produce.call_args[1]["value"])
    assert produced_value["user_id"] == "u-42"

    testing.tearDown()


def test_make_registered_subscriber_with_callable_topic():
    """_make_registered_subscriber supports callable topic."""
    sub = _make_registered_subscriber(
        topic=lambda e: f"dynamic.{e.entity}",
        key=None,
        value=lambda e: {"id": e.entity_id},
    )

    mock_registry = MagicMock()
    event = MagicMock()
    event.entity = "order"
    event.entity_id = "123"
    event.request.registry = mock_registry

    sub(event)

    mock_registry.kafka.producer.produce.assert_called_once()
    call_args = mock_registry.kafka.producer.produce.call_args
    assert call_args[0][0] == "dynamic.order"
