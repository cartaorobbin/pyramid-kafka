"""Tests for transactional consumer message processing."""

from __future__ import annotations

import sys
from unittest.mock import MagicMock

import pytest

from pyramid_kafka.consumer import _process_message_auto, _process_message_transaction


def test_process_message_auto_calls_handler():
    """_process_message_auto calls the handler with request and msg."""
    handler = MagicMock()
    request = MagicMock()
    msg = MagicMock()

    _process_message_auto(handler, request, msg)

    handler.assert_called_once_with(request, msg)


def test_process_message_auto_logs_handler_exception():
    """_process_message_auto catches and logs handler exceptions."""
    handler = MagicMock(side_effect=RuntimeError("boom"))
    request = MagicMock()
    msg = MagicMock()
    msg.topic.return_value = "t1"
    msg.partition.return_value = 0
    msg.offset.return_value = 42

    _process_message_auto(handler, request, msg)

    handler.assert_called_once()


@pytest.fixture()
def _mock_transaction():
    """Temporarily replace the ``transaction`` module with a MagicMock."""
    mock_mod = MagicMock()
    original = sys.modules.get("transaction")
    sys.modules["transaction"] = mock_mod
    yield mock_mod
    if original is not None:
        sys.modules["transaction"] = original
    else:
        del sys.modules["transaction"]


def test_process_message_transaction_commits_on_success(_mock_transaction):
    """On success: handler runs, transaction commits, offset is committed."""
    mock_tm = MagicMock()
    _mock_transaction.TransactionManager.return_value = mock_tm

    handler = MagicMock()
    request = MagicMock()
    msg = MagicMock()
    consumer = MagicMock()

    _process_message_transaction(handler, request, msg, consumer)

    mock_tm.begin.assert_called_once()
    handler.assert_called_once_with(request, msg)
    mock_tm.commit.assert_called_once()
    consumer.commit.assert_called_once_with(message=msg, asynchronous=False)
    mock_tm.abort.assert_not_called()


def test_process_message_transaction_aborts_on_failure(_mock_transaction):
    """On failure: transaction aborts, offset is NOT committed."""
    mock_tm = MagicMock()
    _mock_transaction.TransactionManager.return_value = mock_tm

    handler = MagicMock(side_effect=RuntimeError("db error"))
    request = MagicMock()
    msg = MagicMock()
    msg.topic.return_value = "t1"
    msg.partition.return_value = 0
    msg.offset.return_value = 99
    consumer = MagicMock()

    _process_message_transaction(handler, request, msg, consumer)

    mock_tm.begin.assert_called_once()
    handler.assert_called_once()
    mock_tm.abort.assert_called_once()
    mock_tm.commit.assert_not_called()
    consumer.commit.assert_not_called()


def test_process_message_transaction_creates_explicit_manager(_mock_transaction):
    """_process_message_transaction creates an explicit TransactionManager."""
    mock_tm = MagicMock()
    _mock_transaction.TransactionManager.return_value = mock_tm

    _process_message_transaction(MagicMock(), MagicMock(), MagicMock(), MagicMock())

    _mock_transaction.TransactionManager.assert_called_once_with(explicit=True)
