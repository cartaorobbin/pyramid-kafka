# pyramid-kafka

A Pyramid plugin for Apache Kafka integration using [confluent-kafka](https://github.com/confluentinc/confluent-kafka-python). Provides producer/consumer support with lazy initialization, Pyramid event integration, and a CLI consumer runner.

## Installation

```bash
uv add pyramid-kafka
```

Or with pip:

```bash
pip install pyramid-kafka
```

## Quick Start

### 1. Include the plugin

```python
from pyramid.config import Configurator

def main(global_config, **settings):
    config = Configurator(settings=settings)
    config.include("pyramid_kafka")
    return config.make_wsgi_app()
```

### 2. Configure your `.ini` file

```ini
# Required
kafka.bootstrap_servers = localhost:9092

# Consumer settings (required for consumer only)
kafka.group_id = my-service
kafka.auto_offset_reset = earliest

# Optional
kafka.client_id = my-service
kafka.topics = my.topic.v1 another.topic.v1
kafka.handler = myapp.stream:process_message

# Pass-through to confluent-kafka (any librdkafka setting)
kafka.extra.security.protocol = SASL_SSL
kafka.extra.sasl.mechanisms = PLAIN
kafka.extra.sasl.username = my-key
kafka.extra.sasl.password = my-secret
```

### 3. Produce events

#### Option A: Subclass KafkaEvent

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

# Fire the event from your view or service:
request.registry.notify(OrderCreated(request, order))
```

#### Option B: Register any Pyramid event

```python
from dataclasses import dataclass

@dataclass
class PaymentReceived:
    request: object
    payment_id: str
    amount: float

# In your app's startup/includeme:
config.register_kafka_event(
    PaymentReceived,
    topic="payments.received.v1",
    key=lambda e: e.payment_id,
    value=lambda e: {"payment_id": e.payment_id, "amount": e.amount},
)

# Then just fire the standard Pyramid event:
request.registry.notify(PaymentReceived(request=request, payment_id="p-1", amount=50.0))
```

If `value` is omitted, the library auto-extracts all public fields (uses `dataclasses.fields()` for dataclasses, `vars()` for others, excluding `request` and private attributes).

### 4. Consume messages

Run the built-in CLI consumer:

```bash
kafka-consumer development.ini
```

The consumer reads `kafka.topics` (space or comma-separated) and `kafka.handler` from settings. The handler is a dotted Python path to a callable with signature `(request, message) -> None`:

```python
# myapp/stream.py
import json

def process_message(request, message):
    value = json.loads(message.value().decode("utf-8"))
    topic = message.topic()
    # Route to your business logic...
```

CLI options override settings:

```bash
kafka-consumer development.ini --handler myapp.stream:process_message --topics "topic-a,topic-b" --timeout 2.0
```

## Configuration Reference

| Setting | Required | Default | Description |
|---|---|---|---|
| `kafka.bootstrap_servers` | Yes | — | Comma-separated Kafka broker list |
| `kafka.group_id` | Consumer only | — | Consumer group ID |
| `kafka.auto_offset_reset` | No | `earliest` | Where to start consuming (`earliest` / `latest`) |
| `kafka.client_id` | No | — | Client identifier |
| `kafka.topics` | Consumer only | — | Space or comma-separated topic list |
| `kafka.handler` | Consumer only | — | Dotted path to handler callable (`module:function`) |
| `kafka.extra.*` | No | — | Pass-through to confluent-kafka/librdkafka config |

## API

### `KafkaManager`

Attached to `config.registry.kafka` after `config.include("pyramid_kafka")`.

- `manager.producer` — Lazily-initialized `confluent_kafka.Producer`
- `manager.consumer` — Lazily-initialized `confluent_kafka.Consumer`
- `manager.produce(topic, value, key=None)` — JSON-serialize and produce a message
- `manager.close()` — Flush producer and close consumer

### `KafkaEvent`

Base class for Kafka-bound Pyramid events. Subclass it and fire via `request.registry.notify()`.

### `config.register_kafka_event(event_type, topic, key=None, value=None)`

Pyramid config directive to wire any event class to Kafka. `topic` can be a string or callable `(event) -> str`. `key` and `value` are optional callables `(event) -> str|dict`.

## Development

### Prerequisites

- [uv](https://docs.astral.sh/uv/) for dependency management

### Setup

```bash
git clone https://github.com/cartaorobbin/pyramid-kafka.git
cd pyramid-kafka
uv sync --dev
```

### Running Tests

```bash
uv run pytest
```

### Linting and Formatting

```bash
uv run ruff check .
uv run black .
```

### Building Documentation

```bash
uv run mkdocs serve
```

## License

MIT
