# Architecture

pyramid-kafka is a Pyramid plugin that integrates Apache Kafka via confluent-kafka. It provides a producer, consumer, and event-driven message dispatch through Pyramid's native event system.

## Package Structure

```
src/pyramid_kafka/
├── __init__.py    # includeme() entry point, public exports
├── core.py        # KafkaManager — lazy Producer/Consumer wrapper, settings parsing
├── producer.py    # KafkaEvent base class, Pyramid subscriber, register_kafka_event directive
└── consumer.py    # Click-based CLI consumer runner with handler resolution
```

## Core Design Decisions

**confluent-kafka over kafka-python**: confluent-kafka is built on librdkafka (C), offering significantly better throughput and lower latency. kafka-python is unmaintained.

**Lazy initialization**: Producer and Consumer are created on first access (via properties), not at `includeme()` time. This avoids blocking app startup when brokers are slow or unreachable, and prevents creating unused clients (e.g., a web worker never needs a consumer).

**Two event capture paths**: (A) `KafkaEvent` base class — subclass it and fire with `notify()`, the library catches all subclasses via a single Pyramid subscriber. (B) `config.register_kafka_event()` — a Pyramid config directive that registers a subscriber for any event type with explicit topic/key/value extraction. Path B allows forwarding events that don't inherit from KafkaEvent.

**Settings via Pyramid .ini**: All config uses the `kafka.` prefix. Known keys (`bootstrap_servers`, `group_id`, etc.) are mapped to confluent-kafka's dot-notation. `kafka.extra.*` passes through arbitrary librdkafka settings.

**Click CLI consumer**: The consumer is a standalone Click command (`kafka-consumer`) that bootstraps a Pyramid app, resolves a handler callable from a dotted path, and runs a poll loop. This mirrors the pattern used in production (payments service `pstream.py`) but generalizes it.

## Component Relationships

```
includeme(config)
  ├── creates KafkaManager(settings) → config.registry.kafka
  ├── adds directive: config.register_kafka_event()
  └── scans producer.py → registers @subscriber(KafkaEvent)

App code:
  notify(SomeKafkaEvent(request, ...))
    → kafka_event_subscriber → manager.produce()
  
  notify(RegisteredEvent(...))
    → _make_registered_subscriber closure → producer.produce()

kafka-consumer CLI:
  bootstrap(ini) → registry.kafka.consumer → poll loop → handler(request, msg)
```
