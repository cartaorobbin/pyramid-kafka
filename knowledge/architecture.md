# Architecture

pyramid-kafka is a Pyramid plugin that integrates Apache Kafka via confluent-kafka. It provides a producer, consumer, event-driven message dispatch through Pyramid's native event system, and optional transaction integration via `pyramid_tm`.

## Package Structure

```
src/pyramid_kafka/
├── __init__.py       # includeme() entry point, public exports
├── core.py           # KafkaManager — lazy Producer/Consumer wrapper, settings parsing, transaction routing
├── producer.py       # KafkaEvent base class, Pyramid subscriber, register_kafka_event directive
├── consumer.py       # Click-based CLI consumer runner with handler resolution
└── transaction.py    # KafkaDataManager — IDataManager for buffering produces until transaction commit
```

## Core Design Decisions

**confluent-kafka over kafka-python**: confluent-kafka is built on librdkafka (C), offering significantly better throughput and lower latency. kafka-python is unmaintained.

**Lazy initialization**: Producer and Consumer are created on first access (via properties), not at `includeme()` time. This avoids blocking app startup when brokers are slow or unreachable, and prevents creating unused clients (e.g., a web worker never needs a consumer).

**Two event capture paths**: (A) `KafkaEvent` base class — subclass it and fire with `notify()`, the library catches all subclasses via a single Pyramid subscriber. (B) `config.register_kafka_event()` — a Pyramid config directive that registers a subscriber for any event type with explicit topic/key/value extraction. Path B allows forwarding events that don't inherit from KafkaEvent.

**Settings via Pyramid .ini**: All config uses the `kafka.` prefix. Known keys (`bootstrap_servers`, `group_id`, etc.) are mapped to confluent-kafka's dot-notation. `kafka.extra.*` passes through arbitrary librdkafka settings. `kafka.commit_strategy` controls transaction integration.

**Click CLI consumer**: The consumer is a standalone Click command (`kafka-consumer`) that bootstraps a Pyramid app, resolves a handler callable from a dotted path, and runs a poll loop.

**Transaction integration via IDataManager**: When `kafka.commit_strategy = transaction`, a `KafkaDataManager` participates in the `transaction` package's two-phase commit protocol (same pattern as `zope.sqlalchemy`). Messages are buffered during the request and only sent when the transaction commits. The sort key `~pyramid_kafka` ensures Kafka commits after database managers, so a DB failure aborts before any message is sent.

## Component Relationships

```
includeme(config)
  ├── creates KafkaManager(settings) → config.registry.kafka
  ├── adds directive: config.register_kafka_event()
  └── scans producer.py → registers @subscriber(KafkaEvent)

App code (commit_strategy=auto):
  notify(SomeKafkaEvent(request, ...))
    → kafka_event_subscriber → manager.produce() → immediate send

App code (commit_strategy=transaction):
  notify(SomeKafkaEvent(request, ...))
    → kafka_event_subscriber → manager.produce(request=request)
    → KafkaDataManager.append() (buffered)
    → on transaction.commit(): KafkaDataManager.commit() → producer.produce()
    → on transaction.abort():  KafkaDataManager.abort() → buffer discarded

kafka-consumer CLI (commit_strategy=auto):
  bootstrap(ini) → registry.kafka.consumer → poll loop → handler(request, msg)

kafka-consumer CLI (commit_strategy=transaction):
  bootstrap(ini) → consumer(enable.auto.commit=false) → poll loop
    → per message: begin txn → handler(request, msg) → commit txn → commit offset
    → on error: abort txn → offset not committed → message redelivered
```

## Commit Strategy

The `kafka.commit_strategy` setting controls how messages are committed:

| Strategy | Producer | Consumer |
|---|---|---|
| `auto` (default) | Messages sent immediately | Offsets auto-committed by librdkafka |
| `transaction` | Messages buffered, sent on `pyramid_tm` commit | `enable.auto.commit=false`, offsets committed after handler success |
