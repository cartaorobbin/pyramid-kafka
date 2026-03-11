---
name: lint-format
description: Lint and format code for pyramid-kafka. Use when the user asks to lint, format, check style, or fix code style.
---

# Lint and Format

## Check (no changes)

```bash
uv run ruff check .
uv run black --check .
```

## Fix

```bash
uv run ruff check . --fix
uv run black .
```
