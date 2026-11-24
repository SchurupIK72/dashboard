---
name: implement-spec-stage
description: >
  Workflow step ②: implementation of the current spec stage.
  Triggers: "реализуй ТЗ", "implement spec", "продолжи работу",
  "spec-implementer", "implement spec stage", "реализуй этап".
  One host policy — codex | zcode | claude — is fixed before any assignment:
  codex runs one self-sufficient implementer per item with acceptance by the
  main agent personally; zcode adds exactly one independent acceptor whose
  verdict the main agent confirms; claude keeps the researcher → implementer →
  tester chain per code item. Independent items run in parallel waves;
  acceptance ends with a formal check and a commit; an unknown or ambiguous
  host blocks the assignment.
---

# Implement Spec Stage Skill

**Workflow step ②** — implements the items of one spec stage in waves of independent items under one host policy fixed before any assignment: codex — one self-sufficient implementer per item (docs/config included), acceptance personally by the main agent; zcode — implementer plus exactly one independent acceptor, the verdict confirmed by the main agent; claude — a dedicated researcher, implementer, and acceptance tester per code item.

## Workflow Contract

```yaml
entry:
  branch: NOT main | master
  artifacts:
    - .ai/specs/{branch-name}.md
  condition: stages with status ⬜ or 🔄 exist

exit:
  condition: current stage ✅ (all items [x], checks passed, commit successful)
  tests: stage-local test set green (full suite deferred to write-tests ③)

run_scope:
  stage: one current stage per session
  items: waves of independent items (parallel-scheduling); simultaneously — independent items only
  host_policy: codex | zcode | claude — fixed in I1 before any item assignment; an unknown or ambiguous host blocks the assignment

next_skill: implement-spec-stage (stages remain) | write-tests (all stages ✅)

uses:
  - commit-helper
```

## Sub-steps

Load a sub-step's instruction immediately before performing it; the whole set is not loaded in advance. The main agent accepts a sub-step's result before starting the next one.

| # | Sub-step | Instruction | Result and transition condition |
|---|---|---|---|
| I1 | Entry, selection, and wave plan | `references/i1-entry-selection.md` | One eligible stage, item order, wave plan, run directory |
| I2 | Wave research / package preparation | `references/i2-item-research.md` | claude: accepted researcher reports for all items of the wave; codex/zcode: implementer packages for all items of the wave (no researcher, no research_report) |
| I3 | Assignment | `references/i3-assignment.md` | Models per the complexity table for all wave items with a recorded rationale; implementer packages |
| I4 | Implementation | `references/i4-implementation.md` | Changes to wave items only (implementers in parallel, no tests), reports with checks |
| I5 | Acceptance | `references/i5-acceptance.md` | Acceptance tests green by the acceptance owner (codex: main agent personally; zcode: acceptor + main-agent confirmation; claude: tester) + formal check; `[x]` only after accepted |
| I6 | Stage completion | `references/i6-stage-completion.md` | Checks, statuses, commit, stage impact reporter, run cleanup, next_skill |

I2–I5 repeat for every wave; within a wave the item agents of different items run in parallel, but only on independent items (`references/parallel-scheduling.md`) — claude: researchers, implementers, and testers; codex/zcode: one self-sufficient implementer per item plus the acceptance owner per policy. On claude the main agent performs non-code items itself at wave boundaries and accepts them itself; on codex/zcode every checklist item, including docs and configuration, is assigned to the item's implementer — the main agent keeps only run bookkeeping. Creating or editing sources and executable scripts is a code change; maintaining the spec, writing reports, running checks, and git commands are not. An item's tests are written only by the acceptance owner (claude: tester; zcode: acceptor; codex: the main agent personally) — the implementer writes no tests. Reworking the current item is not a new stage; rework returns of one result are limited to two.

## Repo-root Scripts

| Script | When to run | Purpose |
|---|---|---|
| `scripts/validate_workflow_state.py` | In I1 | Common workflow state gate (`--step implement-spec-stage`). Path **from the repository root**, not from the skill directory |

## Skill-local Supporting Files

| File | When to read | Purpose |
|---|---|---|
| `LEARNINGS.md` | In I1 | Only the lessons of past implementations relevant to the current run |
| `references/i1-entry-selection.md` … `references/i6-stage-completion.md` | Immediately before the corresponding sub-step | Detailed sub-step instructions (table above) |
| `references/stage-selection.md` | In I1, when selecting the stage and item order | Stage selection rules, item order, code/non-code, STOP conditions |
| `references/parallel-scheduling.md` | In I1 (wave plan) and I2–I5 (wave execution) | Dependency graph, independence criteria, waves, acceptance-suite run |
| `references/context-gathering.md` | claude — in I2, before composing the researcher package | Item context: what the main agent reads, what goes into the package |
| `references/agent-orchestration.md` | In I2, I4, and I5, before launching a role | Launching workflow roles (including in parallel), adapters, report verification |
| `references/sufficiency-gate.md` | claude — in I2, when accepting research | Research sufficiency criteria before assigning an implementer; codex/zcode check implementer report completeness instead |
| `references/stage-implementation.md` | In I4–I5 | Item boundaries, division of labor, formal diff check at acceptance |
| `references/spec-status-update.md` | In I5 (checkbox) and I6 (stage, skill row) | Status rules and next_skill |
| `references/task-package.md` | In I2, I3, I5 | Task package contract (implementer field set incl. `item_baseline`, list fields explicit when empty) and result acceptance loop; the `research_report` field applies to claude only |
| `references/model-selection.md` | In I3, when choosing the model | Complexity table (incl. the tester), recording the choice, model unavailability — stop |
| `references/run-artifacts.md` | In I1 (creation), I6 (cleanup) | Run directory with per-item `item_baseline`/`item_diff` storage, resume, limited cleanup |
| `scripts/validate_stage_completion.py` | In I6, after updating statuses | Consistency of spec stage statuses |
| `references/stage-impact-report.md` | In I6, after the commit | Launch of the one stage-level impact-reporter sub-agent: trigger, single-reporter rule, host-uniform role, advisory failure semantics |
| `EVALS.md` | Before changing skill behavior | Regression cases for the eval gate |

## Algorithm

1. **Read relevant experience** — open `LEARNINGS.md` and apply only the lessons related to the current stage (I1).
2. **Perform sub-steps I1–I6 strictly in order** — before each sub-step load its instruction from the "Sub-steps" table; work the stage's items sequentially (I2–I5 for every item: claude — code items; codex/zcode — all items, docs/config included); accept each sub-step's result before moving to the next.
3. **Output the I6 result** — path to the spec, stage statuses, number of remaining stages, and the next step: `implement-spec-stage` or `write-tests`.

## Validation Checklist

- [ ] ENTRY: current branch is not `main/master`; the workflow validator passed (I1).
- [ ] Exactly one stage with completed dependencies selected; wave plan built; no items with overlapping `allowed_files` or explicit dependencies in one wave.
- [ ] Per-host topology held: claude — every code item got its own researcher, its own implementer, and its own acceptance tester; codex/zcode — exactly one self-sufficient implementer per item (docs/config included) with the acceptance owner per policy (codex: the main agent personally, incl. acceptance tests; zcode: one independent acceptor); sub-agents received a task package, not the chat history.
- [ ] The implementer model selected per the complexity table; the choice recorded; claude — the tester always on the junior model; zcode — the acceptor on the host session model; codex — no tester sub-agent; model unavailability — stop without fallback.
- [ ] Implementers wrote no tests; acceptance tests carry the `acceptance` marker; claude/zcode — the tester/acceptor touched nothing outside `tests/`.
- [ ] Item diffs carry no comment pollution: traceability only via `D##` of `.ai/DECISIONS.md`; no spec refs, narrative descriptions, TODO/FIXME, or debug leftovers (preparation for the release cleanliness gate, `integrate-release` Step 3.5).
- [ ] Each item accepted by two checks: functionally — the tester's tests, formally — the main agent (boundaries, format, conformance to the item); at most two rework returns per item.
- [ ] At the end of each wave the stage's accumulated acceptance suite is green; a failure reopens the owning item.
- [ ] `[x]` stands only on accepted items; a stage is `✅` only after all items and checks.
- [ ] Changes are limited to the current stage's items.
- [ ] The stage-local test set is green — the stage's accumulated acceptance tests plus directly related existing tests, every command with explicit paths/node ids; a full-suite run (`uv run pytest` without path filters, repo-wide marker sweeps) never happens during ② — the full suite belongs to `write-tests` ③; test commands are timeout-wrapped ≤ 150 s (budgets of `.ai/TESTS_CONFIG.md`).
- [ ] The spec is updated after the checks, not earlier; next_skill determined by the remaining stages.
- [ ] The commit is created; the current run's temporary files are deleted only after it.

## Continuous Improvement

After each run completes, perform Improvement Triage:

1. Task solved without ambiguities → output `no_change`.
2. A reusable lesson discovered → add a short entry to `LEARNINGS.md`.
3. Skill instructions led to an error → first create an eval case in `EVALS.md`.
4. Propose a `SKILL.md` patch only if the same problem can recur.
5. Prefer replacing, removing, or moving rules to a supporting file over plain addition.
6. Do not update `SKILL.md` before the corresponding eval passes.

## Rules

1. One run implements one stage; the stage's items run in waves of independent ones: only items without `allowed_files` overlap and without explicit dependencies execute simultaneously; the next wave starts after the previous one is accepted and its acceptance suite is green (`references/parallel-scheduling.md`).
2. An item's source code is written only by the implementer; its acceptance tests — only by the acceptance owner per host policy: claude — the acceptance tester (always the junior model); zcode — one independent acceptor; codex — the main agent personally. On claude/zcode the main agent edits neither code nor tests — it maintains the spec, reports, checks, and git commands, performs the formal acceptance, and on claude performs non-code items itself; on codex the main agent never edits item source code, but writes and runs the acceptance tests itself.
3. A sub-agent receives a task package, never the main chat history; role definitions are not duplicated in the skill.
4. Item acceptance = the functional verdict of the acceptance owner (`passed`) + the main agent's own role in the check: claude — the tester's verdict plus the formal check; zcode — one independent acceptor's verdict plus the main agent's confirmation; codex — the main agent's own tests, diff investigation, and verdict, no sub-agent. Failed tests → a rework return to the same implementer with the list of failed tests; per result — one first check and at most two rework returns; a defect in the test itself is fixed by the test owner without spending the rework limit; after a third unsuccessful check — stop and ask the user; the model never changes automatically.
5. The implementer model is selected per the complexity table with a recorded rationale; claude — the tester is always on the junior model regardless of item complexity; zcode — the acceptor runs on the host session model (per-launch pinning unavailable); codex — no tester sub-agent, acceptance is the main agent's own work; model or context-isolation unavailability is a blocking stop without silent substitution (`references/model-selection.md`).
6. Checkbox `[x]` — after the item is accepted; stage `✅` — after all the stage's items and checks; the skill row `✅` — only when all spec stages are complete.
7. `next_skill`: `implement-spec-stage` while unfinished stages remain, otherwise `write-tests`; the validator's static field does not cancel checking the remaining stages.
8. Run results are stored under `.ai/workflow-runs/{branch-slug}/implement-spec-stage/{stage-id}/{run-id}/`; on failure, rejection, or a missed commit they are kept; only the successful run's directory is deleted after the commit; full cleanup of the branch directory is the `integrate-release` step (`references/run-artifacts.md`).
9. The source of truth for the skill is `skills/implement-spec-stage`; the runtime copies (`.agents/skills/`, `.claude/skills/`) are synchronized from it and are not edited directly. Do not edit the skill inside an installed project: dot_ai is the source of truth.
10. A behavioral change to the skill requires an eval case or explicit manual justification.
11. Test command scope and budget (`.ai/TESTS_CONFIG.md`): during ② only the stage-local test set runs — the stage's accumulated acceptance tests (explicit paths from the state file's item→tests mapping) plus existing tests directly related to the changed symbols (explicit paths/node ids from the wave research); a bare `uv run pytest`, a repo-wide `-m acceptance` sweep, or any other full-suite run never happens at any sub-step — the full suite belongs to `write-tests` ③. Every sub-agent test command ≤ 150 s — a `timeout 150` wrapper, output to a file, no pipe; a pytest process longer than 200 s is a hang, not a slow test (on Windows — post-test teardown): kill it and read the results from the file. If it does not fit the budget, the test gets the `slow` marker (excluded from the default run), not silent waiting.
12. A stage reopened by step ③ (`write-tests` defect handling: stage `🔄`, defect registry with a link in the spec, red ③ proof-tests in the working tree without a commit): the registry and the red tests go into the item's package as the oracle — after the fix the ③ tests must turn green; a legitimate divergence of the fixed contract from a ③ test is adapted by the acceptance tester with the reason recorded in the report; foreign uncommitted files of step ③ are never staged into the stage's commit (stage files explicitly). With several `🔄`, the stage is selected by dependencies (`references/stage-selection.md`); ask the user only on genuine ambiguity.
