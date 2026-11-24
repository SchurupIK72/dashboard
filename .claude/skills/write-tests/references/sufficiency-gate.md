# Sufficiency Gate — write-tests

Use before the final test run and the commit.

## PASS Criteria

| # | Criterion | How to check |
|---|---|---|
| 1 | Spec complete | All implementation stages in the spec have `✅` |
| 2 | Changed contracts have tests | The coverage matrix contains every new/changed public contract |
| 3 | The right layer is chosen | For every test it is clear why it is `unit/api/integration/architecture` |
| 4 | Negative/boundary coverage exists for risks | A medium/high risk is not covered by happy path only |
| 5 | No live I/O in unit/api | The mock/stub boundary is described and visible in the test |
| 6 | Local test style is used | A reference pattern is found or `NOT_FOUND` is explicitly stated |
| 7 | The evidence run is completed | The engine manifest has `run_status: completed` — every planned set executed over the explicit selection and GREEN |
| 8 | The defect registry is empty | No confirmed implementation defects (`references/defect-handling.md`); a non-empty registry → batch reopen of the affected stages, the gate does not pass |

Criterion 8 is checked first: with a non-empty defect registry there is no
commit path — step ③ ends with a batch reopen
(`references/defect-handling.md`), not with bypassing red tests. Criterion 7
is proven by the manifest (`scripts/test_evidence.py`), not by an unscoped
bare test command.

## FAIL Signals

- A new test checks a private implementation detail with no public effect.
- A test passes only because of execution order or local machine state.
- A changed file has neither a direct nor a justified indirect test.
- An integration test checks too much unrelated behavior.
- An assertion allows any result just to pass.

## Output Before Commit

Before calling `commit-helper`, briefly record:

```markdown
### Test Coverage Summary
| Changed area | Tests added/updated | Risk covered |
|---|---|---|
| `{area}` | `{test path}` | `{contract/error/invariant}` |

Sufficiency gate: PASS
Evidence manifest: `{path} (run_status: completed)`
```
