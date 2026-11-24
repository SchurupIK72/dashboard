# Test Patterns

Before creating new tests, find the nearest existing pattern and continue its style.

## Pattern search

Search in this order:

1. Tests for the same or a neighboring module.
2. Tests of the same layer (`unit`, `api`, `integration`, `architecture`).
3. Fixtures in `tests/conftest.py` and local `conftest.py` files.
4. Helper factories/builders in `tests/**`.
5. If there is no pattern — create a minimal local helper in the new test file.

## Preferred forms

| Situation | Pattern |
|---|---|
| Several inputs of one contract | `pytest.mark.parametrize` |
| Filesystem artifact | `tmp_path`, content verification |
| Time-dependent behavior | injectable clock or monkeypatch clock provider |
| Network/API client | fake transport, mocked response object, no live request |
| Settings | a local `Settings`/env override via fixture/monkeypatch |
| Pipeline state | explicit input state + assertion on final state/artifacts |
| Import rule | architecture test with allowlist/denylist |

## Anti-patterns

- Live API in a unit/api test.
- Sleep instead of a controlled clock.
- Checking only that "the function was called" without the result.
- Hardcoding a model, credential, or the user's absolute path.
- A large fixture that hides a specific test's important inputs.
- A new test helper duplicating an already existing factory.

## Naming

Names must describe observable behavior:

- `test_returns_empty_report_for_empty_input`
- `test_maps_timeout_to_retryable_error`
- `test_pipeline_writes_stage_status_artifact`

Avoid implementation-focused names:

- `test_calls_private_helper`
- `test_internal_flag_true`
