---
name: run-tests
description: Run the test suite for pyramid-kafka. Use when the user asks to run tests, check tests, or verify the project.
---

# Run Tests

Run the full test suite:

```bash
uv run pytest
```

Run a specific test file:

```bash
uv run pytest tests/test_specific.py
```

Run with verbose output:

```bash
uv run pytest -v
```

Run with coverage:

```bash
uv run pytest --cov=src/pyramid_kafka
```
