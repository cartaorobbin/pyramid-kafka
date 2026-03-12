# Configuration

pyramid-kafka is configured through your Pyramid `.ini` file using the `kafka.` prefix. The plugin reads these settings when you call `config.include("pyramid_kafka")`.

## Required Settings

| Setting | Description |
|---|---|
| `kafka.bootstrap_servers` | Comma-separated list of Kafka broker addresses |

## Consumer Settings

These settings are only required when using the consumer (CLI or `KafkaManager.consumer`).

| Setting | Default | Description |
|---|---|---|
| `kafka.group_id` | — | Consumer group ID (required for consumer) |
| `kafka.auto_offset_reset` | `earliest` | Where to start consuming: `earliest` or `latest` |
| `kafka.topics` | — | Space or comma-separated list of topics to consume |
| `kafka.handler` | — | Dotted path to handler callable (`module.path:function`) |

## Optional Settings

| Setting | Description |
|---|---|
| `kafka.client_id` | Client identifier sent to the broker |

## Pass-Through Settings

Any setting prefixed with `kafka.extra.` is passed directly to confluent-kafka (and the underlying librdkafka). This gives you access to the full range of [librdkafka configuration properties](https://github.com/confluentinc/librdkafka/blob/master/CONFIGURATION.md).

The `kafka.extra.` prefix is stripped before passing to confluent-kafka:

```ini
kafka.extra.security.protocol = SASL_SSL
kafka.extra.sasl.mechanisms = PLAIN
kafka.extra.sasl.username = my-key
kafka.extra.sasl.password = my-secret
```

These become `security.protocol`, `sasl.mechanisms`, `sasl.username`, and `sasl.password` in the confluent-kafka config dict.

## Full Example

```ini
[app:main]
use = egg:myapp

# Required
kafka.bootstrap_servers = broker1:9092,broker2:9092

# Consumer
kafka.group_id = my-service
kafka.auto_offset_reset = earliest
kafka.topics = orders.created.v1 payments.received.v1
kafka.handler = myapp.stream:process_message

# Optional
kafka.client_id = my-service

# Pass-through to librdkafka
kafka.extra.security.protocol = SASL_SSL
kafka.extra.sasl.mechanisms = PLAIN
kafka.extra.sasl.username = my-key
kafka.extra.sasl.password = my-secret
```

## How Settings Are Mapped

The plugin translates Pyramid-style settings to confluent-kafka's dot-notation:

| Pyramid Setting | confluent-kafka Key |
|---|---|
| `kafka.bootstrap_servers` | `bootstrap.servers` |
| `kafka.group_id` | `group.id` |
| `kafka.auto_offset_reset` | `auto.offset.reset` |
| `kafka.client_id` | `client.id` |
| `kafka.extra.<key>` | `<key>` (passed through directly) |
