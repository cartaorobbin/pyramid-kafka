"""Transaction-aware data manager for buffering Kafka produces until commit."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable

    from confluent_kafka import Producer

logger = logging.getLogger(__name__)

_SORT_KEY = "~pyramid_kafka"


class KafkaDataManager:
    """A ``transaction.interfaces.IDataManager`` that buffers Kafka messages.

    Messages appended via ``append()`` are held in memory until the
    two-phase commit vote.  On ``tpc_vote`` the messages are produced
    and flushed.  On abort the buffer is silently discarded.

    The sort key (``~pyramid_kafka``) ensures this data manager votes
    **after** database managers (whose keys sort earlier).  Because
    ``tpc_vote`` is called in sort order, a DB vote failure prevents
    Kafka messages from ever being queued.
    """

    transaction_manager: Any = None

    def __init__(self, producer: Producer, flush_timeout: float = 10.0) -> None:
        """Initialize the data manager with a confluent-kafka Producer.

        Args:
            producer: The confluent-kafka Producer instance.
            flush_timeout: Seconds to wait when flushing in tpc_vote.
        """
        self._producer = producer
        self._flush_timeout = flush_timeout
        self._buffer: list[tuple[str, bytes, bytes | None, Callable | None]] = []

    def append(
        self,
        topic: str,
        value: bytes,
        key: bytes | None,
        on_delivery: Callable | None,
    ) -> None:
        """Buffer a message for later production.

        Args:
            topic: Kafka topic name.
            value: Pre-serialized message value.
            key: Optional pre-serialized message key.
            on_delivery: Optional delivery callback.
        """
        self._buffer.append((topic, value, key, on_delivery))

    # -- IDataManager protocol ------------------------------------------------

    def abort(self, txn: Any) -> None:
        """Discard all buffered messages.

        Args:
            txn: The transaction being aborted.
        """
        self._buffer.clear()

    def tpc_begin(self, txn: Any) -> None:
        """Begin two-phase commit (no-op).

        Args:
            txn: The current transaction.
        """

    def commit(self, txn: Any) -> None:
        """First phase (no-op).

        Producing is deferred to ``tpc_vote`` so that earlier data
        managers (e.g. the database) can still abort the transaction
        in their own ``tpc_vote`` before any Kafka message is queued.

        Args:
            txn: The current transaction.
        """

    def tpc_vote(self, txn: Any) -> None:
        """Produce buffered messages and flush, or abort the transaction.

        This is the last chance to abort.  Messages are grouped by
        topic and sent via ``Producer.produce_batch`` then flushed to
        confirm broker acknowledgement.  Because the sort key places
        this manager after database managers, a DB ``tpc_vote``
        failure means this method is never called — no messages are
        sent.

        Args:
            txn: The current transaction.

        Raises:
            RuntimeError: If messages could not be flushed within the timeout.
        """
        by_topic: dict[str, list[dict[str, Any]]] = {}
        for topic, value, key, on_delivery in self._buffer:
            msg: dict[str, Any] = {"value": value}
            if key is not None:
                msg["key"] = key
            if on_delivery is not None:
                msg["on_delivery"] = on_delivery
            by_topic.setdefault(topic, []).append(msg)

        for topic, messages in by_topic.items():
            self._producer.produce_batch(topic, messages)

        remaining = self._producer.flush(timeout=self._flush_timeout)
        if remaining > 0:
            raise RuntimeError(
                f"Kafka flush timed out with {remaining} messages still pending"
            )

    def tpc_finish(self, txn: Any) -> None:
        """Complete the commit — clear the buffer.

        Args:
            txn: The current transaction.
        """
        count = len(self._buffer)
        self._buffer.clear()
        logger.debug("Transaction committed %d Kafka message(s)", count)

    def tpc_abort(self, txn: Any) -> None:
        """Abort the two-phase commit — discard buffered messages.

        Args:
            txn: The current transaction.
        """
        self._buffer.clear()
        logger.debug("Transaction aborted — discarded buffered Kafka messages")

    def sortKey(self) -> str:  # noqa: N802
        """Return a key that sorts after typical database managers.

        Returns:
            The string ``~pyramid_kafka``.
        """
        return _SORT_KEY
