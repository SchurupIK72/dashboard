# Coverage Matrix

The matrix helps avoid writing "many tests" and instead cover the significant implementation risks. It is a risk checklist, not a coverage-percent target — percent thresholds are not used anywhere in this protocol.

## Mandatory rows

For each changed public contract, check:

| Category | Minimal question | Assertion example |
|---|---|---|
| Happy path | Does the main scenario from the spec work? | result/status/artifact matches the expected one |
| Boundary | What happens on empty, minimal, or maximal input? | empty list, missing field, duplicate key |
| Error path | Is an error turned into a supported result? | exception type, error object, status, log/diagnostic |
| Regression | Is the scenario the code was changed for pinned down? | reproduction of the previous failure |
| Runtime invariant | Is the system's permanent contract intact? | stage order, idempotency, no live call, no forbidden import |
| Artifact/state | Are the created/changed artifacts verified? | file exists, markdown section, DB row, message payload |

## Working template

| Contract | Happy path | Boundary | Error path | Regression | Invariant/artifact | Test file |
|---|---|---|---|---|---|---|
| `{name}` | `{case}` | `{case or n/a}` | `{case or n/a}` | `{case or n/a}` | `{case}` | `{path}` |

## Sufficiency

Coverage is sufficient when:

- every new public contract has a happy path;
- every medium/high risk has at least one negative or boundary case;
- changed artifacts are verified by content, not only by the fact of being called;
- old tests remain GREEN;
- no tests depend on live network, the current date without a clock stub, or local absolute paths.

## Not required

Do not add a test if it:

- repeats an assertion of an already existing test with no new risk;
- tests internal implementation instead of the public effect;
- pins down an accidental order, debug message text, or a private helper without necessity;
- requires real credentials or external service stability.
