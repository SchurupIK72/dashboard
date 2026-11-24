# Sufficiency Gate

Use this gate in I2 after the researcher report arrives, before assigning an
implementer in I3 — claude policy only: it decides whether the accepted research
is strong enough to implement the item safely. On codex/zcode no separate
research report exists and this gate does not run; instead the main agent checks
the returned implementer report for completeness — research performed and
documented, checks with real exit codes — before accepting the item.

## Criteria

| # | Criterion | Evidence |
|---|---|---|
| 1 | Edit sites are known | The report lists file:symbol for every proposed change; new files carry `NOT_FOUND` with an exact creation location |
| 2 | Existing code is understood | Every existing file proposed for editing was read; the main agent re-checked the key claims against the repository |
| 3 | Contracts are known | Touched DTO/API/CLI/file formats are listed or intentionally absent |
| 4 | Reference pattern is known | An analogous implementation is named, or `NOT FOUND` is recorded with a reason |
| 5 | Data flow is understood | No unresolved `CHAIN_BREAK` at the item's entry or persistence/API boundary |
| 6 | Report follows its format | Required sections present, no unknowns presented as facts, no unanswered `INSUFFICIENT_CONTEXT` |
| 7 | Checks are known | Test command or manual verification for the item is identified |
| 8 | Item boundaries are clear | `allowed_files` covers the edit sites; no dependency on later-stage work |

## Decision

- **0 gaps:** accept the report and proceed to I3.
- **1-2 non-blocking gaps:** read the missing files or inspect nearby patterns
  yourself, record what you added, then re-check the gate.
- **3+ gaps:** do not assign an implementer; ask the user to clarify the item (a new
  researcher round may be needed).
- **Blocking gap:** stop even if it is the only gap.

## Blocking Gaps

- edit sites cannot be identified for an existing-file change
- the item goal conflicts with the architecture or `.ai/DECISIONS.md`
- a required contract is missing
- `CHAIN_BREAK` at the entry or persistence/API boundary
- the researcher answered `INSUFFICIENT_CONTEXT` — fix the package and relaunch the
  researcher instead of answering the question yourself
- checks cannot be identified and no manual verification is acceptable

## Stop Message Shape

```markdown
Not assigning an implementer for item `{checkbox_id}` of stage `{stage}`: the research is not complete enough.

Blocker: {blocking gap}
What needs clarifying: {single question or concrete missing artifact}
```
