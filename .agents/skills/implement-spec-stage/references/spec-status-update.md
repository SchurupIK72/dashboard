# Spec Status Update

Use this reference during I5 (item checkbox) and I6 (stage heading, workflow row,
next skill). Statuses are updated only after acceptance and checks — never before.

## Status Marks

| Mark | Meaning | When it appears |
|---|---|---|
| `- [ ]` | Item open | Not yet accepted |
| `- [x]` | Item accepted | Immediately after the I5 `accepted` verdict for this item |
| `⬜` | Stage not started | No verified work on the stage |
| `🔄` | Stage in progress | Partial progress exists (some items `[x]`) while checks are not complete; also the committed state when a session ends mid-stage |
| `✅` | Stage complete | All stage items are `[x]` and the required checks passed (I6) |

## Item Checkbox (I5)

Mark `[x]` immediately after the acceptance verdict, before moving to the next
item. Never mark retroactively without a review, and never ahead of checks.

## Stage Heading (I6)

1. Re-open the spec after the stage checks pass.
2. Update only the selected stage heading to `✅`.
3. If the session ends mid-stage with a partial commit, the stage stays `🔄` and
   accepted items keep their `[x]`.
4. Preserve unrelated spec text.

## Workflow Table Row

After the stage heading, update the skill's own row in `## Workflow выполнения`:

1. Locate the row where the `Навык` column is `implement-spec-stage`.
2. While unchecked stages remain: `🔄` (with progress, e.g. `🔄 (N из M)` — N stages
   complete of M total).
3. Only when every stage heading is `✅`: replace with `✅`.

Each skill updates only its own row. Do not modify rows belonging to other skills.
The single exception: the `write-tests` defect handling may set this skill's row
back to `🔄` during its batch reopen (see below) — it is an acceptance result of
step ③, not a status edit by a foreign skill.

## Reopen From write-tests (③)

When `write-tests` finds confirmed implementation defects
(`write-tests/references/defect-handling.md`), it reopens the affected stages in
one pass — read this state in I1, do not fight it:

- Affected stage headings `✅` → `🔄`; affected items `[x]` → `[ ]`; a defect
  registry link is added near the reopened headings.
- The `implement-spec-stage` workflow row is set back to `🔄` by step ③ (the
  documented exception above); the `write-tests` row stays `⬜`.
- Work the reopened stages through the full I2–I5 cycle
  (`references/stage-selection.md`, Reopened Stages); statuses return to `✅`/`[x]`
  only through normal I5/I6 acceptance.

## Next Skill

- Unchecked stages (`⬜` or `🔄`) remain → `next_skill: implement-spec-stage`; a new
  session continues with the next stage.
- All stages `✅` → `next_skill: write-tests`.

The static `next_skill` field of the workflow validator does not cancel this rule:
verify the remaining stages yourself.

## Completion Output

After updating the spec, report:

```text
spec: {path}
completed_stage: {stage}
remaining_stages: {count}
next_skill: implement-spec-stage | write-tests
```
