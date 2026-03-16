"""Tests for pyramid_kafka.transaction — KafkaDataManager."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from pyramid_kafka.transaction import KafkaDataManager


@pytest.fixture()
def data_manager(mock_producer) -> KafkaDataManager:
    """Return a KafkaDataManager wired to a mock producer."""
    return KafkaDataManager(mock_producer)


def test_data_manager_append_buffers_messages(data_manager):
    """append() accumulates messages without touching the producer."""
    data_manager.append("topic-a", b'{"a":1}', b"k1", None)
    data_manager.append("topic-b", b'{"b":2}', None, None)

    assert len(data_manager._buffer) == 2
    assert data_manager._buffer[0] == ("topic-a", b'{"a":1}', b"k1", None)


def test_data_manager_commit_is_noop(data_manager):
    """commit() does nothing — producing is deferred to tpc_vote."""
    data_manager.append("t1", b"v1", b"k1", None)

    data_manager.commit(txn=None)

    data_manager._producer.produce.assert_not_called()
    data_manager._producer.flush.assert_not_called()
    assert len(data_manager._buffer) == 1


def test_data_manager_tpc_vote_produces_batch_and_flushes(data_manager):
    """tpc_vote() groups messages by topic and calls produce_batch."""
    data_manager.append("t1", b"v1", b"k1", None)
    data_manager.append("t1", b"v2", None, None)
    data_manager.append("t2", b"v3", b"k3", None)

    data_manager.tpc_vote(txn=None)

    producer = data_manager._producer
    assert producer.produce_batch.call_count == 2

    calls = {c[0][0]: c[0][1] for c in producer.produce_batch.call_args_list}
    assert calls["t1"] == [{"value": b"v1", "key": b"k1"}, {"value": b"v2"}]
    assert calls["t2"] == [{"value": b"v3", "key": b"k3"}]
    producer.flush.assert_called_once_with(timeout=10.0)


def test_data_manager_tpc_vote_raises_on_flush_timeout(data_manager):
    """tpc_vote() raises RuntimeError when flush reports pending messages."""
    data_manager._producer.flush.return_value = 3
    data_manager.append("t", b"v", None, None)

    with pytest.raises(RuntimeError, match="3 messages still pending"):
        data_manager.tpc_vote(txn=None)


def test_data_manager_tpc_finish_clears_buffer(data_manager):
    """tpc_finish() empties the buffer after a successful commit."""
    data_manager.append("t", b"v", None, None)
    data_manager.tpc_finish(txn=None)

    assert data_manager._buffer == []


def test_data_manager_abort_discards_buffer(data_manager):
    """abort() clears the buffer without producing anything."""
    data_manager.append("t", b"v", None, None)
    data_manager.abort(txn=None)

    assert data_manager._buffer == []
    data_manager._producer.produce.assert_not_called()


def test_data_manager_tpc_abort_discards_buffer(data_manager):
    """tpc_abort() clears the buffer after a failed two-phase commit."""
    data_manager.append("t", b"v", None, None)
    data_manager.tpc_abort(txn=None)

    assert data_manager._buffer == []


def test_data_manager_sort_key_is_after_databases(data_manager):
    """sortKey() returns a value that sorts after typical DB managers."""
    key = data_manager.sortKey()

    assert key == "~pyramid_kafka"
    assert key > "sqlalchemy"


def test_data_manager_custom_flush_timeout():
    """KafkaDataManager accepts a custom flush_timeout."""
    producer = MagicMock()
    producer.flush.return_value = 0
    dm = KafkaDataManager(producer, flush_timeout=30.0)

    dm.tpc_vote(txn=None)

    producer.flush.assert_called_once_with(timeout=30.0)


def test_data_manager_full_two_phase_commit(data_manager):
    """Full two-phase commit cycle: begin, commit, vote, finish."""
    data_manager.append("orders", b'{"id":"o1"}', b"o1", None)

    data_manager.tpc_begin(txn=None)
    data_manager.commit(txn=None)
    data_manager.tpc_vote(txn=None)
    data_manager.tpc_finish(txn=None)

    data_manager._producer.produce_batch.assert_called_once_with(
        "orders", [{"value": b'{"id":"o1"}', "key": b"o1"}]
    )
    data_manager._producer.flush.assert_called_once()
    assert data_manager._buffer == []


def test_data_manager_tpc_abort_after_commit_never_produces(data_manager):
    """tpc_abort after commit discards buffer — produce was never called."""
    data_manager.append("t", b"v", None, None)

    data_manager.tpc_begin(txn=None)
    data_manager.commit(txn=None)
    data_manager.tpc_abort(txn=None)

    assert data_manager._buffer == []
    data_manager._producer.produce.assert_not_called()
