# Stage Selection

Use this reference in I1 to select the stage, and during the run to keep item order.

## Stage Selection Rules

1. Stop if current branch is `main` or `master`.
2. Open the spec matching the current branch (`.ai/specs/{branch-name}.md`).
3. Find implementation stages under `## Этапы реализации`.
4. Select the first stage marked 🔄 if one exists.
5. Otherwise select the first stage marked ⬜.
6. Scan the «Зависимости» line of every stage before committing to the first ⬜: a stage whose dependencies are not all ✅ is not selectable — reverse dependencies are invisible to the «first ⬜» rule.
7. If all stages are ✅, stop and tell the user to proceed to `write-tests`.
8. If multiple stages are 🔄: when they come from a batch reopen by `write-tests`
   (`references/defect-handling.md` of that skill — spec carries a defect-registry
   link near the stage headings), select the first 🔄 in record order whose
   dependencies are all ✅ — one stage per session until the list is exhausted;
   ask the user only when the order is genuinely ambiguous.

## Run Scope

Default scope is one selected stage per session. Continue to another stage only when
the user explicitly asked for all stages in this run. Even then, repeat I1–I6 for
every stage.

## Item Order

Inside the selected stage, checklist items (`- [ ] C{n}.{m} …`) are worked in waves
of independent items — record order defines priority:

1. An item under rework is always first; reworking the current item is not a new
   stage.
2. Waves are built greedily in record order per
   `references/parallel-scheduling.md`: a wave is a maximal set of pairwise
   independent open items; items are never skipped or reordered.
3. Within a wave, items proceed in parallel per the host policy — claude:
   researchers → implementers → acceptance testers; codex/zcode: one
   self-sufficient implementer per item, then the acceptance owner per policy.
   The next wave starts only after the previous one is accepted and its
   accumulated acceptance suite is green.
4. Necessary additional work inside the agreed requirements is added as a new open
   item with a new ID at the end of the stage checklist, a requirement link, and a
   one-line reason; accepted IDs are not renumbered. New items join the next
   wave planning.

## Code vs Non-Code Items

Creating or editing source files and executable scripts is code work — it goes
through I2–I5 (claude: researcher, implementer, acceptance tester, formal review;
codex/zcode: one self-sufficient implementer plus the acceptance owner per
policy). Writing tests is also code work, but it belongs exclusively to the
acceptance owner (claude: tester role; zcode: acceptor; codex: the main agent
personally); the implementer never writes tests. Maintaining the spec statuses
and run reports, running checks, and git commands is run bookkeeping — the main
agent performs it directly at wave boundaries on every host. On claude, docs and
other non-code items are performed by the main agent as document work within an
accepted item; on codex/zcode every checklist item, including docs and
configuration, is implemented by the item's single implementer.

## Reopened Stages (from write-tests ③)

A stage reopened by the `write-tests` defect handling (stage heading `🔄`, defect
registry link nearby, uncommitted red proof-tests of ③ in the working tree) is
worked through the full I2–I5 cycle — never a point fix:

- The defect registry entry and the red ③ tests go into the reopened item's
  package as the oracle; after the fix those tests must turn green.
- If the fixed contract legitimately diverges from a ③ test, the acceptance
  tester adapts that test (it lives under `tests/`) and records the reason.
- Uncommitted files owned by step ③ are never staged into this stage's commit —
  stage files explicitly.
- The stage-local test set of I6 must be green together with the ③ proof-tests;
  a still-red proof-test means the fix is incomplete (stage stays not-`✅`).

## Stop Conditions

Stop before edits when:

- no matching spec exists
- spec has no unchecked stages
- selected stage has no files or implementation details
- selected stage depends on an earlier incomplete stage
- user asks to skip a required workflow step

## Output Shape

Before I2, hold this internal state:

```text
spec_path: .ai/specs/{branch-name}.md
selected_stage: {stage title}
stage_status: ⬜ | 🔄
items: [{id, text, code|non-code, open|accepted}]  # in record order
waves: [[{id}, {id}], [{id}], …]  # pairwise-independent sets, record-order priority
edges: [{id} → {id}: {one-line rationale}]
current_wave: [{ids of the wave in progress}]
scope: one_stage | all_stages_requested
```
