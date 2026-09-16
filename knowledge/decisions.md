# Architectural Decisions

Record of key technical and architectural decisions for this project.

## Template

Use this format when adding a new decision:

### YYYY-MM-DD — Decision Title

**Status**: Accepted | Superseded | Deprecated

**Context**: What is the issue or situation that motivates this decision?

**Decision**: What is the change that we're proposing or have agreed to?

**Consequences**: What are the trade-offs and results of this decision?

---

## Decisions

### 2026-03-11 — Initial project setup

**Status**: Accepted

**Context**: Starting a new project that needs a solid foundation.

**Decision**: Using uv with src layout, ruff + black for linting/formatting, pytest for testing, and MkDocs for documentation.

**Consequences**: Consistent project structure that follows Python best practices. All team members and AI assistants can rely on the same conventions.

---

### 2026-03-15 — Transactional commit strategy via IDataManager

**Status**: Accepted

**Context**: When producing Kafka messages during a Pyramid request, the message is sent immediately — even if the request later fails and the database transaction is rolled back. This creates data inconsistency: a Kafka consumer may process a message whose originating DB changes were never committed. Similarly, the consumer auto-commits offsets regardless of handler success, risking message loss.

**Decision**: Implement a `KafkaDataManager` that participates in the `transaction` package's two-phase commit protocol, following the same pattern as `zope.sqlalchemy`. Controlled by a new `kafka.commit_strategy` setting (`auto` or `transaction`). When `transaction` is chosen: (1) producer messages are buffered in memory and only sent when the Pyramid transaction commits; (2) consumer auto-commit is disabled and offsets are committed manually after successful processing. The `transaction` package is an optional dependency.

**Consequences**:
- Full backward compatibility — `auto` (default) preserves existing behavior.
- Producer messages participate in the same transaction as DB writes via `pyramid_tm`.
- The `KafkaDataManager` sort key (`~pyramid_kafka`) ensures Kafka commits after database managers, minimising the window where a sent message could correspond to a rolled-back DB transaction.
- Consumer offset commits are tied to handler success, enabling at-least-once delivery semantics.
- Trade-off: Kafka is not truly transactional. If `tpc_finish` succeeds for the DB but Kafka flush fails, the DB commit cannot be rolled back. The sort-key ordering minimises but cannot eliminate this window.

**Superseded in part**: Consumer `auto` no longer relies on librdkafka interval auto-commit. See 2026-09-16.

---

### 2026-09-16 — Support Python 3.11 and 3.12

**Status**: Accepted

**Context**: The package declared `requires-python = ">=3.13"` and CI only ran on 3.13. Many Pyramid applications still run 3.11 and 3.12. The library source already uses `from __future__ import annotations` and 3.10-era typing, so it does not depend on 3.13-only language features.

**Decision**: Support Python 3.11+ (`requires-python = ">=3.11"`), including current 3.13. Black and Ruff target `py311`. CI lints on 3.13 and tests on 3.11, 3.12, and 3.13.

**Consequences**:
- Installers accept 3.11 and 3.12.
- Compatibility is gated by the CI matrix rather than by 3.13-only syntax.
- Tooling must not rewrite code to 3.12+ or 3.13-only constructs.

---

### 2026-09-16 — Consumer auto commits after handler success

**Status**: Accepted

**Context**: `kafka.commit_strategy` has two values (`auto` and `transaction`) shared by producer and consumer. Producer `auto` sends immediately; that stays. Consumer `auto` previously left offsets to librdkafka (`enable.auto.commit`), so a failed handler could still have its offset committed, and apps that wanted commit-after-success had to call `consumer.commit` themselves.

**Decision**: Keep one setting with two values. Change consumer `auto` so the CLI owns the offset: always set `enable.auto.commit=false` (including overwriting `kafka.extra.enable.auto.commit`), run the handler, then `consumer.commit(message=msg, asynchronous=False)` on success. On handler failure, log and skip commit. Offset-commit failures are logged as offset errors, not handler errors, and do not abort a transaction that already committed. Handlers stay `(request, message)`. `transaction` still wraps the handler in a Pyramid `transaction` manager, then commits the offset. Custom poll loops without the CLI must commit themselves.

**Consequences**:
- App handlers do not call `consumer.commit`.
- Consumer `auto` is at-least-once (late commit), not librdkafka interval auto-commit. This is a breaking change for default `auto`.
- Failed messages are redelivered instead of silently skipped. A handler that always fails redelivers forever.
- Anyone using `registry.kafka.consumer` without the CLI must commit offsets or the group never advances.
- Producer `auto` is still immediate send.
- Default remains `auto`; `transaction` stays an opt-in extra.
- Offset commit after `txn.commit()` must not call `abort()`; the explicit manager has no transaction left.
