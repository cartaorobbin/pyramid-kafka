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
