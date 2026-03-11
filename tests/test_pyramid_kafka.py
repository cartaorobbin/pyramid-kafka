"""Initial test suite for pyramid-kafka."""

from pyramid_kafka import __init__  # noqa: F401


def test_import():
    """Verify package is importable."""
    import pyramid_kafka

    assert pyramid_kafka is not None
