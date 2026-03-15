"""Integration tests — real transaction lifecycle, only the Kafka broker is mocked."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
import transaction as txn_pkg

from pyramid_kafka.transaction import KafkaDataManager


@pytest.fixture()
def producer() -> MagicMock:
    """A mock confluent-kafka Producer (the only thing we mock)."""
    p = MagicMock()
    p.flush.return_value = 0
    return p


def test_transaction_commit_sends_all_buffered_messages(producer):
    """When the transaction commits, every buffered message is produced and flushed."""
    tm = txn_pkg.TransactionManager(explicit=True)
    tm.begin()

    dm = KafkaDataManager(producer)
    tm.get().join(dm)

    dm.append("orders", b'{"id":"o1"}', b"o1", None)
    dm.append("payments", b'{"amount":100}', b"p1", None)

    tm.commit()

    assert producer.produce_batch.call_count == 2

    calls = {c[0][0]: c[0][1] for c in producer.produce_batch.call_args_list}
    assert calls["orders"] == [{"value": b'{"id":"o1"}', "key": b"o1"}]
    assert calls["payments"] == [{"value": b'{"amount":100}', "key": b"p1"}]

    producer.flush.assert_called_once()


def test_transaction_abort_discards_all_buffered_messages(producer):
    """When the transaction aborts, no message is produced."""
    tm = txn_pkg.TransactionManager(explicit=True)
    tm.begin()

    dm = KafkaDataManager(producer)
    tm.get().join(dm)

    dm.append("orders", b'{"id":"o1"}', b"o1", None)

    tm.abort()

    producer.produce_batch.assert_not_called()
    producer.flush.assert_not_called()


def test_transaction_abort_on_flush_failure(producer):
    """If flush times out in tpc_vote, the transaction aborts cleanly."""
    producer.flush.return_value = 2

    tm = txn_pkg.TransactionManager(explicit=True)
    tm.begin()

    dm = KafkaDataManager(producer)
    tm.get().join(dm)

    dm.append("t", b"v", None, None)

    with pytest.raises(RuntimeError, match="2 messages still pending"):
        tm.commit()

    assert dm._buffer == []


def test_multiple_data_managers_commit_order(producer):
    """KafkaDataManager commits after other data managers (sort key ordering)."""
    call_order: list[str] = []

    class FakeDbManager:
        transaction_manager = None

        def sortKey(self):  # noqa: N802
            return "sqlalchemy"

        def abort(self, txn):
            call_order.append("db:abort")

        def tpc_begin(self, txn):
            pass

        def commit(self, txn):
            call_order.append("db:commit")

        def tpc_vote(self, txn):
            call_order.append("db:vote")

        def tpc_finish(self, txn):
            call_order.append("db:finish")

        def tpc_abort(self, txn):
            pass

    def track_produce_batch(*args, **kwargs):
        call_order.append("kafka:produce_batch")

    def track_flush(**kwargs):
        call_order.append("kafka:flush")
        return 0

    producer.produce_batch.side_effect = track_produce_batch
    producer.flush.side_effect = track_flush

    tm = txn_pkg.TransactionManager(explicit=True)
    tm.begin()

    db = FakeDbManager()
    kafka = KafkaDataManager(producer)

    tm.get().join(db)
    tm.get().join(kafka)

    kafka.append("t", b"v", None, None)

    tm.commit()

    assert call_order.index("db:commit") < call_order.index("kafka:produce_batch")
    assert call_order.index("db:vote") < call_order.index("kafka:flush")


def test_db_failure_prevents_kafka_send(producer):
    """If a DB-like manager fails in tpc_vote, Kafka messages are never sent."""

    class FailingDbManager:
        transaction_manager = None

        def sortKey(self):  # noqa: N802
            return "sqlalchemy"

        def abort(self, txn):
            pass

        def tpc_begin(self, txn):
            pass

        def commit(self, txn):
            pass

        def tpc_vote(self, txn):
            raise RuntimeError("DB constraint violation")

        def tpc_finish(self, txn):
            pass

        def tpc_abort(self, txn):
            pass

    tm = txn_pkg.TransactionManager(explicit=True)
    tm.begin()

    db = FailingDbManager()
    kafka = KafkaDataManager(producer)

    tm.get().join(db)
    tm.get().join(kafka)

    kafka.append("orders", b'{"id":"o1"}', b"o1", None)

    with pytest.raises(RuntimeError, match="DB constraint violation"):
        tm.commit()

    producer.produce_batch.assert_not_called()
    producer.flush.assert_not_called()


def test_transaction_commit_clears_buffer(producer):
    """After a successful commit the buffer is empty."""
    tm = txn_pkg.TransactionManager(explicit=True)
    tm.begin()

    dm = KafkaDataManager(producer)
    tm.get().join(dm)
    dm.append("t", b"v", None, None)

    tm.commit()

    assert dm._buffer == []
