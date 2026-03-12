# API Reference

## Plugin Entry Point

### `includeme(config)`

Pyramid entry point that wires up Kafka support. Called automatically when you use:

```python
config.include("pyramid_kafka")
```

This does three things:

1. Creates a [`KafkaManager`](#kafkamanager) and attaches it to `config.registry.kafka`
2. Registers the `config.register_kafka_event()` directive
3. Scans the built-in `KafkaEvent` subscriber

---

## KafkaManager

```python
from pyramid_kafka import KafkaManager
```

Lazy wrapper around confluent-kafka `Producer` and `Consumer`. Attached to the Pyramid registry as `config.registry.kafka` after including the plugin.

Producer and Consumer instances are created on first access — not at startup — to avoid blocking the application when brokers are unreachable and to prevent creating unused clients.

### Properties

#### `manager.producer`

Returns a lazily-initialized `confluent_kafka.Producer`. Consumer-only settings (`group.id`, `auto.offset.reset`) are excluded from the producer config.

#### `manager.consumer`

Returns a lazily-initialized `confluent_kafka.Consumer`.

**Raises** `KeyError` if `kafka.group_id` is not set.

### Methods

#### `manager.produce(topic, value, key=None, on_delivery=None)`

Serialize `value` as JSON and produce a message.

| Parameter | Type | Description |
|---|---|---|
| `topic` | `str` | Kafka topic to produce to |
| `value` | `dict[str, Any]` | Payload, serialized as JSON |
| `key` | `str \| None` | Optional message key |
| `on_delivery` | `Callable \| None` | Optional delivery report callback |

#### `manager.close()`

Flush the producer (waits for pending messages) and close the consumer.

---

## KafkaEvent

```python
from pyramid_kafka import KafkaEvent
```

Base class for Kafka-bound Pyramid events. Subclass it and fire via `request.registry.notify()` to automatically produce messages.

### Constructor

```python
KafkaEvent(request, topic, key=None, **kwargs)
```

| Parameter | Type | Description |
|---|---|---|
| `request` | `Request` | The current Pyramid request |
| `topic` | `str` | Kafka topic to produce to |
| `key` | `str \| None` | Optional message key |
| `**kwargs` | `Any` | Payload fields, serialized as JSON |

### Example

```python
from pyramid_kafka import KafkaEvent

class OrderCreated(KafkaEvent):
    def __init__(self, request, order):
        super().__init__(
            request,
            topic="orders.created.v1",
            key=str(order.id),
            order_id=str(order.id),
            amount=float(order.amount),
        )

# In a view or service:
request.registry.notify(OrderCreated(request, order))
```

---

## config.register_kafka_event()

```python
config.register_kafka_event(event_type, topic, key=None, value=None)
```

Pyramid config directive that wires any event class to Kafka — no need to subclass `KafkaEvent`.

| Parameter | Type | Description |
|---|---|---|
| `event_type` | `type` | The Pyramid event class to subscribe to |
| `topic` | `str \| Callable[[event], str]` | Static topic string or callable |
| `key` | `Callable[[event], str] \| None` | Optional callable to extract the message key |
| `value` | `Callable[[event], dict] \| None` | Optional callable to extract the payload |

If `value` is omitted, the library auto-extracts all public fields. For dataclasses it uses `dataclasses.fields()`; for other objects it uses `vars()`. The `request` attribute and private fields (prefixed with `_`) are excluded.

### Example

```python
from dataclasses import dataclass

@dataclass
class PaymentReceived:
    request: object
    payment_id: str
    amount: float

config.register_kafka_event(
    PaymentReceived,
    topic="payments.received.v1",
    key=lambda e: e.payment_id,
    value=lambda e: {"payment_id": e.payment_id, "amount": e.amount},
)

# Fire the event normally:
request.registry.notify(
    PaymentReceived(request=request, payment_id="p-1", amount=50.0)
)
```

---

## CLI Consumer

```
kafka-consumer <ini_file> [OPTIONS]
```

A Click-based command that bootstraps a Pyramid application and runs a Kafka consumer poll loop.

### Arguments

| Argument | Description |
|---|---|
| `ini_file` | Path to the Pyramid `.ini` configuration file |

### Options

| Option | Default | Description |
|---|---|---|
| `--handler` | from settings | Dotted path to handler callable (overrides `kafka.handler`) |
| `--topics` | from settings | Comma-separated topic list (overrides `kafka.topics`) |
| `--timeout` | `1.0` | Consumer poll timeout in seconds |

### Handler Signature

The handler is a callable that receives the Pyramid request and the raw confluent-kafka message:

```python
def process_message(request, message):
    value = json.loads(message.value().decode("utf-8"))
    topic = message.topic()
    # Route to your business logic...
```

### Signal Handling

The consumer responds to `SIGINT` and `SIGTERM` for graceful shutdown. On receiving either signal, it finishes processing the current message, flushes the producer, closes the consumer, and exits cleanly.
