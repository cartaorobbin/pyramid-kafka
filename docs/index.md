# pyramid-kafka

A Pyramid plugin for Apache Kafka integration using [confluent-kafka](https://github.com/confluentinc/confluent-kafka-python). Provides producer/consumer support with lazy initialization, Pyramid event integration, and a CLI consumer runner.

## Getting Started

### Installation

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

See the [Configuration](configuration.md) and [API Reference](api.md) for full details.
