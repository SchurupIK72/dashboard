# Test Layer Selection

Choose the lowest layer that proves the behavior without fragility. A higher layer is needed only when a lower-level test cannot see an important contract.

## Matrix

| Change | Primary layer | What to prove | When to add higher |
|---|---|---|---|
| Pure/domain logic, value objects, validators | `tests/unit/` | input/output, invariants, edge cases | When the domain object is wired into a pipeline and there is a risk of incorrect assembly |
| Parsing, formatting, serialization | `tests/unit/` | accepted formats, invalid input, stable output | When the format is an external API or a file artifact |
| Settings/config/defaults | `tests/unit/` | default, override, invalid config | When the config affects an end-to-end route |
| HTTP/API client | `tests/api/` | request shape, response mapping, error mapping, retry/backoff if present | When several clients participate in one workflow |
| CLI command / service entrypoint | `tests/integration/` | wiring, exit/status, generated artifacts | When there is a pure function — cover it with a unit test separately |
| Agent/pipeline flow | `tests/integration/` | step order, state transition, artifacts, rollback/error path | When individual transforms are complex — add a unit test |
| Import boundary / forbidden dependency | `tests/architecture/` | prohibition of cross-layer dependency | When the change creates a new architectural layer |
| Regression for previous bug | The lowest layer that reproduces it | the exact failure scenario | When the bug only manifested through an integration path |

## Selection rules

1. One risk is covered by one most precise test; do not duplicate a single assertion across three layers.
2. Place the mock boundary at external I/O: network, filesystem outside tmp, clock, random, credentials, LLM/API.
3. An integration test must check the wiring, not the details of a pure function.
4. Add an architecture test only for a stable dependency rule, not for a one-off import.
5. If an existing test layer already covers the contract, extend it instead of creating a new file.
