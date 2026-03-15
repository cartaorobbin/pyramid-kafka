"""Click-based Kafka consumer CLI runner for Pyramid applications."""

from __future__ import annotations

import importlib
import logging
import signal
import sys
from typing import Any

import click
from pyramid.paster import bootstrap, setup_logging

from pyramid_kafka.core import COMMIT_STRATEGY_TRANSACTION

logger = logging.getLogger(__name__)

_running = True


def _handle_signal(signum: int, frame: Any) -> None:
    """Signal handler that sets the shutdown flag.

    Args:
        signum: The signal number received.
        frame: The current stack frame (unused).
    """
    global _running
    logger.info("Received signal %s, shutting down consumer...", signum)
    _running = False


def _resolve_handler(dotted_path: str) -> Any:
    """Import and return the callable at *dotted_path*.

    Args:
        dotted_path: A ``module.path:callable_name`` string.

    Returns:
        The resolved callable.

    Raises:
        ValueError: If the path format is invalid.
        ImportError: If the module cannot be imported.
        AttributeError: If the callable is not found in the module.
    """
    if ":" not in dotted_path:
        raise ValueError(
            f"Handler path must be 'module.path:callable', got '{dotted_path}'"
        )
    module_path, attr_name = dotted_path.rsplit(":", 1)
    module = importlib.import_module(module_path)
    return getattr(module, attr_name)


def _process_message_auto(
    handler_fn: Any,
    request: Any,
    msg: Any,
) -> None:
    """Process a message with auto commit strategy (current behavior).

    Args:
        handler_fn: The message handler callable.
        request: The Pyramid request.
        msg: The consumed Kafka message.
    """
    try:
        handler_fn(request, msg)
    except Exception:
        logger.exception(
            "Error processing message topic=%s partition=%s offset=%s",
            msg.topic(),
            msg.partition(),
            msg.offset(),
        )


def _process_message_transaction(
    handler_fn: Any,
    request: Any,
    msg: Any,
    consumer: Any,
) -> None:
    """Process a message within a transaction, committing offset on success.

    The handler runs inside a ``transaction`` context.  If the handler
    (and any joined data managers such as SQLAlchemy) succeed, the
    consumer offset is committed synchronously.  On failure the
    transaction is aborted and the offset is **not** committed, so the
    message will be redelivered.

    Args:
        handler_fn: The message handler callable.
        request: The Pyramid request.
        msg: The consumed Kafka message.
        consumer: The confluent-kafka Consumer for offset commits.

    Raises:
        ImportError: If the ``transaction`` package is not installed.
    """
    try:
        import transaction as _txn_mod
    except ImportError:
        raise ImportError(
            "The 'transaction' package is required for "
            "kafka.commit_strategy = 'transaction'. "
            "Install it with: pip install pyramid-kafka[transaction]"
        ) from None

    txn_manager = _txn_mod.TransactionManager(explicit=True)
    txn_manager.begin()
    try:
        handler_fn(request, msg)
        txn_manager.commit()
        consumer.commit(message=msg, asynchronous=False)
        logger.debug(
            "Committed offset topic=%s partition=%s offset=%s",
            msg.topic(),
            msg.partition(),
            msg.offset(),
        )
    except Exception:
        txn_manager.abort()
        logger.exception(
            "Transaction aborted for message topic=%s partition=%s offset=%s",
            msg.topic(),
            msg.partition(),
            msg.offset(),
        )


@click.command("kafka-consumer")
@click.argument("ini_file")
@click.option(
    "--handler",
    default=None,
    help="Dotted path to handler callable (overrides kafka.handler setting).",
)
@click.option(
    "--topics",
    default=None,
    help="Comma-separated topic list (overrides kafka.topics setting).",
)
@click.option(
    "--timeout",
    default=1.0,
    type=float,
    help="Consumer poll timeout in seconds.",
)
def run(
    ini_file: str,
    handler: str | None,
    topics: str | None,
    timeout: float,
) -> None:
    """Start a Kafka consumer for a Pyramid application.

    Args:
        ini_file: Path to the Pyramid .ini configuration file.
        handler: Optional dotted path to handler callable.
        topics: Optional comma-separated topic list.
        timeout: Poll timeout in seconds.
    """
    global _running
    _running = True

    setup_logging(ini_file)
    env = bootstrap(ini_file)
    registry = env["registry"]
    request = env["request"]

    kafka_manager = registry.kafka
    is_transactional = kafka_manager.commit_strategy == COMMIT_STRATEGY_TRANSACTION

    handler_path = handler or registry.settings.get("kafka.handler")
    if not handler_path:
        click.echo(
            "Error: No handler specified. Set 'kafka.handler' in settings "
            "or use --handler.",
            err=True,
        )
        sys.exit(1)

    handler_fn = _resolve_handler(handler_path)

    topic_str = topics or registry.settings.get("kafka.topics", "")
    topic_list = [t.strip() for t in topic_str.replace(",", " ").split() if t.strip()]
    if not topic_list:
        click.echo(
            "Error: No topics specified. Set 'kafka.topics' in settings "
            "or use --topics.",
            err=True,
        )
        sys.exit(1)

    consumer = kafka_manager.consumer
    consumer.subscribe(topic_list)
    logger.info(
        "Subscribed to topics: %s (commit_strategy=%s)",
        topic_list,
        kafka_manager.commit_strategy,
    )

    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    try:
        while _running:
            msg = consumer.poll(timeout)
            if msg is None:
                continue
            if msg.error():
                logger.error("Consumer error: %s", msg.error())
                continue

            if is_transactional:
                _process_message_transaction(handler_fn, request, msg, consumer)
            else:
                _process_message_auto(handler_fn, request, msg)
    finally:
        kafka_manager.close()
        env["closer"]()
        logger.info("Consumer shut down cleanly")
