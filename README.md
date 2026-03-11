# pyramid-kafka

A Pyramid plugin for Apache Kafka integration (producer/consumer support).

## Installation

```bash
uv add pyramid-kafka
```

Or with pip:

```bash
pip install pyramid-kafka
```

## Usage

```python
# In your Pyramid application
from pyramid.config import Configurator

def main(global_config, **settings):
    config = Configurator(settings=settings)
    config.include("pyramid_kafka")
    return config.make_wsgi_app()
```

## Development

### Prerequisites

- [uv](https://docs.astral.sh/uv/) for dependency management

### Setup

```bash
git clone https://github.com/robbin/pyramid-kafka.git
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
