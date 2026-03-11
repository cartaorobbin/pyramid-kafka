"""Tests for pyramid_kafka.consumer — CLI runner and handler resolution."""

from __future__ import annotations

import pytest

from pyramid_kafka.consumer import _resolve_handler


def test_resolve_handler_valid_path():
    """_resolve_handler imports a callable from a dotted path."""
    handler = _resolve_handler("tests.conftest:_dummy_handler")

    assert callable(handler)
    assert handler.__name__ == "_dummy_handler"


def test_resolve_handler_invalid_format():
    """_resolve_handler raises ValueError when ':' separator is missing."""
    with pytest.raises(ValueError, match="module.path:callable"):
        _resolve_handler("no_colon_here")


def test_resolve_handler_missing_module():
    """_resolve_handler raises ImportError for a non-existent module."""
    with pytest.raises(ImportError):
        _resolve_handler("nonexistent.module:func")


def test_resolve_handler_missing_attribute():
    """_resolve_handler raises AttributeError for missing callable in module."""
    with pytest.raises(AttributeError):
        _resolve_handler("tests.conftest:nonexistent_function")
