# Context Gathering — write-tests

The phase's goal is to turn the completed implementation into a short map of what must be proven by tests.

## Sources

Read in this order:

1. `.ai/specs/{branch-name}.md` — vision, architectural decisions, all completed stages.
2. Step ② artifacts (relying on implement-spec-stage): acceptance tests in `tests/`
   with the `acceptance` marker (what is already proven and by which checks; their
   fate is decided by the Phase 2 curator), item statuses in the spec, stage commits
   (`git log main..HEAD`).
3. `git diff --name-only main...HEAD` or the nearest available base — the actually changed files.
4. The changed files themselves — public functions, classes, CLI/API entrypoints, config, and artifacts.
5. Existing tests nearby in meaning — style, fixtures, helper APIs.
6. `.ai/ARCHITECTURE.md` — layer boundaries and allowed dependencies.

Tracing checks the code against the spec items rather than taking the code as
truth: a persistent "code ≠ spec item" discrepancy is a suspicion of an
implementation defect (`references/defect-handling.md`), not a signal to adjust
the test targets to the code.

## What to extract

| Field | Question |
|---|---|
| Contract | What does the public surface now accept and return? |
| Behavior | What new or changed behavior does the user / calling code see? |
| Failure modes | Which errors, empty inputs, conflicts, and degraded paths are supported? |
| State/artifacts | Which files, statuses, DB records, messages, or side effects change? |
| Configuration | Which settings, env vars, feature flags, or defaults affect behavior? |
| Boundaries | Where are mock/stub needed instead of live I/O? |

## Phase output

Build the working table:

| Changed file | Public surface | Risk | Existing test pattern | Proposed test layer |
|---|---|---|---|---|
| `{path}` | `{function/class/command}` | `{low/medium/high}` | `{test path or NOT_FOUND}` | `{unit/api/integration/architecture}` |

## Stop Conditions

Stop and clarify with the user if:

- the spec is not found or not all stages are marked `✅`;
- the diff contains changes absent from the spec and they change the scope;
- expected behavior cannot be determined without a product decision;
- the check requires a live API/production credential and the mock boundary is unclear.
