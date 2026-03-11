---
alwaysApply: true
---

# Code Quality Rules

These rules apply to **every** chat, regardless of whether the full dev workflow is active.

## Testing Principles

### Function-Based Tests Only

NEVER use class-based test cases. Use individual test functions with descriptive names.

- **Bad**: `class TestUser:` with methods
- **Good**: `test_user_creation_from_email()`

### Descriptive Test Names

Follow the pattern `test_[component]_[action]_[scenario]`:

- **Good**: `test_payment_refund_partial_amount`
- **Bad**: `test_refund`, `test_1`

### Single Concept Per Test

Each test function tests exactly ONE concept. Multiple asserts on the same result are fine when they verify different facets of a single outcome. Do not combine unrelated assertions.

### Parametrized Tests for Multiple Cases

Use `pytest.mark.parametrize` (or the framework equivalent) when testing the same behavior with different inputs rather than duplicating test functions.

### No Conditional Logic in Tests

Tests must be deterministic. No `if` statements, no loops over assertions. Use separate tests or parametrize instead.

### Assert Exact Values, Not Calculations

When the expected value is known, assert equality with a literal value. Never compute the expected value in the test itself — that hides bugs.

- **Good**: `assert result.total == Money("150.75")`
- **Bad**: `assert result.total == price + tax`

### No Mocks Unless Absolutely Necessary

Test with real objects and real behavior. Only use mocks when the dependency is truly external (network, filesystem, third-party service) and cannot be replaced with a simpler in-memory alternative.

### Prefer Fixtures Over Helper Functions

When test setup is reused across multiple tests, express it as a pytest fixture (or framework equivalent) — not a plain helper function. Fixtures are composable, cacheable, and visible to the test runner.

## Code Quality

### Type Hints

Use type hints for all function signatures and class attributes.

### No Obvious Comments

Do not add comments that merely narrate what the code does. Comments should explain non-obvious intent, trade-offs, or constraints that the code itself cannot convey.

### Clean Formatting

Run the project's formatter and linter before committing. All pre-commit checks must pass.
