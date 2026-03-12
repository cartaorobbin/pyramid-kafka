# pyramid-kafka

A Pyramid plugin for Apache Kafka integration using [confluent-kafka](https://github.com/confluentinc/confluent-kafka-python). Provides producer/consumer support with lazy initialization, Pyramid event integration, and a CLI consumer runner.

## Features

- **Lazy initialization** — Producer and Consumer connect on first use, not at startup
- **Pyramid event integration** — Produce messages by firing standard Pyramid events
- **Two event paths** — Subclass `KafkaEvent` or use `register_kafka_event()` with any event class
- **CLI consumer** — Built-in `kafka-consumer` command with graceful shutdown
- **Pass-through config** — Full access to librdkafka settings via `kafka.extra.*`

## Quick Start

### Install

```bash
uv add pyramid-kafka
```

### Include the plugin

```python
from pyramid.config import Configurator

def main(global_config, **settings):
    config = Configurator(settings=settings)
    config.include("pyramid_kafka")
    return config.make_wsgi_app()
```

### Configure

Add Kafka settings to your `.ini` file:

```ini
kafka.bootstrap_servers = localhost:9092
kafka.group_id = my-service
```

### Produce an event

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

request.registry.notify(OrderCreated(request, order))
```

### Consume messages

```bash
kafka-consumer development.ini
```

## Next Steps

- [Configuration](configuration.md) — Full settings reference and examples
- [API Reference](api.md) — `KafkaManager`, `KafkaEvent`, `register_kafka_event()`, and CLI details
